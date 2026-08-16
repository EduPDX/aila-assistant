"""Skills embutidas (Fase 8) — receitas úteis e SEGURAS (só leitura) que compõem
tools reais da Aila. Servem de exemplo e já entregam valor sem config externa."""

from __future__ import annotations

from aila.cognition.skills.models import Skill, SkillInput, SkillStep

BUILTIN_SKILLS: list[Skill] = [
    Skill(
        name="change_analysis",
        description=(
            "Antes de alterar uma função: mostra ONDE ela é definida e o RAIO DE "
            "IMPACTO (quem depende dela / o que testar). Só leitura."
        ),
        inputs=[SkillInput("name", "string", "nome da função a alterar")],
        steps=[
            SkillStep("code.definition", {"name": "{name}"}, save_as="definition"),
            SkillStep("code.impact", {"name": "{name}", "depth": 3}, save_as="impact"),
        ],
    ),
    Skill(
        name="repo_overview",
        description="Visão geral do código da Aila (repo-map: módulos/classes/funções mais chamadas).",
        steps=[SkillStep("code.map", {})],
    ),
]
