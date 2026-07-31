"""Speech-to-Text via faster-whisper (roda na GPU com CUDA).

FASE 2. Requer o extra ``voice``::

    pip install -e ".[voice]"

O modelo é carregado sob demanda (lazy) para não ocupar VRAM à toa.
"""

from __future__ import annotations

from pathlib import Path

from aila.core.logging import get_logger

log = get_logger("stt")


class SpeechToText:
    def __init__(self, model_size: str = "base", language: str = "pt", device: str = "cuda"):
        self.model_size = model_size
        self.language = language
        self.device = device
        self._model = None

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                'STT indisponível. Instale: pip install -e ".[voice]"'
            ) from exc
        # compute_type float16 aproveita os Tensor Cores da RTX 4060.
        self._model = WhisperModel(
            self.model_size, device=self.device, compute_type="float16"
        )
        log.info(f"Whisper '{self.model_size}' carregado ({self.device})")

    def transcribe(self, audio_path: str | Path) -> str:
        """Transcreve um arquivo de áudio para texto."""
        self._ensure_model()
        segments, _ = self._model.transcribe(str(audio_path), language=self.language)
        return " ".join(seg.text.strip() for seg in segments).strip()
