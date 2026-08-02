"""Text-to-Speech: a Aila fala.

Engines:
    - **sapi**  : síntese nativa do Windows (System.Speech via PowerShell).
                  Zero dependências, offline, com voz pt-BR (ex.: "Microsoft
                  Maria"). É o padrão garantido para a Aila falar de imediato.
    - **piper** : vozes neurais de alta qualidade (offline). Requer o pacote
                  `piper-tts` + um modelo de voz baixado.
    - **auto**  : usa Piper se disponível, senão SAPI.

Todas as engines produzem um arquivo WAV, consumido pela UI (ou pelo lip-sync
do avatar na Fase 4).
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from aila.core.logging import get_logger

log = get_logger("tts")


def _piper_available() -> bool:
    try:
        import piper  # type: ignore  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


class TextToSpeech:
    def __init__(self, engine: str = "auto", voice: str = "", rate: int = 0) -> None:
        self.voice = voice
        self.rate = rate
        if engine == "auto":
            engine = "piper" if _piper_available() else "sapi"
        self.engine = engine
        log.info(f"TTS engine: {self.engine} (voz: {voice or 'auto'})")

    # ------------------------------------------------------------------ #
    def synthesize(self, text: str, out_path: str | Path) -> Path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        text = (text or "").strip()
        if not text:
            raise ValueError("texto vazio para síntese")
        if self.engine == "piper":
            return self._piper(text, out)
        return self._sapi(text, out)

    # ----------------------------- SAPI ------------------------------- #
    def _sapi(self, text: str, out: Path) -> Path:
        """Windows System.Speech. Texto passado por arquivo (sem injeção)."""
        tf = tempfile.NamedTemporaryFile(
            "w", suffix=".txt", delete=False, encoding="utf-8"
        )
        tf.write(text)
        tf.close()
        voice = self.voice.replace("'", "")  # nome de voz é confiável (config)
        select = (
            f"try {{ $s.SelectVoice('{voice}') }} catch {{}}"
            if voice
            else (
                "$pt = $s.GetInstalledVoices() | "
                "Where-Object { $_.VoiceInfo.Culture.Name -like 'pt*' } | "
                "Select-Object -First 1; "
                "if ($pt) { $s.SelectVoice($pt.VoiceInfo.Name) }"
            )
        )
        script = (
            "$ErrorActionPreference='Stop';"
            "Add-Type -AssemblyName System.Speech;"
            f"$t = Get-Content -Raw -Encoding UTF8 -LiteralPath '{tf.name}';"
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            f"{select};"
            f"$s.Rate = {int(self.rate)};"
            f"$s.SetOutputToWaveFile('{out}');"
            "$s.Speak($t);$s.Dispose()"
        )
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or "falha no SAPI")
        finally:
            Path(tf.name).unlink(missing_ok=True)
        return out

    # ----------------------------- Piper ------------------------------ #
    def _piper(self, text: str, out: Path) -> Path:
        try:
            from piper.voice import PiperVoice  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Piper indisponível. Instale 'piper-tts' e baixe uma voz, ou use "
                "engine 'sapi'. Veja docs/VOICE.md."
            ) from exc
        import wave

        voice = PiperVoice.load(self.voice)
        with wave.open(str(out), "wb") as wav:
            voice.synthesize(text, wav)
        return out
