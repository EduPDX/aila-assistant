"""Execução de Skills (Fase 8).

O SkillRunner roda os passos de uma Skill pelo MESMO ToolRegistry do engine —
portanto cada passo chama a tool real, que por sua vez chama ``authorize()``.
A Skill é só composição: NÃO contorna segurança, NÃO reimplementa o tool-loop.

Interpolação: valores string dos args passam por ``str.format(**ctx)``, onde o
contexto = inputs da skill + saídas de passos anteriores (via ``save_as``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aila.cognition.skills.models import Skill, SkillResult
from aila.core.logging import get_logger

if TYPE_CHECKING:
    from aila.core.event_bus import EventBus
    from aila.tools.registry import ToolRegistry

log = get_logger("skills")


class SkillRunner:
    def __init__(self, registry: ToolRegistry, bus: EventBus | None = None) -> None:
        self.registry = registry
        self.bus = bus

    def _render(self, value: Any, ctx: dict[str, Any]) -> Any:
        if isinstance(value, str):
            try:
                return value.format(**ctx)
            except (KeyError, IndexError, ValueError):
                return value                      # placeholder ausente → mantém literal
        if isinstance(value, dict):
            return {k: self._render(v, ctx) for k, v in value.items()}
        if isinstance(value, list):
            return [self._render(v, ctx) for v in value]
        return value

    async def run(self, skill: Skill, inputs: dict[str, Any] | None = None) -> SkillResult:
        ctx: dict[str, Any] = dict(inputs or {})
        steps_out: list[dict[str, Any]] = []
        outputs: dict[str, str] = {}
        ok_all = True
        for st in skill.steps:
            args = self._render(st.args, ctx)
            res = await self.registry.execute(st.tool, args)   # ← authorize() dentro da tool
            steps_out.append({"tool": st.tool, "ok": res.ok, "content": res.content})
            if st.save_as:
                ctx[st.save_as] = res.content
                outputs[st.save_as] = res.content
            if not res.ok and not st.optional:
                ok_all = False
                break
        if self.bus is not None:
            try:
                await self.bus.emit("skill.ran",
                                    {"skill": skill.name, "ok": ok_all, "steps": len(steps_out)},
                                    source="skills")
            except Exception as exc:  # noqa: BLE001 - o bus nunca deve quebrar a skill
                log.warning(f"bus falhou em skill.ran: {exc!r}")
        content = "\n\n".join(f"[{s['tool']}]\n{s['content']}" for s in steps_out)
        return SkillResult(ok=ok_all, steps=steps_out, outputs=outputs, content=content)
