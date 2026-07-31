"""Protocolo de comunicação AI CORE -> Avatar 3D.

O CORE envia um ``AvatarState`` (JSON) pela WebSocket. A engine 3D
(Unreal/Unity) consome esse estado para dirigir animações, expressões faciais,
gestos e sincronização labial.

Formato do payload (exemplo):

    {
        "emotion": "focused",
        "gesture": "hand_explain",
        "animation": "thinking",
        "speech_state": "talking",
        "intensity": 0.7,
        "viseme": null,
        "text": "Deixa eu pensar nisso..."
    }
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Emotion(str, Enum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    CONFIDENT = "confident"
    FOCUSED = "focused"
    CONFUSED = "confused"
    SURPRISED = "surprised"
    SAD = "sad"
    THINKING = "thinking"


class Gesture(str, Enum):
    NONE = "none"
    HAND_EXPLAIN = "hand_explain"
    POINT = "point"
    THUMBS_UP = "thumbs_up"
    SHRUG = "shrug"
    WAVE = "wave"
    NOD = "nod"


class Animation(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"
    TALKING = "talking"
    TYPING = "typing"
    CELEBRATE = "celebrate"


class SpeechState(str, Enum):
    SILENT = "silent"
    TALKING = "talking"
    LISTENING = "listening"


class AvatarState(BaseModel):
    """Estado que dirige o avatar 3D. Serializável direto para a engine."""

    emotion: Emotion = Emotion.NEUTRAL
    gesture: Gesture = Gesture.NONE
    animation: Animation = Animation.IDLE
    speech_state: SpeechState = SpeechState.SILENT
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    # viseme opcional para lip-sync fino (preenchido pelo TTS na fase de voz)
    viseme: str | None = None
    # texto associado (para legendas / debug)
    text: str | None = None

    def to_event_payload(self) -> dict:
        return self.model_dump(mode="json")
