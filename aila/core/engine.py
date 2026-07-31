"""AilaEngine — o orquestrador central.

Responsabilidades:
    - montar o prompt de sistema (persona + capacidades dos agentes),
    - manter o contexto de conversa,
    - executar dois modos:
        * chat    -> resposta em streaming, sem ferramentas (rápido),
        * agent   -> laço de tool-calling (usa os agentes),
    - emitir estados do avatar (emotion engine) pelo event bus.

Toda saída flui pelo callback ``emit`` (tipicamente ligado ao EventBus /
WebSocket), então a engine não conhece a camada de transporte.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from aila.agents.base import AgentDeps
from aila.agents.manager import AgentManager
from aila.avatar.emotion_engine import EmotionEngine
from aila.core.config import Settings
from aila.core.context import ConversationContext, Message
from aila.core.logging import get_logger
from aila.llm.base import LLMBackend

log = get_logger("engine")

# emit(event_type, payload) -> None
Emit = Callable[[str, dict[str, Any]], Awaitable[None]]

MAX_TOOL_ITERS = 5


class AilaEngine:
    def __init__(self, settings: Settings, llm: LLMBackend, agents: AgentManager) -> None:
        self.settings = settings
        self.llm = llm
        self.agents = agents
        self.emotions = EmotionEngine()
        self.context = ConversationContext(
            system_prompt=self._system_prompt(),
            max_turns=settings.context.max_turns,
        )

    # ------------------------------------------------------------------ #
    def _system_prompt(self) -> str:
        base = self.settings.app.persona.strip()
        caps = self.agents.describe_capabilities()
        return f"{base}\n\n{caps}"

    # ------------------------------------------------------------------ #
    async def stream_reply(self, user_text: str, emit: Emit) -> str:
        """Modo CHAT: streaming puro, sem ferramentas. Baixa latência."""
        await emit("avatar.state", self.emotions.thinking().to_event_payload())
        self.context.add_user(user_text)

        parts: list[str] = []
        async for chunk in self.llm.chat(self.context.build(), stream=True):
            if chunk.content:
                parts.append(chunk.content)
                await emit("assistant.token", {"text": chunk.content})

        final = "".join(parts).strip()
        self.context.add_assistant(final)
        await emit("assistant.message", {"text": final})
        await emit("avatar.state", self.emotions.from_text(final).to_event_payload())
        return final

    # ------------------------------------------------------------------ #
    async def run_agentic(self, user_text: str, emit: Emit) -> str:
        """Modo AGENT: laço de tool-calling usando os agentes habilitados."""
        await emit("avatar.state", self.emotions.thinking().to_event_payload())
        self.context.add_user(user_text)
        tools = self.agents.registry.schemas()

        final_text = ""
        for _ in range(MAX_TOOL_ITERS):
            msg = await self.llm.chat_message(self.context.build(), tools=tools)
            tool_calls = msg.get("tool_calls") or []

            if not tool_calls:
                final_text = (msg.get("content") or "").strip()
                break

            # registra o turno do assistente que pediu as ferramentas
            self.context._messages.append(
                Message(role="assistant", content=msg.get("content", ""))
            )
            for call in tool_calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                await emit("agent.invoked", {"tool": name, "args": args})
                result = await self.agents.registry.execute(name, args)
                await emit(
                    "agent.result",
                    {"tool": name, "ok": result.ok, "content": result.content[:2000]},
                )
                self.context.add_tool(name, result.content)
        else:
            final_text = "Limite de iterações de ferramentas atingido."

        self.context.add_assistant(final_text)
        await emit("assistant.message", {"text": final_text})
        await emit("avatar.state", self.emotions.from_text(final_text).to_event_payload())
        return final_text

    # ------------------------------------------------------------------ #
    async def process(self, user_text: str, emit: Emit, mode: str = "chat") -> str:
        if mode == "agent":
            return await self.run_agentic(user_text, emit)
        return await self.stream_reply(user_text, emit)


def build_engine(settings: Settings, llm: LLMBackend) -> AilaEngine:
    """Fábrica: instancia agentes + engine a partir da configuração."""
    from aila.security.audit import AuditLog
    from aila.security.permissions import PermissionManager
    from aila.security.sandbox import PathSandbox

    audit = AuditLog(_resolve(settings.security.audit_log))
    permissions = PermissionManager(settings.security, audit)
    sandbox = PathSandbox(settings.sandbox_path())

    deps = AgentDeps(settings=settings, permissions=permissions, sandbox=sandbox, llm=llm)
    manager = AgentManager(deps)
    engine = AilaEngine(settings, llm, manager)
    # guarda refs úteis para a API (confirmação de permissão, auditoria)
    engine.permissions = permissions  # type: ignore[attr-defined]
    engine.audit = audit  # type: ignore[attr-defined]
    return engine


def _resolve(path_str: str):
    from pathlib import Path

    from aila.core.config import PROJECT_ROOT

    p = Path(path_str)
    return p if p.is_absolute() else PROJECT_ROOT / p
