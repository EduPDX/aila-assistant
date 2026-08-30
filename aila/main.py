"""Entrypoint da Aila: monta o app FastAPI, a engine e serve a UI.

Rodar:
    python -m aila.main
    # ou, após 'pip install -e .':
    aila
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from aila.api.routes import router as api_router
from aila.api.voice import router as voice_router
from aila.api.websocket import websocket_endpoint
from aila.core.config import DATA_ROOT, PROJECT_ROOT, get_settings
from aila.core.engine import build_engine
from aila.core.logging import get_logger, setup_logging
from aila.llm.registry import get_backend

UI_DIR = PROJECT_ROOT / "ui"             # leitura (no bundle, quando empacotado)
MODELS_DIR = DATA_ROOT / "ui" / "models"  # gravável (VRM escolhido pelo usuário)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    log = get_logger("main")

    llm = get_backend(settings.llm)
    online = await llm.health()
    if online:
        # Se o modelo configurado não estiver baixado, usa um disponível
        # (evita o 404 do Ollama). Ignora modelos de embedding para o chat.
        models = await llm.list_models()
        if models and settings.llm.model not in models and hasattr(llm, "default_model"):
            chat_models = [m for m in models if "embed" not in m.lower()] or models
            llm.default_model = chat_models[0]
            log.warning(
                f"Modelo '{settings.llm.model}' não está no Ollama; usando "
                f"'{llm.default_model}'. Para o recomendado: ollama pull {settings.llm.model}"
            )
        eff = getattr(llm, "default_model", settings.llm.model)
        log.info(f"LLM online ({settings.llm.backend}) — modelo: {eff}")
    else:
        log.warning(
            f"LLM OFFLINE em {settings.llm.base_url}. "
            f"Inicie o Ollama com 'ollama serve' e baixe um modelo."
        )

    # Política de rede (offline/híbrido): compartilhada entre engine e voz.
    from aila.security.network_policy import NetworkPolicy

    network = NetworkPolicy(settings.network.mode)
    engine = build_engine(settings, llm, network=network)
    app.state.settings = settings
    app.state.engine = engine
    app.state.network = network

    # Planejador de VRAM (Fase 1: só medir/mostrar). Trata os 8 GB da GPU como
    # orçamento explícito — o "memory plan" impresso no boot, à la kimi-k3-in-c.
    from aila.core.vram import VramPlanner

    app.state.vram = VramPlanner(settings.llm.base_url)

    async def _vram_plan() -> None:
        with contextlib.suppress(Exception):
            p = await app.state.vram.measure()
            if p.available:
                log.info(
                    f"plano de VRAM: {p.used_mb}/{p.total_mb} MB usados · "
                    f"livre {p.free_mb} MB · estado {p.state}"
                    + (f" · Ollama {p.models_mb} MB" if p.models_mb else "")
                )
            else:
                log.info("plano de VRAM: nvidia-smi indisponível (medidor desligado)")
    asyncio.create_task(_vram_plan())

    # Warm-up (NÃO bloqueia o boot): pré-carrega o modelo de chat E o de
    # embeddings no Ollama. Sem isso, a PRIMEIRA mensagem paga o cold-start dos
    # DOIS (a recuperação de memória carrega o embed antes da resposta) — daí a
    # 1ª pergunta ser lenta e as seguintes rápidas (keep_alive as mantém quentes).
    if online:
        async def _warmup() -> None:
            eff = getattr(llm, "default_model", settings.llm.model)
            with contextlib.suppress(Exception):
                async for _ in llm.chat([{"role": "user", "content": "oi"}],
                                        stream=True, max_tokens=1):
                    pass
            if settings.memory.enabled:
                with contextlib.suppress(Exception):
                    await llm.embed(["aquecimento"], model=settings.memory.embed_model)
            log.info(f"warm-up concluído (chat: {eff} · embed: {settings.memory.embed_model})")
        asyncio.create_task(_warmup())

    # Benchmark da escada de modelos (R12) no boot: background + cache. Só mede de
    # fato se o cache estiver velho/desatualizado e a VRAM não estiver apertada —
    # então não pesa a cada run.bat. A aba Recursos lê o resultado guardado.
    if online and settings.llm.benchmark_on_boot:
        async def _boot_bench() -> None:
            with contextlib.suppress(Exception):
                from aila.core.benchmark import boot_benchmark

                await boot_benchmark(
                    llm, settings, max_age_days=settings.llm.benchmark_max_age_days)
        asyncio.create_task(_boot_bench())

    # Event Bus como backbone: logging estruturado + tracker de estado/atividade.
    from aila.core.event_bus import bus as event_bus
    from aila.core.observability import attach_observability

    app.state.events = attach_observability(event_bus)

    # Sistema de voz (STT/TTS). Falha aqui não deve derrubar o app.
    app.state.voice = None
    if settings.voice.enabled:
        try:
            from aila.voice.system import VoiceSystem

            app.state.voice = VoiceSystem(settings.voice, network=network)
            log.info(f"Voz habilitada — TTS: {app.state.voice.tts.engine}")
        except Exception as exc:  # noqa: BLE001
            log.warning(f"Sistema de voz indisponível: {exc!r}")

    log.info(f"Aila pronta em http://{settings.host}:{settings.port}")
    # Servidores MCP externos (opt-in, offline-safe): registra as tools deles no
    # mesmo registry — cada uma passando por authorize(). Falha não derruba o app.
    app.state.mcp = None
    if settings.mcp.enabled:
        from aila.tools.mcp_adapter import connect_and_register

        try:
            app.state.mcp = await connect_and_register(
                settings.mcp, engine.agents.registry, engine.permissions)
        except Exception as exc:  # noqa: BLE001
            log.warning(f"MCP indisponível: {exc!r}")

    log.info(f"Modo de rede: {network.mode} · somente-leitura: {settings.security.read_only}")

    yield

    if app.state.mcp is not None:
        await app.state.mcp.close_all()
    await llm.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="Aila", version="0.1.0", lifespan=lifespan)
    app.include_router(api_router)
    app.include_router(voice_router)

    @app.middleware("http")
    async def _no_cache_ui(request, call_next):  # noqa: ANN001, ANN202
        # A UI (HTML/JS/CSS) NÃO pode ser cacheada de forma "esperta" pelo
        # Chromium do Electron, senão após um update ele serve os módulos ES
        # antigos. Força revalidação (ETag do StaticFiles cuida do 304).
        resp = await call_next(request)
        p = request.url.path
        if p == "/" or p.startswith("/static"):
            resp.headers["Cache-Control"] = "no-cache, must-revalidate"
        return resp

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):  # noqa: ANN202
        await websocket_endpoint(websocket)

    @app.get("/")
    async def index():  # noqa: ANN202
        # UI modular (avatar central + sidebar + painel de status + config/temas)
        return FileResponse(UI_DIR / "app.html", headers={"Cache-Control": "no-cache"})

    # modelos VRM ficam numa pasta gravável; na 1ª execução copia o VRM padrão
    # do bundle. O mount específico vem ANTES do /static geral (precedência).
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    default_vrm = MODELS_DIR / "avatar.vrm"
    bundled_vrm = UI_DIR / "models" / "avatar.vrm"
    if not default_vrm.exists() and bundled_vrm.exists() and bundled_vrm != default_vrm:
        try:
            import shutil

            shutil.copyfile(bundled_vrm, default_vrm)
        except OSError:
            pass
    app.mount("/static/models", StaticFiles(directory=str(MODELS_DIR)), name="models")
    if UI_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    # AILA_RELOAD=1 → reinicia o backend sozinho ao editar um .py (modo fonte/dev;
    # a própria Aila se auto-modificando é refletida na hora). Só observa 'aila/'.
    reload = os.environ.get("AILA_RELOAD") == "1"
    uvicorn.run(
        "aila.main:app",
        host=settings.host,
        port=settings.port,
        reload=reload,
        reload_dirs=["aila"] if reload else None,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
