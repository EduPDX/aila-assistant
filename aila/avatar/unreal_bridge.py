"""Ponte Unreal via Remote Control: dirige a personagem 3D SEM plugins extras.

Usa a **Web Remote Control API** do Unreal (já embutida; basta habilitar o
plugin "Remote Control API"). A cada mudança de estado, a Aila faz um
``PUT /remote/object/call`` para tocar a animação da emoção na personagem —
nada de OSC, Blueprint ou script no editor.

Pré-requisitos no Unreal:
    - Plugin "Remote Control API" ligado (servidor em 127.0.0.1:30010).
    - A personagem posicionada no nível (ex.: BP_Character da Hayakawa).

O caminho do componente de malha e a pasta de animações são configuráveis
(``avatar.unreal_*``), pois dependem do nível/projeto.
"""

from __future__ import annotations

import httpx

from aila.core.logging import get_logger

log = get_logger("unreal")

# emoção -> animação de idle (em loop), pelo nome do asset
EMO_ANIM = {
    "happy": "Anim_Breathy_Happy",
    "confident": "Anim_Breathy_Happy",
    "surprised": "Anim_Breathy_Happy",
    "sad": "Anim_Breathy_UnHappy",
    "confused": "Anim_Breathy_UnHappy",
    "focused": "Anim_Breathy",
    "thinking": "Anim_Breathy",
    "neutral": "Anim_Breathy",
}


class UnrealRemoteControlBridge:
    def __init__(
        self,
        rc_url: str,
        mesh_path: str,
        anim_base: str,
    ) -> None:
        self.call_url = rc_url.rstrip("/") + "/remote/object/call"
        self.mesh_path = mesh_path
        self.anim_base = anim_base.rstrip("/") + "/"
        self._client = httpx.Client(timeout=1.5)
        self._last_anim: str | None = None
        log.info(f"ponte Unreal (Remote Control) -> {self.call_url}")

    def _full_asset(self, name: str) -> str:
        # /Game/.../Anim/Anim_X  ->  /Game/.../Anim/Anim_X.Anim_X
        return f"{self.anim_base}{name}.{name}"

    def play(self, anim_name: str, looping: bool = True) -> bool:
        body = {
            "objectPath": self.mesh_path,
            "functionName": "PlayAnimation",
            "parameters": {
                "NewAnimToPlay": self._full_asset(anim_name),
                "bLooping": looping,
            },
            "generateTransaction": False,
        }
        try:
            resp = self._client.put(self.call_url, json=body)
            if resp.status_code >= 400:
                log.warning(f"Unreal recusou PlayAnimation: {resp.status_code} {resp.text[:120]}")
                return False
            return True
        except httpx.HTTPError as exc:
            log.warning(f"Unreal indisponível (Remote Control): {exc!r}")
            return False

    def send(self, state: dict) -> None:
        """Recebe um AvatarState (dict) e dirige a personagem. Nunca levanta."""
        anim = EMO_ANIM.get(state.get("emotion", "neutral"), "Anim_Breathy")
        if anim == self._last_anim:
            return  # evita re-enviar a mesma animação
        self._last_anim = anim
        self.play(anim, looping=True)
