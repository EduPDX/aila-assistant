"""Handler de WebSocket: canal bidirecional em tempo real com a UI.

Protocolo (JSON por mensagem):

  Cliente -> Servidor
    {"type": "user.message", "text": "...", "mode": "chat"|"agent"}
    {"type": "permission.response", "id": "...", "approved": true}

  Servidor -> Cliente
    {"type": "assistant.token",  "text": "..."}
    {"type": "assistant.message","text": "..."}
    {"type": "agent.invoked",    "tool": "...", "args": {...}}
    {"type": "agent.result",     "tool": "...", "ok": true, "content": "..."}
    {"type": "avatar.state",     ...AvatarState...}
    {"type": "permission.request","id": "...", "action": "...", "params": {...}, "risk": "review"|"danger"}
    {"type": "error",            "message": "..."}
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from aila.core.logging import get_logger

log = get_logger("websocket")


class WSSession:
    """Estado de uma conexão: roteia emissões e confirmações de permissão."""

    def __init__(self, ws: WebSocket, engine: Any) -> None:
        self.ws = ws
        self.engine = engine

    @property
    def _pending(self) -> dict[str, asyncio.Future[bool]]:
        # registro COMPARTILHADO no engine → sobrevive a reconexões do WebSocket
        return self.engine.perm_pending

    async def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        await self.ws.send_json({"type": event_type, **payload})

    async def confirm(self, action: str, params: dict[str, Any]) -> bool:
        """Callback registrado no PermissionManager: pergunta à UI e espera."""
        req_id = uuid.uuid4().hex
        fut: asyncio.Future[bool] = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut
        # nível de risco (a policy classifica; só REVIEW/DANGER chegam aqui) → UI mostra
        try:
            risk = self.engine.permissions.policy.classify(action)
        except Exception:  # noqa: BLE001 - risco é informativo; nunca deve travar a confirmação
            risk = "review"
        await self.emit(
            "permission.request",
            {"id": req_id, "action": action, "params": params, "risk": risk},
        )
        try:
            return await asyncio.wait_for(fut, timeout=120)
        except TimeoutError:
            return False
        finally:
            self._pending.pop(req_id, None)

    def resolve_permission(self, req_id: str, approved: bool) -> None:
        fut = self._pending.get(req_id)
        if fut and not fut.done():
            fut.set_result(approved)


async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    engine = ws.app.state.engine
    session = WSSession(ws, engine)

    # Liga a confirmação de permissão a ESTA conexão.
    engine.permissions.set_confirm_handler(session.confirm)
    await session.emit("system.status", {"message": "conectado"})

    # Conversa única: ao conectar, retoma a última conversa em vez de vazio.
    resumed = engine.resume_last()
    if resumed["id"] is not None:
        await session.emit("session.loaded",
                           {"id": resumed["id"], "messages": resumed["messages"], "resumed": True})

    # Ponte bus→WS: eventos cognitivos de BACKGROUND (consolidação/grafo/skill)
    # rodam fora do turno (só no event bus) → encaminha p/ a tela em tempo real.
    from aila.core.event_bus import bus as _bus

    _FWD = ("memory.consolidated", "graph.updated", "skill.ran", "system.vram")

    async def _forward(event) -> None:  # noqa: ANN001
        try:
            await session.emit(event.type, event.payload)
        except Exception:  # noqa: BLE001 - conexão pode ter caído
            pass

    for _et in _FWD:
        _bus.subscribe(_et, _forward)

    async def run_message(text: str, mode: str) -> None:
        try:
            await engine.process(text, session.emit, mode=mode)
        except Exception as exc:  # noqa: BLE001
            log.exception("erro ao processar mensagem")
            try:
                await session.emit("error", {"message": str(exc)})
            except Exception:  # noqa: BLE001 - conexão pode ter caído
                pass

    tasks: set[asyncio.Task] = set()
    try:
        while True:
            data = await ws.receive_json()
            mtype = data.get("type")

            if mtype == "user.message":
                text = data.get("text", "").strip()
                mode = data.get("mode", "chat")
                if not text:
                    continue
                # roda em BACKGROUND: o loop precisa continuar recebendo (senão o
                # permission.response que o process() espera nunca chega → deadlock).
                task = asyncio.create_task(run_message(text, mode))
                tasks.add(task)
                task.add_done_callback(tasks.discard)

            elif mtype == "permission.response":
                session.resolve_permission(data.get("id", ""), bool(data.get("approved")))

            elif mtype == "session.new":
                engine.new_session()
                await session.emit("session.changed", {"id": engine.session_id})

            elif mtype == "session.load":
                sid = data.get("id")
                if sid is None:
                    await session.emit("error", {"message": "session.load requer 'id'"})
                else:
                    engine.load_session(int(sid))
                    msgs = engine.store.get_messages(engine.session_id) if engine.store else []
                    await session.emit("session.loaded", {"id": engine.session_id, "messages": msgs})

            # ---- Plan/Execute ----
            elif mtype == "plan.approve":
                if engine.plan_manager.approve():
                    await session.emit("plan.approved", {"id": engine.plan_manager.active_plan.id if engine.plan_manager.active_plan else ""})
                    # Executa em background
                    async def _run_plan():
                        async def _exec_tool(name, args):
                            return await engine.agents.registry.execute(name, args)
                        plan = engine.plan_manager.active_plan or engine.plan_manager._history[-1]
                        await engine.plan_manager.execute(plan, _exec_tool, session.emit)
                    task = asyncio.create_task(_run_plan())
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
                else:
                    await session.emit("error", {"message": "Nenhum plano pendente para aprovar."})

            elif mtype == "plan.reject":
                if engine.plan_manager.reject():
                    await session.emit("plan.rejected", {})
                else:
                    await session.emit("error", {"message": "Nenhum plano pendente para rejeitar."})

            else:
                await session.emit("error", {"message": f"tipo desconhecido: {mtype}"})

    except WebSocketDisconnect:
        log.info("cliente desconectou")
    except Exception as exc:  # noqa: BLE001
        log.exception("erro na websocket")
        try:
            await session.emit("error", {"message": str(exc)})
        except Exception:  # noqa: BLE001
            pass
    finally:
        for _et in _FWD:                 # desliga a ponte bus→WS desta conexão
            _bus.unsubscribe(_et, _forward)
        for task in tasks:               # cancela processamentos em voo desta conexão
            task.cancel()
