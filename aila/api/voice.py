"""Rotas de voz: transcrição (STT), síntese (TTS) e status.

    POST /api/voice/transcribe   (multipart: file=áudio)   -> {"text": "..."}
    POST /api/voice/speak        (json: {"text": "..."})   -> audio/wav
    GET  /api/voice/status                                 -> {...}
"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from aila.core.logging import get_logger

log = get_logger("voice_api")
router = APIRouter(prefix="/api/voice")


class SpeakBody(BaseModel):
    text: str


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
        raise HTTPException(status_code=500, detail=f"Falha na transcrição: {exc}")
    return JSONResponse({"text": text})


@router.post("/speak")
async def speak(request: Request, body: SpeakBody) -> FileResponse:
    voice = _voice(request)
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Texto vazio.")
    try:
        wav = voice.speak_to_file(text)
    except Exception as exc:  # noqa: BLE001
        log.exception("falha na síntese")
        raise HTTPException(status_code=500, detail=f"Falha na síntese: {exc}")
    return FileResponse(str(wav), media_type="audio/wav", filename="aila.wav")
