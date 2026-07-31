"""Rotas REST: status, modelos, auditoria, configuração."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api")


@router.get("/status")
async def status(request: Request) -> dict:
    engine = request.app.state.engine
    llm = engine.llm
    return {
        "app": engine.settings.app.name,
        "llm_backend": engine.settings.llm.backend,
        "llm_online": await llm.health(),
        "model": engine.settings.llm.model,
        "read_only": engine.settings.security.read_only,
        "agents": list(engine.agents.agents.keys()),
        "memory_count": engine.memory.count() if engine.memory else 0,
    }


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
