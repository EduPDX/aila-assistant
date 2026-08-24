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
    Skill(
        name="verify",
        description=(
            "Verifica as mudanças de código de uma vez: roda o LINTER (ruff) e "
            "depois os TESTES (pytest), consolidando o resultado. Use ao terminar "
            "uma edição para confirmar que nada quebrou."
        ),
        steps=[
            SkillStep("code.lint", {"path": ".", "select": "F"}, save_as="lint"),
            # testes exigem L3; se gated/indisponível, ainda devolve o lint (optional)
            SkillStep("code.test", {}, save_as="tests", optional=True),
        ],
    ),
    Skill(
        name="review_changes",
        description=(
            "Panorama antes de commitar: mostra o ESTADO do repo (git.status), o "
            "DIFF das mudanças e os problemas de LINT. Use para revisar o que você "
            "mexeu antes de decidir commitar. Só leitura."
        ),
        steps=[
            SkillStep("git.status", {}, save_as="status"),
            SkillStep("git.diff", {}, save_as="diff"),
            SkillStep("code.lint", {"path": ".", "select": "F"}, save_as="lint"),
        ],
    ),
]
