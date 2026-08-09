"""Avatar 3D: protocolo de estado, motor de emoções e Behavior Planner."""

from aila.avatar.behavior_planner import BehaviorPlanner
from aila.avatar.behavior_spec import BehaviorSpec, GestureCue, Motion
from aila.avatar.emotion_engine import EmotionEngine
from aila.avatar.protocol import AvatarState, Emotion, Gesture, SpeechState

__all__ = [
    "AvatarState", "Emotion", "Gesture", "SpeechState", "EmotionEngine",
    "BehaviorPlanner", "BehaviorSpec", "GestureCue", "Motion",
]
