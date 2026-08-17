"""Rotas REST: status, modelos, auditoria, configuração."""

from __future__ import annotations

import time

from fastapi import APIRouter, Body, File, HTTPException, Request, UploadFile
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
        "autonomy_level": engine.permissions.policy.autonomy,
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


@router.get("/cognition")
async def cognition(request: Request, n: int = 20) -> dict:
    """Feed do "subconsciente": atividade cognitiva recente (memória/grafo/
    guardrail/skill) + totais. Só metadados. Base p/ o mini-subconsciente e a aba 🧠."""
    tracker = getattr(request.app.state, "events", None)
    if tracker is None:
        return {"totals": {}, "recent": []}
    return tracker.cognitive_summary(n)


@router.get("/graph")
async def graph(kind: str = "code", limit: int = 1500) -> dict:
    """Grafo do subconsciente p/ visualização: nós + arestas + comunidades.
    kind=code (Code Graph real da Aila) | knowledge (aprendido das conversas).
    Construído sob demanda; só metadados estruturais."""
    from aila.cognition.graph.service import get_service

    k = "knowledge" if kind == "knowledge" else "code"
    try:
        return get_service().view(k, max(1, min(limit, 4000)))
    except Exception as exc:  # noqa: BLE001 - a UI degrada com grafo vazio
        return {"kind": k, "nodes": [], "edges": [], "communities": [], "error": str(exc)}


class TaskBody(BaseModel):
    goal: str


@router.post("/tasks")
async def create_task(request: Request, body: TaskBody) -> dict:
    """Cria e executa (em background) uma tarefa autônoma. Exige autonomia L4."""
    from aila.security.permissions import PermissionDenied

    engine = request.app.state.engine
    if not body.goal.strip():
        raise HTTPException(status_code=400, detail="Objetivo vazio.")
    try:
        task = await engine.start_task(body.goal)
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return task.to_dict()


@router.post("/dev-task")
async def create_dev_task(request: Request, body: TaskBody) -> dict:
    """SELF-IMPROVEMENT: a Aila trabalha no próprio código (branch de backup,
    valida com testes). Exige autonomia L5."""
    from aila.security.permissions import PermissionDenied

    engine = request.app.state.engine
    if not body.goal.strip():
        raise HTTPException(status_code=400, detail="Objetivo vazio.")
    try:
        task = await engine.start_dev_task(body.goal)
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return task.to_dict()


@router.get("/tasks")
async def list_tasks(request: Request) -> dict:
    return {"tasks": [t.to_dict() for t in request.app.state.engine.tasks.list()]}


@router.get("/tasks/{task_id}")
async def get_task(request: Request, task_id: str) -> dict:
    task = request.app.state.engine.tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    return task.to_dict()


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(request: Request, task_id: str) -> dict:
    ok = await request.app.state.engine.tasks.cancel(task_id)
    return {"cancelled": ok}


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


def _redacted_config() -> dict:
    """Config EFETIVA como dict, com as chaves de API removidas (só has_key)."""
    from aila.core.config import get_settings

    s = get_settings().model_dump()
    for cfg in (s.get("providers") or {}).values():
        if isinstance(cfg, dict) and "api_key" in cfg:
            cfg["has_key"] = bool(cfg.get("api_key"))
            cfg["api_key"] = ""
    return s


@router.get("/config")
async def get_config() -> dict:
    """Configuração efetiva (para a tela de Configurações). Chaves de API redigidas."""
    return _redacted_config()


@router.patch("/config")
async def patch_config(body: dict = Body(...)) -> dict:  # noqa: B008
    """Grava um patch (parcial, aninhado) no local.yaml e recarrega a config.
    A maioria dos ajustes só entra em vigor ao REINICIAR (são lidos no boot);
    autonomia/rede têm endpoints próprios que aplicam na hora."""
    from aila.core.config import get_settings, update_local_yaml

    if not isinstance(body, dict) or not body:
        raise HTTPException(status_code=400, detail="Corpo vazio ou inválido.")
    update_local_yaml(body)
    get_settings.cache_clear()          # próxima leitura pega o novo valor
    return {"ok": True, "restart_recommended": True, "config": _redacted_config()}


class AutonomyBody(BaseModel):
    level: int   # 1..5


@router.post("/autonomy")
async def set_autonomy(request: Request, body: AutonomyBody) -> dict:
    """Troca o nível de autonomia (1..5) em tempo de execução."""
    engine = request.app.state.engine
    engine.settings.security.autonomy_level = max(1, min(5, body.level))
    lvl = engine.permissions.policy.autonomy
    return {"autonomy_level": lvl}


_PROVIDER_LABELS = {"openai": "OpenAI", "gemini": "Gemini",
                    "grok": "Grok (xAI)", "deepseek": "DeepSeek", "nvidia": "NVIDIA"}


def _providers_snapshot(engine) -> dict:
    """Estado dos provedores (NUNCA devolve a api_key — só has_key)."""
    from aila.llm.openai_compat import PROVIDER_DEFAULTS

    s = engine.settings
    routing = s.routing
    local_pref = (not routing.enabled) or routing.default in ("local", "default")
    provs = [{
        "name": "local", "label": f"Local · {s.llm.model}", "kind": "local",
        "has_key": True, "enabled": True, "active": True, "preferred": local_pref,
    }]
    for name, cfg in s.providers.items():
        d = PROVIDER_DEFAULTS.get(name, {})
        provs.append({
            "name": name, "label": _PROVIDER_LABELS.get(name, name), "kind": "cloud",
            "model": cfg.model or d.get("model", ""),
            "vision": bool(cfg.vision or d.get("vision", False)),
            "has_key": bool(cfg.api_key),
            "enabled": bool(cfg.enabled and cfg.api_key),
            "preferred": bool(routing.enabled and routing.default == name),
            "active": name in engine.router.providers,
        })
    return {"providers": provs, "routing_enabled": routing.enabled,
            "routing_default": routing.default, "network_mode": engine.network.mode
            if engine.network else "hybrid"}


@router.get("/providers")
async def list_providers(request: Request) -> dict:
    """Provedores de LLM (local + nuvem) e qual é o preferido. Sem expor chaves."""
    return _providers_snapshot(request.app.state.engine)


class ProviderBody(BaseModel):
    name: str
    api_key: str | None = None   # nova chave (None = mantém a atual)
    enabled: bool = True         # ativar/desativar o provedor
    preferred: bool = True       # usar como modelo preferido (roteia p/ ele)
    clear_key: bool = False      # remover a chave salva


@router.post("/providers")
async def set_provider(request: Request, body: ProviderBody) -> dict:
    """Salva/ativa/desativa um provedor de LLM em runtime e persiste no local.yaml
    (gravável, gitignored). A chave nunca é logada nem devolvida."""
    from aila.core.config import update_local_yaml
    from aila.llm.openai_compat import build_external_providers

    engine = request.app.state.engine
    s = engine.settings
    verified: bool | None = None

    if body.name == "local":
        s.routing.enabled = False              # preferir o local = desliga roteamento p/ nuvem
        s.routing.default = "local"
    elif body.name in _PROVIDER_LABELS:
        cfg = getattr(s.providers, body.name)
        if body.clear_key:
            cfg.api_key = ""
        elif body.api_key is not None and body.api_key.strip():
            cfg.api_key = body.api_key.strip()
        cfg.enabled = bool(body.enabled and cfg.api_key)
        if cfg.enabled and body.preferred:
            s.routing.enabled = True
            s.routing.default = body.name
        elif not cfg.enabled and s.routing.default == body.name:
            s.routing.enabled = False
            s.routing.default = "local"
    else:
        raise HTTPException(status_code=400, detail=f"provedor desconhecido: {body.name}")

    # aplica AO VIVO (reconstrói os provedores externos do router)
    externals = build_external_providers(s, engine.network)
    engine.router.providers = {engine.router.default.name: engine.router.default, **externals}
    engine.router.config = s.routing

    # valida a chave (best-effort) quando um provedor de nuvem foi ativado
    if body.name != "local" and body.name in externals:
        try:
            verified = await externals[body.name].health()
        except Exception:  # noqa: BLE001 - verificação é informativa
            verified = False

    # persiste (chaves ficam só no local.yaml gravável, nunca no repositório)
    update_local_yaml({
        "providers": {n: {"enabled": bool(c.enabled), "api_key": c.api_key or "",
                          "model": c.model or ""} for n, c in s.providers.items()},
        "routing": {"enabled": bool(s.routing.enabled), "default": s.routing.default},
    })
    snap = _providers_snapshot(engine)
    snap["verified"] = verified
    return snap


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


@router.delete("/memory/{mem_id}")
async def delete_memory(request: Request, mem_id: int) -> dict:
    """Esquece uma memória específica (controle direto pela UI de Configurações)."""
    engine = request.app.state.engine
    if engine.memory is None:
        raise HTTPException(status_code=404, detail="Memória desativada.")
    engine.memory.delete(mem_id)
    return {"ok": True, "count": engine.memory.count()}


@router.post("/reset")
async def reset(request: Request) -> dict:
    """Apaga TODO o histórico interno — memória de longo prazo, grafo de
    Conhecimento e conversas — para recomeçar do zero. NÃO afeta o código da
    Aila nem o grafo de Código."""
    engine = request.app.state.engine
    if engine.memory is not None:
        engine.memory.clear()
    kg = getattr(engine, "kgraph", None)
    if kg is not None:
        kg.conn.execute("DELETE FROM kg_edge")
        kg.conn.execute("DELETE FROM kg_node")
        kg.conn.commit()
        kg._loaded = False
    if engine.store is not None:
        for s in engine.store.list_sessions():
            engine.store.delete_session(s["id"])
    engine.session_id = None
    engine.context.clear()
    return {"ok": True}
