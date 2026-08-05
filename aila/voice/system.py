"""VoiceSystem — orquestra entrada (STT) e saída (TTS) de voz."""

from __future__ import annotations

import tempfile
from pathlib import Path

from aila.core.config import DATA_ROOT, VoiceConfig
from aila.core.logging import get_logger
from aila.voice.stt import SpeechToText
from aila.voice.tts import TextToSpeech

log = get_logger("voice")

_OUT_DIR = DATA_ROOT / "data" / "voice"


class VoiceSystem:
    def __init__(self, cfg: VoiceConfig) -> None:
        self.cfg = cfg
        self.stt = SpeechToText(
            model_size=cfg.stt.model, language=cfg.stt.language, device=cfg.stt.device
        )
        self.tts = TextToSpeech(
            engine=cfg.tts.engine,
            voice=cfg.tts.voice,
            rate=cfg.tts.rate,
            edge_pitch=cfg.tts.edge_pitch,
            edge_rate=cfg.tts.edge_rate,
        )
        _OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    def transcribe_bytes(self, data: bytes, suffix: str = ".webm") -> str:
        """Salva o áudio recebido e o transcreve."""
        with tempfile.NamedTemporaryFile("wb", suffix=suffix, delete=False) as tf:
            tf.write(data)
            path = tf.name
        try:
            return self.stt.transcribe(path)
        finally:
            Path(path).unlink(missing_ok=True)

    def speak_to_file(self, text: str) -> Path:
        """Sintetiza ``text`` em áudio e retorna o caminho REAL do arquivo
        (pode ser .wav ou .mp3, dependendo do engine/PyAV)."""
        import hashlib

        key = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
        wav, mp3 = _OUT_DIR / f"{key}.wav", _OUT_DIR / f"{key}.mp3"
        if wav.exists():
            return wav
        if mp3.exists():
            return mp3
        return self.tts.synthesize(text, wav)  # devolve o caminho de fato gerado

    def status(self) -> dict:
        return {
            "enabled": self.cfg.enabled,
            "stt_available": self.stt.available,
            "stt_model": self.cfg.stt.model,
            "tts_engine": self.tts.engine,
            "tts_voice": self.cfg.tts.voice or "auto",
            "output_enabled": self.cfg.tts.output_enabled,
        }
