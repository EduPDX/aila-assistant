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

import asyncio
import subprocess
import tempfile
import threading
import wave
from pathlib import Path

from aila.core.logging import get_logger

log = get_logger("tts")


def _module_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:  # noqa: BLE001
        return False


def _run_coro(coro):
    """Executa uma corrotina mesmo se já houver um event loop rodando
    (roda em um thread próprio com seu próprio loop)."""
    box: dict = {}

    def runner():
        try:
            box["result"] = asyncio.run(coro)
        except Exception as exc:  # noqa: BLE001
            box["error"] = exc

    t = threading.Thread(target=runner)
    t.start()
    t.join()
    if "error" in box:
        raise box["error"]
    return box.get("result")


def mp3_to_wav(mp3_path: str | Path, wav_path: str | Path, rate: int = 22050) -> Path:
    """Converte um MP3 (ex.: saída do Edge-TTS) para WAV PCM 16-bit mono."""
    import av  # PyAV (já vem com o extra de voz)
    import numpy as np

    chunks = []
    with av.open(str(mp3_path)) as container:
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="s16", layout="mono", rate=rate)
        for frame in container.decode(stream):
            for rframe in resampler.resample(frame):
                chunks.append(rframe.to_ndarray().reshape(-1))
    data = np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.int16)
    out = Path(wav_path)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data.astype("<i2").tobytes())
    return out


class TextToSpeech:
    def __init__(
        self,
        engine: str = "auto",
        voice: str = "",
        rate: int = 0,
        edge_pitch: str = "+0Hz",
        edge_rate: str = "+0%",
    ) -> None:
        self.voice = voice
        self.rate = rate
        self.edge_pitch = edge_pitch
        self.edge_rate = edge_rate
        if engine == "auto":
            if _module_available("edge_tts"):
                engine = "edge"
                if not self.voice:
                    self.voice = "pt-BR-FranciscaNeural"
            elif _module_available("piper"):
                engine = "piper"
            else:
                engine = "sapi"
        self.engine = engine
        log.info(f"TTS engine: {self.engine} (voz: {self.voice or 'auto'})")

    # ------------------------------------------------------------------ #
    def synthesize(self, text: str, out_path: str | Path) -> Path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        text = (text or "").strip()
        if not text:
            raise ValueError("texto vazio para síntese")
        if self.engine == "edge":
            return self._edge(text, out)
        if self.engine == "piper":
            return self._piper(text, out)
        return self._sapi(text, out)

    # ----------------------------- Edge ------------------------------- #
    def _edge(self, text: str, out: Path) -> Path:
        """Edge-TTS (vozes neurais da Microsoft, online). Gera MP3; converte
        para WAV se o PyAV estiver disponível, senão devolve o MP3 direto — o
        navegador toca MP3 nativamente e o lip-sync (MediaElementSource) também
        funciona. Assim a voz NÃO depende do PyAV (que falta no .exe)."""
        try:
            import edge_tts  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                'Edge-TTS indisponível. Instale: pip install edge-tts'
            ) from exc

        voice = self.voice or "pt-BR-FranciscaNeural"
        mp3 = out.with_suffix(".mp3")

        async def _gen():
            comm = edge_tts.Communicate(
                text, voice, rate=self.edge_rate, pitch=self.edge_pitch
            )
            await comm.save(str(mp3))

        _run_coro(_gen())
        if _module_available("av"):
            try:
                mp3_to_wav(mp3, out)
                mp3.unlink(missing_ok=True)
                return out
            except Exception as exc:  # noqa: BLE001 - conversão falhou: usa o MP3
                log.warning(f"mp3->wav falhou ({exc!r}); servindo MP3 direto")
        return mp3

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
