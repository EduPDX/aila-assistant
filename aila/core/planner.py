"""Planner — decompõe um objetivo em um PLANO de passos acionáveis, e replaneja
quando um passo falha.

Usa o Model Router (tarefa "plan" → pode ir p/ um modelo de raciocínio mais
forte no modo híbrido). Devolve uma lista de strings (passos). Parsing robusto:
aceita array JSON ou lista numerada, com fallback para o objetivo inteiro.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from aila.core.logging import get_logger
from aila.llm.router import RouteTask

if TYPE_CHECKING:
    from aila.llm.router import ModelRouter

log = get_logger("planner")

_SYS = (
    "Você é um planejador de tarefas. Decomponha o objetivo do usuário em uma "
    "sequência CURTA de passos concretos e acionáveis (3 a 6). Cada passo é uma "
    "frase no imperativo. Responda APENAS com um array JSON de strings, sem "
    "nenhum texto fora do array."
)


def parse_steps(text: str, fallback: str) -> list[str]:
    m = re.search(r"\[.*\]", text or "", re.S)
    if m:
        try:
            arr = json.loads(m.group(0))
            steps = [str(s).strip() for s in arr if str(s).strip()]
            if steps:
                return steps[:8]
        except (json.JSONDecodeError, TypeError):
            pass
    # fallback: linhas numeradas / com marcador
    steps: list[str] = []
    for line in (text or "").splitlines():
        clean = re.sub(r"^\s*(\d+[.)]|[-*•])\s*", "", line).strip()
        if clean and len(clean) > 3:
            steps.append(clean)
    return steps[:8] or [fallback]


class Planner:
    def __init__(self, router: ModelRouter) -> None:
        self.router = router

    async def _ask(self, user: str, fallback: str) -> list[str]:
        backend = self.router.select(RouteTask(kind="plan"))
        try:
            resp = await backend.complete(
                [{"role": "system", "content": _SYS}, {"role": "user", "content": user}]
            )
        except Exception as exc:  # noqa: BLE001 - planejar nunca deve quebrar
            log.warning(f"planner falhou ({exc!r}); usando 1 passo = objetivo")
            return [fallback]
        return parse_steps(resp, fallback)

    async def plan(self, goal: str) -> list[str]:
        return await self._ask(f"Objetivo: {goal}", goal)

    async def replan(self, goal: str, done: list[str], failure: str) -> list[str]:
        done_txt = "\n".join(f"- {d}" for d in done) or "(nenhum)"
        user = (
            f"Objetivo: {goal}\nPassos já concluídos:\n{done_txt}\n"
            f"O último passo FALHOU: {failure}\n"
            "Replaneje os PRÓXIMOS passos para atingir o objetivo (array JSON)."
        )
        return await self._ask(user, goal)
