"""Rotas de voz: transcrição (STT), síntese (TTS) e status.

    POST /api/voice/transcribe   (multipart: file=áudio)   -> {"text": "..."}
    POST /api/voice/speak        (json: {"text": "..."})   -> audio/wav
    GET  /api/voice/status                                 -> {...}
"""

from __future__ import annotations

import re

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from aila.core.logging import get_logger

log = get_logger("voice_api")
router = APIRouter(prefix="/api/voice")


class SpeakBody(BaseModel):
    text: str


def speech_text(raw: str) -> str:
    """Limpa o texto para NÃO ler código/markdown em voz alta.

    Remove blocos de código (a Aila não deve falar o código nem os '#'),
    marcações de markdown, links e URLs — deixando só a prosa.
    """
    t = raw or ""
    t = re.sub(r"```[\s\S]*?```", " ", t)              # blocos de código: fora
    t = re.sub(r"`([^`]*)`", r"\1", t)                 # código inline: mantém a palavra
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)     # [texto](url) -> texto
    t = re.sub(r"https?://\S+", " ", t)                # URLs cruas: fora
    t = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", t)        # títulos #
    t = re.sub(r"(?m)^\s*[-*+]\s+", "", t)             # marcadores de lista
    t = re.sub(r"(?m)^\s*\d+\.\s+", "", t)             # listas numeradas
    t = re.sub(r"[*_>#`|]", "", t)                     # ênfase/símbolos soltos
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n\s*\n+", "\n\n", t)
    return t.strip()


def _voice(request: Request):
    voice = getattr(request.app.state, "voice", None)
    if voice is None or not voice.cfg.enabled:
        raise HTTPException(status_code=503, detail="Sistema de voz desabilitado.")
    return voice


@router.get("/status")
async def status(request: Request) -> dict:
    voice = getattr(request.app.state, "voice", None)
    if voice is None:
        return {"enabled": False}
    return voice.status()


@router.post("/transcribe")
async def transcribe(request: Request, file: UploadFile = File(...)) -> JSONResponse:
    voice = _voice(request)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Áudio vazio.")
    suffix = "." + (file.filename or "audio.webm").rsplit(".", 1)[-1]
    try:
        text = voice.transcribe_bytes(data, suffix=suffix)
    except Exception as exc:  # noqa: BLE001
        log.exception("falha na transcrição")
        raise HTTPException(status_code=500, detail=f"Falha na transcrição: {exc}") from exc
    return JSONResponse({"text": text})


@router.post("/speak")
async def speak(request: Request, body: SpeakBody) -> FileResponse:
    voice = _voice(request)
    text = speech_text(body.text)   # remove código/markdown antes de falar
    if not text:
        raise HTTPException(status_code=400, detail="Texto vazio.")
    try:
        audio = voice.speak_to_file(text)
    except Exception as exc:  # noqa: BLE001
        log.exception("falha na síntese")
        raise HTTPException(status_code=500, detail=f"Falha na síntese: {exc}") from exc
    is_mp3 = str(audio).lower().endswith(".mp3")
    media = "audio/mpeg" if is_mp3 else "audio/wav"
    return FileResponse(str(audio), media_type=media, filename="aila." + ("mp3" if is_mp3 else "wav"))
