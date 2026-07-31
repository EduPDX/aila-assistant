"""Entrypoint da Aila: monta o app FastAPI, a engine e serve a UI.

Rodar:
    python -m aila.main
    # ou, após 'pip install -e .':
    aila
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from aila.api.routes import router as api_router
from aila.api.websocket import websocket_endpoint
from aila.core.config import PROJECT_ROOT, get_settings
from aila.core.engine import build_engine
from aila.core.logging import get_logger, setup_logging
from aila.llm.registry import get_backend

UI_DIR = PROJECT_ROOT / "ui"


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
    log.info(f"Aila pronta em http://{settings.host}:{settings.port}")
    log.info(f"Modo somente-leitura: {settings.security.read_only}")

    yield

    await llm.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="Aila", version="0.1.0", lifespan=lifespan)
    app.include_router(api_router)

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):  # noqa: ANN202
        await websocket_endpoint(websocket)

    @app.get("/")
    async def index():  # noqa: ANN202
        return FileResponse(UI_DIR / "index.html")

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
