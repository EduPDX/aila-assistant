"""Gerenciamento de contexto de conversa (memória de curto prazo).

Mantém a janela de mensagens que é enviada ao LLM. Quando o histórico cresce
demais, as mensagens mais antigas são condensadas em um resumo, preservando a
mensagem de sistema (persona).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(slots=True)
class Message:
    role: Role
    content: str
    name: str | None = None  # nome do agente/ferramenta, quando role="tool"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_llm(self) -> dict[str, str]:
        msg = {"role": self.role, "content": self.content}
        if self.name:
            msg["name"] = self.name
        return msg


class ConversationContext:
    """Histórico de uma sessão de conversa."""

    def __init__(self, system_prompt: str, max_turns: int = 20) -> None:
        self.system = Message(role="system", content=system_prompt)
        self.max_turns = max_turns
        self._messages: list[Message] = []
        self._summary: str | None = None

    def add_user(self, content: str) -> None:
        self._messages.append(Message(role="user", content=content))
        self._trim()

    def add_assistant(self, content: str) -> None:
        self._messages.append(Message(role="assistant", content=content))

    def add_tool(self, name: str, content: str) -> None:
        self._messages.append(Message(role="tool", name=name, content=content))

    def _trim(self) -> None:
        """Mantém apenas os últimos ``max_turns`` turnos na janela ativa.

        As mensagens excedentes ficam disponíveis para sumarização futura
        (gancho para o módulo de memória de longo prazo / RAG).
        """
        limit = self.max_turns * 2  # ~2 mensagens por turno (user + assistant)
        if len(self._messages) > limit:
            self._messages = self._messages[-limit:]

    def set_summary(self, summary: str) -> None:
        self._summary = summary

    def build(self) -> list[dict[str, str]]:
        """Monta a lista de mensagens no formato do LLM."""
        out = [self.system.to_llm()]
        if self._summary:
            out.append(
                {"role": "system", "content": f"Resumo da conversa anterior: {self._summary}"}
            )
        out.extend(m.to_llm() for m in self._messages)
        return out

    def clear(self) -> None:
        self._messages.clear()
        self._summary = None
