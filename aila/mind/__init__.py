"""Cognitive Core da Aila — identidade, corpo e estado interno.

Separado de ``aila.cognition`` (memória/grafo/skills) de propósito: aqui mora
"quem a Aila é", lá mora "o que ela sabe".
"""

from aila.mind.identity import load_identity
from aila.mind.personality import (
    MotionBias,
    PersonalityStyle,
    derive_style,
    error_style,
    motion_bias,
    should_take_initiative,
)
from aila.mind.schemas import (
    Action,
    AilaState,
    BodyState,
    Capabilities,
    Decision,
    Experience,
    Identity,
    PersonalityTraits,
    Speech,
)
from aila.mind.self_model import AilaSelf

__all__ = [
    "Action", "AilaSelf", "AilaState", "BodyState", "Capabilities", "Decision",
    "Experience", "Identity", "MotionBias", "PersonalityStyle", "PersonalityTraits",
    "Speech", "derive_style", "error_style", "load_identity", "motion_bias",
    "should_take_initiative",
]
