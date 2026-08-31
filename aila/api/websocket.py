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

from fastapi import WebSocket, WebSocketDisconnect, status

from aila.core.logging import get_logger
from aila.security.origin import local_origin_allowed

log = get_logger("websocket")


class WSSession:
    """Estado de uma conexão: roteia emissões e confirmações de permissão."""

    def __init__(self, ws: WebSocket, engine: Any) -> None:
        self.ws = ws
        self.engine = engine
        self.session_id: int | None = None
        self.turn_lock = asyncio.Lock()
        # Confirmações são propriedade DESTA conexão. Não sobrevivem a uma
        # reconexão nem podem ser aprovadas por outra aba/origem.
        self._pending: dict[str, asyncio.Future[bool]] = {}

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

    def cancel_permissions(self) -> None:
        for fut in self._pending.values():
            if not fut.done():
                fut.set_result(False)
        self._pending.clear()


def websocket_origin_allowed(ws: WebSocket) -> bool:
    """Bloqueia Cross-Site WebSocket Hijacking.

    Navegadores sempre enviam Origin; clientes locais não-browser podem omitir.
    Quando presente, a origem precisa ser HTTP(S), loopback e usar a mesma porta
    do Host que recebeu a conexão.
    """
    return local_origin_allowed(
        ws.headers.get("origin"),
        ws.headers.get("host", ""),
        getattr(ws.client, "host", None),
    )


async def websocket_endpoint(ws: WebSocket) -> None:
    if not websocket_origin_allowed(ws):
        log.warning("WebSocket recusado: origem não local")
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await ws.accept()
    engine = ws.app.state.engine
    session = WSSession(ws, engine)

    await session.emit("system.status", {"message": "conectado"})

    # Autorrepresentação: as capacidades REAIS (derivadas das ferramentas
    # registradas) são estáticas após o boot → manda UMA vez no connect p/ a UI
    # mostrar "o que a Aila consegue fazer".
    if engine.self_model is not None:
        await session.emit("aila.capabilities",
                           {"items": engine.self_model.state().capabilities})

    # Ao conectar: começar VAZIO (padrão) evita contaminar o modelo com um
    # histórico antigo/confuso; ou retomar a última conversa se configurado.
    # O histórico anterior continua salvo e acessível pela barra lateral.
    async with engine.turn_lock:
        if getattr(engine.settings.app, "fresh_chat_on_start", True):
            session.session_id = engine.new_session()
            await session.emit("session.changed", {"id": session.session_id})
        else:
            resumed = engine.resume_last()
            session.session_id = resumed["id"]
            if resumed["id"] is not None:
                await session.emit(
                    "session.loaded",
                    {"id": resumed["id"], "messages": resumed["messages"], "resumed": True},
                )

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
            # Uma conexão preserva a ordem de seus próprios turnos; a trava da
            # engine impede mistura com outra aba. Antes do turno, restaura o
            # histórico que pertence a esta conexão.
            async with session.turn_lock, engine.turn_lock:
                if session.session_id is not None and engine.session_id != session.session_id:
                    engine.load_session(session.session_id)
                with engine.permissions.confirm_context(session.confirm):
                    await engine.process(text, session.emit, mode=mode)
                session.session_id = engine.session_id
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

            elif mtype == "body.report":
                # Ciclo corpo→mente (Fase D): o avatar relata o estado REAL do
                # corpo; a Aila passa a saber o que está fazendo. Nunca deixa a
                # conexão cair por um relato torto.
                try:
                    body = data.get("body") or {}
                    if isinstance(body, dict) and engine.self_model is not None:
                        from aila.mind.scene import readable_action, readable_target

                        # Fase M: traduz os ids da cena (analysis/panel_memory…) em
                        # nomes naturais, p/ a fala sair "apontando para o gráfico".
                        alvo = readable_target(body.get("interaction_target") or "")
                        gaze = readable_target(body.get("gaze_target") or "")
                        engine.self_model.update_body(
                            posture=body.get("posture"),
                            gesture=body.get("gesture"),
                            hands=body.get("hands"),
                            gaze_target=gaze or (body.get("gaze_target") or ""),
                            interaction_target=alvo,
                            interaction_action=(readable_action(body.get("interaction_action"))
                                                if alvo else ""),
                        )
                        if alvo:                       # a cena vira o FOCO de atenção
                            engine.self_model.update_experience(attention=alvo)
                        from aila.mind.observability import trace as _trace

                        b = engine.self_model.body
                        _trace("BODY", left=b.hands.get("left"), right=b.hands.get("right"),
                               gaze=b.gaze_target, interaction=b.interaction_target)
                        await session.emit("aila.state",
                                           engine.self_model.state().to_event_payload())
                except Exception as exc:  # noqa: BLE001 - relato é informativo
                    log.warning(f"body.report inválido: {exc!r}")

            elif mtype == "permission.response":
                session.resolve_permission(data.get("id", ""), bool(data.get("approved")))

            elif mtype == "session.new":
                async with session.turn_lock, engine.turn_lock:
                    session.session_id = engine.new_session()
                    await session.emit("session.changed", {"id": session.session_id})

            elif mtype == "session.load":
                sid = data.get("id")
                if sid is None:
                    await session.emit("error", {"message": "session.load requer 'id'"})
                else:
                    async with session.turn_lock, engine.turn_lock:
                        session.session_id = int(sid)
                        engine.load_session(session.session_id)
                        msgs = engine.store.get_messages(session.session_id) if engine.store else []
                        await session.emit(
                            "session.loaded", {"id": session.session_id, "messages": msgs}
                        )

            # ---- Plan/Execute ----
            elif mtype == "plan.approve":
                if engine.plan_manager.approve():
                    await session.emit("plan.approved", {"id": engine.plan_manager.active_plan.id if engine.plan_manager.active_plan else ""})
                    # Executa em background
                    async def _run_plan():
                        async def _exec_tool(name, args):
                            return await engine.agents.registry.execute(name, args)
                        plan = engine.plan_manager.active_plan or engine.plan_manager._history[-1]
                        with engine.permissions.confirm_context(session.confirm):
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
        session.cancel_permissions()
        for _et in _FWD:                 # desliga a ponte bus→WS desta conexão
            _bus.unsubscribe(_et, _forward)
        for task in tasks:               # cancela processamentos em voo desta conexão
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
