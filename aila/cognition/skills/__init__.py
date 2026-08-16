"""Skills — receitas nomeadas e reutilizáveis que compõem tools existentes.
Cada passo passa pela mesma segurança (authorize/policy) da tool que invoca."""

from aila.cognition.skills.loader import load_skills, register_skills, skill_to_tool
from aila.cognition.skills.models import Skill, SkillInput, SkillResult, SkillStep
from aila.cognition.skills.runner import SkillRunner

__all__ = [
    "Skill", "SkillStep", "SkillInput", "SkillResult", "SkillRunner",
    "load_skills", "register_skills", "skill_to_tool",
]
