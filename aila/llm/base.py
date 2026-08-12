"""Interface abstrata de backend de LLM.

Qualquer motor de inferência (Ollama, llama.cpp, vLLM, ...) implementa esta
interface, de modo que o resto do sistema não conhece detalhes do backend.
"""

from __future__ import annotations

import abc
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ChatChunk:
    """Um pedaço de resposta em streaming."""

    content: str
    # raciocínio (reasoning_content) de modelos "thinking" (ex.: Nemotron) —
    # separado do content; a UI mostra num bloco colapsável.
    reasoning: str = ""
    done: bool = False
    # tool_calls aparecem quando o modelo decide usar ferramentas (mesmo em stream)
    tool_calls: list[dict[str, Any]] | None = None
    # metadados opcionais no chunk final (tokens, duração etc.)
    meta: dict[str, Any] | None = None


@dataclass(slots=True)
class ModelCapabilities:
    """O que um provedor/modelo suporta — usado pelo Model Router p/ decidir.

    Default conservador (só chat local). Cada provedor sobrescreve o que oferece.
    """

    tools: bool = True          # function/tool calling
    vision: bool = False        # entrada de imagem
    streaming: bool = True
    structured: bool = False    # saída estruturada / JSON mode
    context: int = 8192         # janela de contexto (tokens)
    local: bool = True          # roda no PC (sem enviar dados p/ fora)


class LLMBackend(abc.ABC):
    """Contrato mínimo de um backend de chat."""

    #: identificador do provedor (ex.: "ollama", "openai") — usado em logs/router
    name: str = "llm"

    def capabilities(self, model: str | None = None) -> ModelCapabilities:
        """Capacidades do provedor (opcionalmente por modelo). Default conservador;
        provedores externos/multimodais sobrescrevem."""
        return ModelCapabilities()

    @abc.abstractmethod
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
        """Gera uma resposta de chat. Deve ser um gerador assíncrono.

        Se ``tools`` for informado e o modelo optar por usá-las, os chunks
        podem conter ``tool_calls`` (o backend deve fazer fallback sem tools
        caso o modelo não suporte).
        """
        raise NotImplementedError
        yield  # pragma: no cover  (torna a assinatura um async generator)

    @abc.abstractmethod
    async def complete(
        self, messages: list[dict[str, str]], *, model: str | None = None, **kwargs: Any
    ) -> str:
        """Conveniência: retorna a resposta completa como string."""
        raise NotImplementedError

    async def chat_message(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Chamada não-streaming que devolve a mensagem completa do assistente,
        incluindo ``tool_calls`` quando o modelo decide usar ferramentas.

        Implementação-base (fallback): ignora ``tools`` e devolve só o texto.
        Backends com suporte nativo a tool-calling devem sobrescrever.
        """
        text = await self.complete(messages, model=model, **kwargs)
        return {"role": "assistant", "content": text, "tool_calls": []}

    async def embed(
        self, texts: list[str], *, model: str | None = None
    ) -> list[list[float]]:
        """Gera embeddings para uma lista de textos.

        Usado pela memória de longo prazo (RAG). Backends sem suporte a
        embeddings devem levantar ``NotImplementedError``.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def list_models(self) -> list[str]:
        """Lista os modelos disponíveis no backend."""
        raise NotImplementedError

    @abc.abstractmethod
    async def health(self) -> bool:
        """True se o backend está acessível."""
        raise NotImplementedError

    async def aclose(self) -> None:
        """Libera recursos (conexões etc.). Opcional."""
