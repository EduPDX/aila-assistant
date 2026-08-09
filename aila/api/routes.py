"""Rotas REST: status, modelos, auditoria, configuração."""

from __future__ import annotations

import time

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/api")

_IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


@router.get("/status")
async def status(request: Request) -> dict:
    engine = request.app.state.engine
    llm = engine.llm
    return {
        "app": engine.settings.app.name,
        "llm_backend": engine.settings.llm.backend,
        "llm_online": await llm.health(),
        "model": getattr(engine.llm, "default_model", engine.settings.llm.model),
        "read_only": engine.settings.security.read_only,
        "network_mode": engine.network.mode if engine.network else "hybrid",
        "providers": list(engine.router.providers.keys()),   # local + externos habilitados
        "agents": list(engine.agents.agents.keys()),
        "memory_count": engine.memory.count() if engine.memory else 0,
        "agent_state": getattr(request.app.state, "events", None).state
        if getattr(request.app.state, "events", None) else "IDLE",
    }


@router.get("/events")
async def events(request: Request, n: int = 40) -> dict:
    """Atividade recente do agente (via Event Bus) — observabilidade/debug."""
    tracker = getattr(request.app.state, "events", None)
    if tracker is None:
        return {"events": [], "state": "IDLE"}
    return {"events": tracker.events(n), "state": tracker.state, "provider": tracker.provider}


class NetworkBody(BaseModel):
    mode: str   # "offline" | "hybrid"


@router.post("/network")
async def set_network(request: Request, body: NetworkBody) -> dict:
    """Troca o modo de rede em tempo de execução (offline/híbrido)."""
    engine = request.app.state.engine
    if engine.network is None:
        raise HTTPException(status_code=503, detail="Política de rede indisponível.")
    mode = engine.network.set_mode(body.mode)
    return {"network_mode": mode}


@router.get("/metrics")
async def metrics(request: Request) -> dict:
    """Métricas reais do sistema (CPU/RAM/GPU/VRAM/tokens-s/uptime) para o painel."""
    from aila.core.metrics import collect

    return collect(request.app.state.engine)


@router.get("/models")
async def models(request: Request) -> dict:
    engine = request.app.state.engine
    return {"models": await engine.llm.list_models()}


@router.get("/audit")
async def audit(request: Request, n: int = 50) -> dict:
    engine = request.app.state.engine
    return {"entries": engine.audit.tail(n)}


@router.get("/tools")
async def tools(request: Request) -> dict:
    engine = request.app.state.engine
    return {
        "tools": [
            {"name": t.name, "agent": t.agent, "description": t.description}
            for t in engine.agents.registry.all()
        ]
    }


@router.get("/sessions")
async def sessions(request: Request) -> dict:
    engine = request.app.state.engine
    if engine.store is None:
        return {"sessions": []}
    return {"sessions": engine.store.list_sessions(), "current": engine.session_id}


@router.get("/sessions/{session_id}")
async def session_messages(request: Request, session_id: int) -> dict:
    engine = request.app.state.engine
    if engine.store is None:
        return {"messages": []}
    return {"messages": engine.store.get_messages(session_id)}


class RenameBody(BaseModel):
    title: str


@router.patch("/sessions/{session_id}")
async def rename_session(request: Request, session_id: int, body: RenameBody) -> dict:
    engine = request.app.state.engine
    if engine.store is not None:
        engine.store.rename_session(session_id, body.title)
    return {"ok": True}


@router.delete("/sessions/{session_id}")
async def delete_session(request: Request, session_id: int) -> dict:
    engine = request.app.state.engine
    if engine.store is not None:
        engine.store.delete_session(session_id)
        if getattr(engine, "session_id", None) == session_id:
            engine.session_id = None  # a sessão ativa foi apagada
    return {"ok": True}


@router.post("/upload")
async def upload(request: Request, file: UploadFile = File(...)) -> dict:
    """Salva uma imagem no workspace e retorna o caminho relativo (para o Vision Agent)."""
    engine = request.app.state.engine
    sandbox = engine.agents.deps.sandbox
    ext = ("." + (file.filename or "img.png").rsplit(".", 1)[-1]).lower()
    if ext not in _IMG_EXT:
        raise HTTPException(status_code=400, detail=f"Extensão não suportada: {ext}")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    rel = f"uploads/{int(time.time())}{ext}"
    dest = sandbox.resolve(rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return {"path": rel, "bytes": len(data)}


@router.get("/avatar/current")
async def avatar_current(request: Request) -> dict:
    """Último estado do avatar (para polling HTTP ou depuração da ponte 3D)."""
    engine = request.app.state.engine
    return {
        "state": engine.last_avatar_state,
        "transport": engine.settings.avatar.transport,
        "osc": f"{engine.settings.avatar.osc_host}:{engine.settings.avatar.osc_port}",
    }


@router.post("/upload/file")
async def upload_file(request: Request, file: UploadFile = File(...)) -> dict:
    """Salva um arquivo anexado no workspace (para a Aila ler/analisar).

    Se for texto pequeno, devolve o conteúdo para incluir direto na conversa.
    """
    from pathlib import Path as _Path

    engine = request.app.state.engine
    sandbox = engine.agents.deps.sandbox
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    name = _Path(file.filename or "arquivo").name  # sem diretórios (anti-traversal)
    rel = f"uploads/{name}"
    dest = sandbox.resolve(rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    text = None
    if len(data) <= 100_000:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = None
    return {"path": rel, "name": name, "bytes": len(data), "text": text}


@router.post("/avatar/vrm")
async def upload_vrm(request: Request, file: UploadFile = File(...)) -> dict:
    """Salva um modelo VRM escolhido pelo usuário como o avatar padrão."""
    from aila.core.config import DATA_ROOT

    if not (file.filename or "").lower().endswith(".vrm"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .vrm")
    data = await file.read()
    if len(data) < 1000:
        raise HTTPException(status_code=400, detail="Arquivo VRM inválido.")
    dest = DATA_ROOT / "ui" / "models" / "avatar.vrm"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return {"ok": True, "bytes": len(data), "name": file.filename}


@router.post("/avatar/test")
async def avatar_test(request: Request, emotion: str = "happy", gesture: str = "none") -> dict:
    """Define manualmente o estado do avatar — para testar o receptor 3D sem chat.

    Ex.: POST /api/avatar/test?emotion=confused&gesture=shrug
    """
    from aila.avatar.protocol import AvatarState, Emotion, Gesture

    engine = request.app.state.engine
    # tolera valores inválidos vindos da query (cai para o default)
    emo = emotion if emotion in set(Emotion) else "neutral"
    ges = gesture if gesture in set(Gesture) else "none"
    state = AvatarState(
        emotion=emo,
        gesture=ges,
        animation="talking",
        speech_state="talking",
        intensity=0.85,
        text=f"teste: {emo}",
    ).to_event_payload()
    engine.last_avatar_state = state
    if engine.avatar_sink is not None:
        engine.avatar_sink(state)
    return {"ok": True, "state": state}


@router.get("/memory")
async def memory(request: Request, n: int = 20) -> dict:
    engine = request.app.state.engine
    if engine.memory is None:
        return {"enabled": False, "count": 0, "recent": []}
    return {
        "enabled": True,
        "count": engine.memory.count(),
        "recent": engine.memory.recent(n),
    }
