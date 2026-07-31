"""Backend Ollama (HTTP) com streaming.

Fala com a API nativa do Ollama (`/api/chat`, `/api/tags`). Aproveita a
aceleração CUDA da RTX 4060 automaticamente — o offload de camadas para a GPU
é gerenciado pelo próprio Ollama.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from aila.core.logging import get_logger
from aila.llm.base import ChatChunk, LLMBackend

log = get_logger("ollama")


class OllamaBackend(LLMBackend):
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        default_model: str = "qwen2.5:7b-instruct",
        keep_alive: str = "10m",
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.keep_alive = keep_alive
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

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
        body: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": stream,
            "keep_alive": self.keep_alive,
            "options": {},
        }
        if tools:
            body["tools"] = tools
        if temperature is not None:
            body["options"]["temperature"] = temperature
        if max_tokens is not None:
            body["options"]["num_predict"] = max_tokens
        body["options"].update(kwargs.get("options", {}))

        if not stream:
            resp = await self._client.post("/api/chat", json=body)
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("message", {})
            yield ChatChunk(
                content=msg.get("content", ""),
                done=True,
                tool_calls=msg.get("tool_calls") or None,
                meta={k: data.get(k) for k in ("total_duration", "eval_count")},
            )
            return

        try:
            async for chunk in self._stream(body):
                yield chunk
        except httpx.HTTPStatusError as exc:
            # Modelo sem suporte a tools em streaming: repete sem ferramentas.
            if tools and exc.response.status_code in (400, 500):
                log.warning("modelo sem suporte a tools no stream; repetindo sem elas")
                body.pop("tools", None)
                async for chunk in self._stream(body):
                    yield chunk
            else:
                raise

    async def _stream(self, body: dict[str, Any]) -> AsyncIterator[ChatChunk]:
        async with self._client.stream("POST", "/api/chat", json=body) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    log.warning(f"linha não-JSON do Ollama ignorada: {line[:80]}")
                    continue
                msg = data.get("message", {})
                content = msg.get("content", "")
                tool_calls = msg.get("tool_calls") or None
                done = bool(data.get("done"))
                if content or done or tool_calls:
                    yield ChatChunk(
                        content=content,
                        done=done,
                        tool_calls=tool_calls,
                        meta={"eval_count": data.get("eval_count")} if done else None,
                    )

    # ------------------------------------------------------------------ #
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
        body: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.keep_alive,
        }
        if tools:
            body["tools"] = tools
        try:
            resp = await self._client.post("/api/chat", json=body)
            resp.raise_for_status()
            return resp.json().get("message", {"role": "assistant", "content": ""})
        except httpx.HTTPStatusError as exc:
            # Modelo pode não suportar tools: tenta de novo sem elas.
            if tools and exc.response.status_code in (400, 500):
                log.warning("modelo sem suporte a tools; repetindo sem ferramentas")
                body.pop("tools", None)
                resp = await self._client.post("/api/chat", json=body)
                resp.raise_for_status()
                return resp.json().get("message", {"role": "assistant", "content": ""})
            raise

    async def list_models(self) -> list[str]:
        try:
            resp = await self._client.get("/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except httpx.HTTPError as exc:
            log.error(f"falha ao listar modelos: {exc!r}")
            return []

    async def health(self) -> bool:
        try:
            resp = await self._client.get("/api/version")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def aclose(self) -> None:
        await self._client.aclose()
