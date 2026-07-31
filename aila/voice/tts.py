"""Text-to-Speech via Piper (rápido, offline) ou XTTS (voz clonável).

FASE 2. Piper é o default por ser leve e roubar pouca VRAM; XTTS entra quando
se quer clonagem de voz e maior naturalidade.

A saída de áudio pode alimentar o lip-sync do avatar (visemes) na fase 4.
"""

from __future__ import annotations

from pathlib import Path

from aila.core.logging import get_logger

log = get_logger("tts")


class TextToSpeech:
    def __init__(self, engine: str = "piper", voice: str = "pt_BR-faber-medium"):
        self.engine = engine
        self.voice = voice

    def synthesize(self, text: str, out_path: str | Path) -> Path:
        """Gera um WAV a partir do texto. Retorna o caminho do arquivo."""
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if self.engine == "piper":
            return self._piper(text, out)
        if self.engine == "xtts":
            return self._xtts(text, out)
        raise ValueError(f"Engine TTS desconhecida: {self.engine}")

    def _piper(self, text: str, out: Path) -> Path:
        try:
            from piper.voice import PiperVoice  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Piper indisponível. Instale 'piper-tts' e baixe uma voz. "
                "Veja docs/ROADMAP.md (Fase 2)."
            ) from exc
        voice = PiperVoice.load(self.voice)
        with open(out, "wb") as fh:
            voice.synthesize(text, fh)
        return out

    def _xtts(self, text: str, out: Path) -> Path:
        raise NotImplementedError(
            "XTTS será integrado na Fase 2 (clonagem de voz). Veja docs/ROADMAP.md."
        )
