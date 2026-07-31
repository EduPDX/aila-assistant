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
    {"type": "permission.request","id": "...", "action": "...", "params": {...}}
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
        self._pending: dict[str, asyncio.Future[bool]] = {}

    async def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        await self.ws.send_json({"type": event_type, **payload})

    async def confirm(self, action: str, params: dict[str, Any]) -> bool:
        """Callback registrado no PermissionManager: pergunta à UI e espera."""
        req_id = uuid.uuid4().hex
        fut: asyncio.Future[bool] = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut
        await self.emit(
            "permission.request", {"id": req_id, "action": action, "params": params}
        )
        try:
            return await asyncio.wait_for(fut, timeout=120)
        except asyncio.TimeoutError:
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

    try:
        while True:
            data = await ws.receive_json()
            mtype = data.get("type")

            if mtype == "user.message":
                text = data.get("text", "").strip()
                mode = data.get("mode", "chat")
                if not text:
                    continue
                try:
                    await engine.process(text, session.emit, mode=mode)
                except Exception as exc:  # noqa: BLE001
                    log.exception("erro ao processar mensagem")
                    await session.emit("error", {"message": str(exc)})

            elif mtype == "permission.response":
                session.resolve_permission(data.get("id", ""), bool(data.get("approved")))

            elif mtype == "session.new":
                engine.new_session()
                await session.emit("session.changed", {"id": engine.session_id})

            elif mtype == "session.load":
                engine.load_session(int(data.get("id")))
                msgs = engine.store.get_messages(engine.session_id) if engine.store else []
                await session.emit("session.loaded", {"id": engine.session_id, "messages": msgs})

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
