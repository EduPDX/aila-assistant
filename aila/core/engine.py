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
from aila.database.store import ConversationStore
from aila.llm.base import LLMBackend

log = get_logger("engine")

# emit(event_type, payload) -> None
Emit = Callable[[str, dict[str, Any]], Awaitable[None]]

MAX_TOOL_ITERS = 5


class AilaEngine:
    def __init__(
        self,
        settings: Settings,
        llm: LLMBackend,
        agents: AgentManager,
        store: "ConversationStore | None" = None,
    ) -> None:
        self.settings = settings
        self.llm = llm
        self.agents = agents
        self.store = store
        self.session_id: int | None = None
        self.emotions = EmotionEngine()
        self.context = ConversationContext(
            system_prompt=self._system_prompt(),
            max_turns=settings.context.max_turns,
        )

    # ------------------------------------------------------------------ #
    def _system_prompt(self) -> str:
        base = self.settings.app.persona.strip()
        caps = self.agents.describe_capabilities()
        return (
            f"{base}\n\n{caps}\n\n"
            "Use as ferramentas acima automaticamente quando a tarefa exigir ler, "
            "escrever ou buscar arquivos, ou gerar/analisar/corrigir código. Para "
            "conversa comum, apenas responda. Nunca invente resultados de ferramentas."
        )

    # ------------------------ sessões / persistência ------------------- #
    def ensure_session(self, title: str = "Nova conversa") -> int:
        if self.store is None:
            return -1
        if self.session_id is None:
            self.session_id = self.store.create_session(title)
        return self.session_id

    def new_session(self, title: str = "Nova conversa") -> int:
        self.context.clear()
        self.session_id = None
        return self.ensure_session(title)

    def load_session(self, session_id: int) -> None:
        if self.store is None:
            return
        self.context.clear()
        self.session_id = session_id
        for m in self.store.get_messages(session_id):
            if m["role"] == "user":
                self.context.add_user(m["content"])
            elif m["role"] == "assistant":
                self.context.add_assistant(m["content"])

    def _persist(self, role: str, content: str) -> None:
        if self.store is None or not content:
            return
        self.ensure_session(content[:40] if role == "user" else "Nova conversa")
        self.store.add_message(self.session_id, role, content)

    # ------------------------------------------------------------------ #
    async def process(self, user_text: str, emit: Emit, mode: str = "auto") -> str:
        """Laço unificado, em streaming, com roteamento automático de ferramentas.

        ``mode="auto"`` (padrão): a IA decide sozinha se usa ferramentas.
        ``mode="chat"``: força conversa pura (sem ferramentas), menor latência.
        """
        await emit("avatar.state", self.emotions.thinking().to_event_payload())
        self.context.add_user(user_text)
        self._persist("user", user_text)

        tools = self.agents.registry.schemas() if mode != "chat" else None

        final_text = ""
        for _ in range(MAX_TOOL_ITERS):
            collected: list[str] = []
            tool_calls: list[dict] = []
            async for chunk in self.llm.chat(self.context.build(), stream=True, tools=tools):
                if chunk.content:
                    collected.append(chunk.content)
                    await emit("assistant.token", {"text": chunk.content})
                if chunk.tool_calls:
                    tool_calls = chunk.tool_calls

            text = "".join(collected)

            if not tool_calls:
                final_text = text.strip()
                break

            # turno do assistente que solicitou ferramentas (mantém tool_calls)
            self.context._messages.append(
                Message(role="assistant", content=text, tool_calls=tool_calls)
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
            final_text = final_text or "Limite de iterações de ferramentas atingido."

        self.context.add_assistant(final_text)
        self._persist("assistant", final_text)
        await emit("assistant.message", {"text": final_text})
        await emit("avatar.state", self.emotions.from_text(final_text).to_event_payload())
        return final_text


def build_engine(settings: Settings, llm: LLMBackend) -> AilaEngine:
    """Fábrica: instancia agentes + engine a partir da configuração."""
    from aila.security.audit import AuditLog
    from aila.security.permissions import PermissionManager
    from aila.security.sandbox import PathSandbox

    audit = AuditLog(_resolve(settings.security.audit_log))
    permissions = PermissionManager(settings.security, audit)
    sandbox = PathSandbox(settings.sandbox_path())
    store = ConversationStore()

    deps = AgentDeps(settings=settings, permissions=permissions, sandbox=sandbox, llm=llm)
    manager = AgentManager(deps)
    engine = AilaEngine(settings, llm, manager, store=store)
    # guarda refs úteis para a API (confirmação de permissão, auditoria)
    engine.permissions = permissions  # type: ignore[attr-defined]
    engine.audit = audit  # type: ignore[attr-defined]
    return engine


def _resolve(path_str: str):
    from pathlib import Path

    from aila.core.config import PROJECT_ROOT

    p = Path(path_str)
    return p if p.is_absolute() else PROJECT_ROOT / p
