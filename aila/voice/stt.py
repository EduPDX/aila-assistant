"""Speech-to-Text via faster-whisper (CTranslate2).

Na RTX 4060 roda em CUDA com float16 (Tensor Cores); cai para CPU/int8 se a
GPU não estiver disponível. O modelo é baixado do HuggingFace na 1ª execução e
carregado sob demanda (lazy) para não ocupar VRAM à toa.

O áudio do navegador (webm/opus) é decodificado pelo PyAV, que o faster-whisper
usa internamente — basta passar o caminho do arquivo.
"""

from __future__ import annotations

from pathlib import Path

from aila.core.logging import get_logger

log = get_logger("stt")


class SpeechToText:
    def __init__(
        self, model_size: str = "base", language: str = "pt", device: str = "auto"
    ) -> None:
        self.model_size = model_size
        self.language = language
        self.device = device
        self._model = None

    def _pick_device(self) -> tuple[str, str]:
        """Retorna (device, compute_type)."""
        if self.device in ("cpu",):
            return "cpu", "int8"
        if self.device in ("cuda",):
            return "cuda", "float16"
        # auto: tenta CUDA, cai para CPU
        try:
            import ctranslate2  # type: ignore

            if ctranslate2.get_cuda_device_count() > 0:
                return "cuda", "float16"
        except Exception:  # noqa: BLE001
            pass
        return "cpu", "int8"

    def _load(self, device: str, compute: str) -> None:
        from faster_whisper import WhisperModel  # type: ignore

        self._model = WhisperModel(self.model_size, device=device, compute_type=compute)
        self._device = device
        log.info(f"Whisper '{self.model_size}' carregado ({device}/{compute})")

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel  # type: ignore  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                'STT indisponível. Instale: pip install -e ".[voice]"'
            ) from exc
        device, compute = self._pick_device()
        self._load(device, compute)

    @property
    def available(self) -> bool:
        try:
            import faster_whisper  # type: ignore  # noqa: F401

            return True
        except Exception:  # noqa: BLE001
            return False

    def transcribe(self, audio_path: str | Path) -> str:
        """Transcreve um arquivo de áudio para texto.

        Se a GPU foi escolhida mas as libs CUDA (cuBLAS/cuDNN) não estão
        disponíveis em runtime, refaz o carregamento em CPU automaticamente.
        """
        self._ensure_model()
        try:
            segments, _ = self._model.transcribe(str(audio_path), language=self.language)
            return " ".join(seg.text.strip() for seg in segments).strip()
        except RuntimeError as exc:
            msg = str(exc).lower()
            cuda_issue = any(k in msg for k in ("cublas", "cudnn", "cuda", "gpu"))
            if getattr(self, "_device", "cpu") == "cuda" and cuda_issue:
                log.warning(f"GPU indisponível em runtime ({exc}); recarregando em CPU")
                self._model = None
                self._load("cpu", "int8")
                segments, _ = self._model.transcribe(str(audio_path), language=self.language)
                return " ".join(seg.text.strip() for seg in segments).strip()
            raise
