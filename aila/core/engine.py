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
from collections.abc import Awaitable, Callable
from typing import Any

from aila.agents.base import AgentDeps
from aila.agents.manager import AgentManager
from aila.avatar.emotion_engine import EmotionEngine
from aila.core.config import Settings
from aila.core.context import ConversationContext, Message
from aila.core.logging import get_logger
from aila.database.store import ConversationStore
from aila.llm.base import LLMBackend
from aila.memory.store import MemoryStore

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
        store: ConversationStore | None = None,
        memory: MemoryStore | None = None,
    ) -> None:
        self.settings = settings
        self.llm = llm
        self.agents = agents
        self.store = store
        self.memory = memory
        self.session_id: int | None = None
        self.emotions = EmotionEngine()
        # Canal opcional para um motor 3D (ex.: ponte OSC -> Unreal).
        self.avatar_sink: Callable[[dict[str, Any]], None] | None = None
        self.last_avatar_state: dict[str, Any] | None = None
        # gesto pedido pela IA (AvatarAgent) durante o turno atual
        self.pending_gesture: str | None = None
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

    # --------------------------- avatar -------------------------------- #
    async def _avatar(self, emit: Emit, payload: dict[str, Any]) -> None:
        """Emite o estado do avatar para a UI (WebSocket) e, se houver, para o
        motor 3D (ponte OSC). Guarda o último estado para /api/avatar/current."""
        self.last_avatar_state = payload
        await emit("avatar.state", payload)
        if self.avatar_sink is not None:
            try:
                self.avatar_sink(payload)
            except Exception as exc:  # noqa: BLE001
                log.warning(f"avatar_sink falhou: {exc!r}")

    # -------------------------- memória (RAG) -------------------------- #
    async def _recall(self, query: str, emit: Emit) -> str | None:
        """Recupera memórias relevantes e retorna um bloco de contexto (ou None)."""
        if self.memory is None:
            return None
        cfg = self.settings.memory
        try:
            hits = await self.memory.search(query, top_k=cfg.top_k, min_score=cfg.min_score)
        except Exception as exc:  # noqa: BLE001 - memória nunca deve quebrar o chat
            log.warning(f"recuperação de memória falhou: {exc!r}")
            return None
        if not hits:
            return None
        await emit("memory.recalled", {"items": [{"text": h.text, "score": round(h.score, 2)} for h in hits]})
        linhas = "\n".join(f"- {h.text}" for h in hits)
        return f"Memórias relevantes de conversas anteriores:\n{linhas}"

    async def _remember(self, user_text: str, answer: str) -> None:
        """Grava a troca na memória de longo prazo (best-effort)."""
        if self.memory is None or not self.settings.memory.store_conversations:
            return
        if len(user_text.strip()) < 8:  # ignora saudações triviais
            return
        try:
            await self.memory.add(
                f"Usuário: {user_text}\nAila: {answer}",
                kind="chat",
                session_id=self.session_id,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(f"gravação de memória falhou: {exc!r}")

    def _messages_with_memory(self, mem_block: str | None) -> list[dict]:
        msgs = self.context.build()
        if mem_block:
            # insere logo após o prompt de sistema principal
            msgs.insert(1, {"role": "system", "content": mem_block})
        return msgs

    # ------------------------------------------------------------------ #
    async def process(self, user_text: str, emit: Emit, mode: str = "auto") -> str:
        """Laço unificado, em streaming, com roteamento automático de ferramentas.

        ``mode="auto"`` (padrão): a IA decide sozinha se usa ferramentas.
        ``mode="chat"``: força conversa pura (sem ferramentas), menor latência.
        """
        await self._avatar(emit, self.emotions.thinking().to_event_payload())
        await emit("aila.state", {"status": "THINKING"})

        # Recupera memórias relevantes ANTES de adicionar a mensagem ao contexto.
        mem_block = await self._recall(user_text, emit)

        self.context.add_user(user_text)
        self._persist("user", user_text)

        tools = self.agents.registry.schemas() if mode != "chat" else None

        final_text = ""
        for _ in range(MAX_TOOL_ITERS):
            collected: list[str] = []
            tool_calls: list[dict] = []
            async for chunk in self.llm.chat(
                self._messages_with_memory(mem_block), stream=True, tools=tools
            ):
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
                await emit("aila.state", {"status": _tool_status(name), "tool": name})
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
        await self._remember(user_text, final_text)
        await emit("assistant.message", {"text": final_text})
        await self._avatar(emit, self.emotions.from_text(final_text).to_event_payload())
        # gesto explícito pedido pela IA (via AvatarAgent) tem prioridade
        if self.pending_gesture:
            await emit("avatar.gesture", {"value": self.pending_gesture})
            self.pending_gesture = None
        await emit("aila.state", {"status": "IDLE"})
        return final_text


def _tool_status(tool_name: str) -> str:
    """Mapeia o nome da ferramenta para um estado global da Aila."""
    if tool_name.startswith("code."):
        return "CODING"
    if tool_name.startswith(("vision.", "binary.")):
        return "ANALYZING_IMAGE" if tool_name.startswith("vision.") else "TOOL_RUNNING"
    if tool_name.startswith("file."):
        return "READING_FILE"
    if tool_name.startswith("web.") or tool_name.startswith("memory.search"):
        return "SEARCHING"
    return "TOOL_RUNNING"


def build_engine(settings: Settings, llm: LLMBackend) -> AilaEngine:
    """Fábrica: instancia agentes + engine a partir da configuração."""
    from aila.security.audit import AuditLog
    from aila.security.permissions import PermissionManager
    from aila.security.sandbox import PathSandbox

    audit = AuditLog(_resolve(settings.security.audit_log))
    permissions = PermissionManager(settings.security, audit)
    sandbox = PathSandbox(settings.sandbox_path())
    store = ConversationStore()

    # Memória de longo prazo (RAG): embeddings via o próprio backend de LLM.
    memory: MemoryStore | None = None
    if settings.memory.enabled:
        async def _embed(texts: list[str]) -> list[list[float]]:
            return await llm.embed(texts, model=settings.memory.embed_model)

        memory = MemoryStore(_resolve(settings.memory.db_path), _embed)

    deps = AgentDeps(
        settings=settings, permissions=permissions, sandbox=sandbox, llm=llm, memory=memory
    )
    manager = AgentManager(deps)
    engine = AilaEngine(settings, llm, manager, store=store, memory=memory)
    # o AvatarAgent aciona gestos setando engine.pending_gesture (emitido no turno)
    deps.gesture_sink = lambda g: setattr(engine, "pending_gesture", g)

    # Ponte OSC para um motor 3D (Unreal), quando configurada.
    if settings.avatar.transport in ("osc", "both"):
        try:
            from aila.avatar.osc_bridge import OSCAvatarBridge

            bridge = OSCAvatarBridge(settings.avatar.osc_host, settings.avatar.osc_port)
            engine.avatar_sink = bridge.send
        except Exception as exc:  # noqa: BLE001
            from aila.core.logging import get_logger

            get_logger("engine").warning(
                f"ponte OSC indisponível ({exc!r}). Instale: pip install -e \".[avatar]\""
            )

    # Ponte Unreal via Remote Control (sem plugins extras). Tem precedência.
    av = settings.avatar
    if av.unreal_enabled and av.unreal_mesh_path:
        from aila.avatar.unreal_bridge import UnrealRemoteControlBridge

        engine.avatar_sink = UnrealRemoteControlBridge(
            av.unreal_rc_url, av.unreal_mesh_path, av.unreal_anim_base
        ).send
    # guarda refs úteis para a API (confirmação de permissão, auditoria)
    engine.permissions = permissions  # type: ignore[attr-defined]
    engine.audit = audit  # type: ignore[attr-defined]
    return engine


def _resolve(path_str: str):
    from aila.core.config import data_path

    return data_path(path_str)
