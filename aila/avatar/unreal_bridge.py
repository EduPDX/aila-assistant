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

import threading

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

# gesto -> animação one-shot (braço/corpo). Toca uma vez e volta ao idle.
# Ajuste os nomes conforme o que cada animação faz na sua personagem.
GEST_ANIM = {
    "thumbs_up": "Anim_Nice",
    "hand_explain": "Anim_Nice",
    "wave": "Anim_Quan",
    "point": "Anim_Quan",
    "shrug": "Anim_Doodle",
    "nod": "Anim_Stand",
}


class UnrealRemoteControlBridge:
    def __init__(
        self,
        rc_url: str,
        mesh_path: str,
        anim_base: str,
        gesture_hold: float = 2.5,
    ) -> None:
        self.call_url = rc_url.rstrip("/") + "/remote/object/call"
        self.mesh_path = mesh_path
        self.anim_base = anim_base.rstrip("/") + "/"
        self.gesture_hold = gesture_hold
        self._client = httpx.Client(timeout=1.5)
        self._last_key: tuple[str, str] | None = None
        self._timer: threading.Timer | None = None
        self._editor_ready = False
        log.info(f"ponte Unreal (Remote Control) -> {self.call_url}")

    def _full_asset(self, name: str) -> str:
        # /Game/.../Anim/Anim_X  ->  /Game/.../Anim/Anim_X.Anim_X
        return f"{self.anim_base}{name}.{name}"

    def _rc_call(self, function_name: str, parameters: dict) -> bool:
        body = {
            "objectPath": self.mesh_path,
            "functionName": function_name,
            "parameters": parameters,
            "generateTransaction": False,
        }
        try:
            resp = self._client.put(self.call_url, json=body)
            if resp.status_code >= 400:
                log.warning(f"Unreal recusou {function_name}: {resp.status_code} {resp.text[:120]}")
                return False
            return True
        except httpx.HTTPError as exc:
            log.warning(f"Unreal indisponível (Remote Control): {exc!r}")
            return False

    def _ensure_editor_updates(self) -> None:
        # Sem isto, PlayAnimation não atualiza a malha no viewport do EDITOR.
        if not self._editor_ready:
            if self._rc_call("SetUpdateAnimationInEditor", {"NewUpdateState": True}):
                self._editor_ready = True

    def play(self, anim_name: str, looping: bool = True) -> bool:
        self._ensure_editor_updates()
        return self._rc_call(
            "PlayAnimation",
            {"NewAnimToPlay": self._full_asset(anim_name), "bLooping": looping},
        )

    def _resume_idle(self, emotion: str) -> None:
        self.play(EMO_ANIM.get(emotion, "Anim_Breathy"), looping=True)

    def send(self, state: dict) -> None:
        """Recebe um AvatarState (dict) e dirige a personagem. Nunca levanta.

        Emoção -> animação de idle (loop). Gesto -> animação one-shot que toca e
        depois volta ao idle da emoção (após ``gesture_hold`` segundos).
        """
        emotion = state.get("emotion", "neutral")
        gesture = state.get("gesture", "none")
        key = (emotion, gesture)
        if key == self._last_key:
            return
        self._last_key = key

        # cancela um retorno-ao-idle pendente de um gesto anterior
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

        gest_anim = GEST_ANIM.get(gesture) if gesture and gesture != "none" else None
        if gest_anim:
            self.play(gest_anim, looping=False)          # gesto: toca uma vez
            self._timer = threading.Timer(self.gesture_hold, self._resume_idle, args=(emotion,))
            self._timer.daemon = True
            self._timer.start()
        else:
            self.play(EMO_ANIM.get(emotion, "Anim_Breathy"), looping=True)
