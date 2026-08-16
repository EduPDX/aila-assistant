"""Modelos de Skill (Fase 8).

Uma Skill é uma RECEITA nomeada e reutilizável: uma sequência de passos, cada um
invocando uma ferramenta já existente (com interpolação de argumentos). Não é um
novo motor — reusa o ToolRegistry, então CADA passo passa pela mesma segurança
(authorize/policy) da tool que ele chama. Puramente dados.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SkillStep:
    tool: str                                    # ex.: "code.impact"
    args: dict[str, Any] = field(default_factory=dict)   # template: "{param}" interpolável
    save_as: str | None = None                   # guarda o .content do passo p/ passos seguintes
    optional: bool = False                       # se True, falha NÃO aborta a skill


@dataclass(slots=True)
class SkillInput:
    name: str
    type: str = "string"
    description: str = ""
    required: bool = True


@dataclass(slots=True)
class Skill:
    name: str
    description: str
    steps: list[SkillStep] = field(default_factory=list)
    inputs: list[SkillInput] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Skill:
        steps = [
            SkillStep(tool=s["tool"], args=s.get("args") or {},
                      save_as=s.get("save_as"), optional=bool(s.get("optional", False)))
            for s in (d.get("steps") or [])
        ]
        inputs = [
            SkillInput(name=i["name"], type=i.get("type", "string"),
                       description=i.get("description", ""), required=bool(i.get("required", True)))
            for i in (d.get("inputs") or [])
        ]
        return cls(name=d["name"], description=d.get("description", ""),
                   steps=steps, inputs=inputs)


@dataclass(slots=True)
class SkillResult:
    ok: bool
    steps: list[dict[str, Any]]                  # [{tool, ok, content}]
    outputs: dict[str, str] = field(default_factory=dict)   # save_as -> content
    content: str = ""                            # relatório legível (todos os passos)
