"""Entrypoint da Aila: monta o app FastAPI, a engine e serve a UI.

Rodar:
    python -m aila.main
    # ou, após 'pip install -e .':
    aila
"""

from __future__ import annotations

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
        log.info(f"LLM online ({settings.llm.backend}) — modelo: {settings.llm.model}")
    else:
        log.warning(
            f"LLM OFFLINE em {settings.llm.base_url}. "
            f"Inicie o Ollama com 'ollama serve' e baixe um modelo."
        )

    engine = build_engine(settings, llm)
    app.state.settings = settings
    app.state.engine = engine

    # Sistema de voz (STT/TTS). Falha aqui não deve derrubar o app.
    app.state.voice = None
    if settings.voice.enabled:
        try:
            from aila.voice.system import VoiceSystem

            app.state.voice = VoiceSystem(settings.voice)
            log.info(f"Voz habilitada — TTS: {app.state.voice.tts.engine}")
        except Exception as exc:  # noqa: BLE001
            log.warning(f"Sistema de voz indisponível: {exc!r}")

    log.info(f"Aila pronta em http://{settings.host}:{settings.port}")
    log.info(f"Modo somente-leitura: {settings.security.read_only}")

    yield

    await llm.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="Aila", version="0.1.0", lifespan=lifespan)
    app.include_router(api_router)
    app.include_router(voice_router)

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):  # noqa: ANN202
        await websocket_endpoint(websocket)

    @app.get("/")
    async def index():  # noqa: ANN202
        # nova UI (avatar central + drawer de config + temas); index.html antigo
        # continua acessível em /static/index.html
        return FileResponse(UI_DIR / "app.html")

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
    uvicorn.run(
        "aila.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
