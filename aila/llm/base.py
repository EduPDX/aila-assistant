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
    done: bool = False
    # tool_calls aparecem quando o modelo decide usar ferramentas (mesmo em stream)
    tool_calls: list[dict[str, Any]] | None = None
    # metadados opcionais no chunk final (tokens, duração etc.)
    meta: dict[str, Any] | None = None


class LLMBackend(abc.ABC):
    """Contrato mínimo de um backend de chat."""

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
