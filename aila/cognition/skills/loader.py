"""Carga e registro de Skills (Fase 8).

Skills = embutidas (código) + externas (arquivos .yaml/.yml num diretório opcional).
Cada Skill é registrada no ToolRegistry como ``skill.<nome>`` → o LLM pode invocar
a receita inteira como UMA ferramenta; os passos internos passam pela segurança
normal (authorize por tool). Externas com nome repetido têm precedência sobre as
embutidas (customização pelo usuário)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from aila.cognition.skills.builtins import BUILTIN_SKILLS
from aila.cognition.skills.models import Skill
from aila.cognition.skills.runner import SkillRunner
from aila.core.logging import get_logger
from aila.tools.schema import Tool, ToolParam, ToolResult

if TYPE_CHECKING:
    from aila.tools.registry import ToolRegistry

log = get_logger("skills")


def load_skills(skills_dir: str | Path | None = None) -> list[Skill]:
    """Embutidas + externas (.yaml/.yml). Externa sobrescreve embutida de mesmo nome."""
    by_name: dict[str, Skill] = {s.name: s for s in BUILTIN_SKILLS}
    if skills_dir:
        p = Path(skills_dir)
        if p.is_dir():
            for f in sorted([*p.glob("*.yaml"), *p.glob("*.yml")]):
                try:
                    data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
                    sk = Skill.from_dict(data)
                    by_name[sk.name] = sk
                    log.info(f"skill externa carregada: {sk.name} ({f.name})")
                except (KeyError, ValueError, yaml.YAMLError) as exc:
                    log.warning(f"skill inválida em {f.name}: {exc!r}")
    return list(by_name.values())


def skill_to_tool(skill: Skill, runner: SkillRunner) -> Tool:
    async def handler(args: dict) -> ToolResult:
        missing = [i.name for i in skill.inputs
                   if i.required and not str(args.get(i.name, "")).strip()]
        if missing:
            return ToolResult.error(
                f"Skill '{skill.name}': faltam parâmetros: {', '.join(missing)}")
        result = await runner.run(skill, args)
        if not result.ok:
            return ToolResult.error(result.content or f"Skill '{skill.name}' falhou.")
        return ToolResult.success(result.content, skill=skill.name, steps=len(result.steps))

    return Tool(
        name=f"skill.{skill.name}",
        description=f"[Skill] {skill.description}",
        params=[ToolParam(i.name, i.type, i.description, required=i.required)
                for i in skill.inputs],
        handler=handler,
        agent="skill",
    )


def register_skills(registry: ToolRegistry, runner: SkillRunner, skills: list[Skill]) -> int:
    """Registra cada skill como tool ``skill.<nome>``. Avisa (não falha) se um
    passo referenciar uma tool que não existe no registry."""
    known = {t.name for t in registry.all()}
    count = 0
    for sk in skills:
        for st in sk.steps:
            if st.tool not in known and not st.tool.startswith("skill."):
                log.warning(f"skill '{sk.name}': passo usa tool ausente '{st.tool}'")
        try:
            registry.register(skill_to_tool(sk, runner))
            count += 1
        except ValueError:
            log.warning(f"skill duplicada, ignorada: skill.{sk.name}")
    return count
