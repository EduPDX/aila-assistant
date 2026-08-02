"""Ponte OSC: transmite o AvatarState para um motor 3D (Unreal Engine).

O Unreal roda um **OSC Server** (plugin OSC nativo, Blueprint puro) escutando em
``osc_host:osc_port``. A cada mudança de estado, a Aila envia mensagens OSC que
o Blueprint roteia por endereço para dirigir o Animation Blueprint e o
Control Rig de morph (expressões).

Contrato de endereços (ver docs/AVATAR_3D.md):

    /aila/emotion    (string)  neutral|happy|confident|focused|confused|...
    /aila/gesture    (string)  wink|nice|point|...   (só quando != none)
    /aila/animation  (string)  idle|thinking|talking|typing|celebrate
    /aila/speech     (string)  silent|talking|listening
    /aila/intensity  (float)   0.0 .. 1.0
    /aila/text       (string)  legenda opcional (truncada)

UDP fire-and-forget: se o Unreal não estiver ouvindo, nada quebra.
"""

from __future__ import annotations

from typing import Any

from aila.core.logging import get_logger

log = get_logger("osc")


class OSCAvatarBridge:
    def __init__(self, host: str = "127.0.0.1", port: int = 8000) -> None:
        from pythonosc.udp_client import SimpleUDPClient  # import tardio (opcional)

        self.host = host
        self.port = port
        self.client = SimpleUDPClient(host, port)
        log.info(f"ponte OSC do avatar -> {host}:{port}")

    def send(self, state: dict[str, Any]) -> None:
        """Envia um AvatarState (dict serializado) via OSC. Nunca levanta."""
        try:
            self.client.send_message("/aila/emotion", str(state.get("emotion", "neutral")))
            gesture = state.get("gesture", "none")
            if gesture and gesture != "none":
                self.client.send_message("/aila/gesture", str(gesture))
            self.client.send_message("/aila/animation", str(state.get("animation", "idle")))
            self.client.send_message("/aila/speech", str(state.get("speech_state", "silent")))
            self.client.send_message("/aila/intensity", float(state.get("intensity", 0.5)))
            text = state.get("text")
            if text:
                self.client.send_message("/aila/text", str(text)[:120])
        except Exception as exc:  # noqa: BLE001 - o avatar nunca deve quebrar o chat
            log.warning(f"falha ao enviar OSC: {exc!r}")
