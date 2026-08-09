"""Backend para provedores compatíveis com a API OpenAI.

OpenAI, DeepSeek, xAI/Grok e Google Gemini expõem endpoints
``/chat/completions`` no formato da OpenAI — então UM backend parametrizado
(base_url + api_key + modelo) atende os quatro, em vez de 4 clientes
duplicados. As capacidades (visão, contexto) variam por provedor e vêm da
config.

Segurança: a ``api_key`` vem da configuração (env/local.yaml), nunca do
código. Antes de qualquer chamada, consulta a ``NetworkPolicy`` — no modo
OFFLINE o provedor se recusa a sair para a rede.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

import httpx

from aila.core.logging import get_logger
from aila.llm.base import ChatChunk, LLMBackend, ModelCapabilities

if TYPE_CHECKING:
    from aila.core.config import Settings
    from aila.security.network_policy import NetworkPolicy

log = get_logger("provider")


class OpenAICompatBackend(LLMBackend):
    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        api_key: str,
        default_model: str,
        vision: bool = False,
        context: int = 128000,
        network: NetworkPolicy | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self._vision = vision
        self._context = context
        self.network = network
        self.last_tps = 0.0
        self._client = httpx.AsyncClient(
            base_url=self.base_url, timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def capabilities(self, model: str | None = None) -> ModelCapabilities:
        return ModelCapabilities(
            tools=True, vision=self._vision, streaming=True, structured=True,
            context=self._context, local=False,
        )

    def _guard(self) -> None:
        if self.network is not None:
            self.network.guard(f"provedor externo '{self.name}'")

    # ------------------------------------------------------------------ #
    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = True,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatChunk]:
        self._guard()   # offline → NetworkBlocked
        body: dict[str, Any] = {"model": model or self.default_model, "messages": messages}
        if tools:
            body["tools"] = tools
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        if not stream:
            resp = await self._client.post("/chat/completions", json=body)
            resp.raise_for_status()
            msg = resp.json()["choices"][0]["message"]
            yield ChatChunk(content=msg.get("content") or "", done=True,
                            tool_calls=msg.get("tool_calls") or None)
            return

        body["stream"] = True
        async for chunk in self._stream(body):
            yield chunk

    async def _stream(self, body: dict[str, Any]) -> AsyncIterator[ChatChunk]:
        acc: dict[int, dict[str, str]] = {}   # index -> {id, name, arguments}
        async with self._client.stream("POST", "/chat/completions", json=body) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = obj.get("choices") or [{}]
                delta = choices[0].get("delta", {})
                if delta.get("content"):
                    yield ChatChunk(content=delta["content"])
                for tcd in delta.get("tool_calls") or []:
                    idx = tcd.get("index", 0)
                    slot = acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                    if tcd.get("id"):
                        slot["id"] = tcd["id"]
                    fn = tcd.get("function") or {}
                    if fn.get("name"):
                        slot["name"] = fn["name"]
                    if fn.get("arguments"):
                        slot["arguments"] += fn["arguments"]
        tool_calls = _finalize_tools(acc)
        yield ChatChunk(content="", done=True, tool_calls=tool_calls or None)

    async def complete(
        self, messages: list[dict[str, str]], *, model: str | None = None, **kwargs: Any
    ) -> str:
        parts: list[str] = []
        async for chunk in self.chat(messages, model=model, stream=True, **kwargs):
            parts.append(chunk.content)
        return "".join(parts)

    async def chat_message(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self._guard()
        body: dict[str, Any] = {"model": model or self.default_model, "messages": messages}
        if tools:
            body["tools"] = tools
        resp = await self._client.post("/chat/completions", json=body)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]

    async def list_models(self) -> list[str]:
        try:
            self._guard()
            resp = await self._client.get("/models")
            resp.raise_for_status()
            return [m["id"] for m in resp.json().get("data", [])]
        except Exception as exc:  # noqa: BLE001
            log.warning(f"{self.name}: falha ao listar modelos: {exc!r}")
            return []

    async def health(self) -> bool:
        if self.network is not None and self.network.is_offline:
            return False
        try:
            resp = await self._client.get("/models")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def aclose(self) -> None:
        await self._client.aclose()


def _finalize_tools(acc: dict[int, dict[str, str]]) -> list[dict]:
    """Converte os deltas de tool_call acumulados no formato que o engine lê."""
    calls: list[dict] = []
    for slot in acc.values():
        if not slot["name"]:
            continue
        calls.append({
            "id": slot["id"], "type": "function",
            "function": {"name": slot["name"], "arguments": slot["arguments"] or "{}"},
        })
    return calls


# metadados oficiais por provedor (base_url/modelo/capacidades). A config só
# precisa de enabled+api_key; estes são o default (a config pode sobrescrever).
PROVIDER_DEFAULTS: dict[str, dict[str, Any]] = {
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini",
               "vision": True, "context": 128000},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
               "model": "gemini-2.0-flash", "vision": True, "context": 1000000},
    "grok": {"base_url": "https://api.x.ai/v1", "model": "grok-2-latest",
             "vision": False, "context": 131072},
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat",
                 "vision": False, "context": 64000},
}


def build_external_providers(
    settings: Settings, network: NetworkPolicy | None = None
) -> dict[str, LLMBackend]:
    """Cria os provedores externos HABILITADOS (com api_key), resolvendo
    base_url/modelo/capacidades pela tabela (config sobrescreve se preenchida)."""
    out: dict[str, LLMBackend] = {}
    for name, cfg in settings.providers.items():
        if not cfg.enabled:
            continue
        if not cfg.api_key:
            log.warning(f"provedor '{name}' habilitado mas SEM api_key — ignorado.")
            continue
        d = PROVIDER_DEFAULTS.get(name, {})
        base_url = cfg.base_url or d.get("base_url", "")
        model = cfg.model or d.get("model", "")
        if not base_url or not model:
            log.warning(f"provedor '{name}' sem base_url/modelo — ignorado.")
            continue
        out[name] = OpenAICompatBackend(
            name=name, base_url=base_url, api_key=cfg.api_key, default_model=model,
            vision=cfg.vision or d.get("vision", False),
            context=cfg.context or d.get("context", 128000),
            network=network, timeout=settings.llm.timeout_seconds,
        )
        log.info(f"provedor externo habilitado: {name} ({model})")
    return out
