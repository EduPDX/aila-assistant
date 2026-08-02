"""Lip-sync: extrai a envoltória de amplitude de um WAV e transmite o valor da
boca (0..1) para o Unreal em tempo real, via ``SetMorphTarget``.

Estratégia (server-side, tudo na mesma máquina do Unreal):
    1. Pré-calcula a envoltória (RMS por quadro) do WAV do TTS.
    2. Toca o áudio (winsound, stdlib do Windows).
    3. Num thread, percorre a envoltória em tempo real e envia o peso do morph
       da boca para o Unreal a ~30 quadros/s, sincronizado com o áudio.

Só depende da stdlib (wave, winsound) + numpy (já é dependência base).
O nome do morph da boca é configurável (``avatar.unreal_mouth_morph``).
"""

from __future__ import annotations

import threading
import time
import wave

import numpy as np

from aila.core.logging import get_logger

log = get_logger("lipsync")


def amplitude_envelope(wav_path: str, fps: int = 30) -> tuple[list[float], float]:
    """Retorna (envoltória normalizada 0..1 por quadro, duração em segundos)."""
    with wave.open(str(wav_path), "rb") as wf:
        sr = wf.getframerate()
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if sampwidth == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128.0
    else:  # 24/32-bit -> trata como int32
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0

    if n_channels > 1:
        data = data.reshape(-1, n_channels).mean(axis=1)

    duration = len(data) / sr if sr else 0.0
    samples_per_frame = max(1, sr // fps)
    env: list[float] = []
    for i in range(0, len(data), samples_per_frame):
        chunk = data[i : i + samples_per_frame]
        if len(chunk):
            env.append(float(np.sqrt(np.mean(chunk**2))))

    if env:
        peak = max(env) or 1.0
        # normaliza e realça (raiz) para a boca abrir mais em volumes médios
        env = [min(1.0, (v / peak) ** 0.6) for v in env]
    return env, duration


class LipSync:
    """Toca um WAV e dirige o morph da boca no Unreal em sincronia."""

    def __init__(self, rc_call, morph_name: str, fps: int = 30) -> None:
        # rc_call(function_name: str, parameters: dict) -> bool  (da ponte Unreal)
        self._rc_call = rc_call
        self.morph_name = morph_name
        self.fps = fps
        self._stop = threading.Event()

    def _set_mouth(self, value: float) -> None:
        self._rc_call("SetMorphTarget", {"MorphTargetName": self.morph_name, "Value": value})

    def speak(self, wav_path: str, play_audio: bool = True) -> None:
        """Bloqueante: toca o áudio e anima a boca até o fim. Use em um thread."""
        if not self.morph_name:
            log.warning("nome do morph da boca não configurado; lip-sync desativado")
            return
        env, _ = amplitude_envelope(wav_path, self.fps)
        if not env:
            return

        if play_audio:
            try:
                import winsound

                winsound.PlaySound(
                    str(wav_path), winsound.SND_FILENAME | winsound.SND_ASYNC
                )
            except Exception as exc:  # noqa: BLE001
                log.warning(f"não consegui tocar o áudio: {exc!r}")

        self._stop.clear()
        period = 1.0 / self.fps
        start = time.monotonic()
        for i, value in enumerate(env):
            if self._stop.is_set():
                break
            self._set_mouth(value)
            # mantém o ritmo alinhado ao relógio (evita drift)
            target = start + (i + 1) * period
            time.sleep(max(0.0, target - time.monotonic()))
        self._set_mouth(0.0)  # fecha a boca no fim

    def speak_async(self, wav_path: str, play_audio: bool = True) -> threading.Thread:
        t = threading.Thread(target=self.speak, args=(wav_path, play_audio), daemon=True)
        t.start()
        return t

    def stop(self) -> None:
        self._stop.set()
