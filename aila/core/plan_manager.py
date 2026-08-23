"""PlanManager — gerencia o ciclo de vida dos planos.

Gera planos via LLM, valida, expõe para aprovação do usuário,
e executa cada step ferramenta por ferramenta.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from aila.core.logging import get_logger
from aila.core.plan import Plan, PlanStep, StepStatus

if TYPE_CHECKING:
    pass

log = get_logger("plan_manager")

# Tipo da função que executa uma tool
ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[Any]]


class PlanManager:
    """Gerencia planos: geração → aprovação → execução."""

    def __init__(self) -> None:
        self.active_plan: Plan | None = None
        self._history: list[Plan] = []

    def new_plan(self, goal: str = "", steps: list[dict] | None = None) -> Plan:
        """Cria um novo plano (gerado pelo LLM ou importado)."""
        plan = Plan(
            id=uuid.uuid4().hex[:8],
            goal=goal,
            steps=[PlanStep(**s) for s in (steps or [])],
            status="pending",
            created_at=time.time(),
        )
        self.active_plan = plan
        return plan

    def approve(self) -> bool:
        """Usuário aprovou o plano — pode começar a executar."""
        if not self.active_plan or self.active_plan.status != "pending":
            return False
        self.active_plan.status = "approved"
        return True

    def reject(self) -> bool:
        """Usuário rejeitou o plano."""
        if not self.active_plan:
            return False
        self.active_plan.status = "cancelled"
        self._history.append(self.active_plan)
        self.active_plan = None
        return True

    async def execute(
        self,
        plan: Plan,
        tool_executor: ToolExecutor,
        emit: Callable[[str, dict], Awaitable[None]] | None = None,
    ) -> Plan:
        """Executa todos os steps do plano na ordem das dependências."""
        plan.status = "running"
        max_iter = len(plan.steps) + 1   # segurança contra loop infinito

        for _ in range(max_iter):
            step = plan.next_pending()
            if step is None:
                break   # todos concluídos ou sem dependentes disponíveis

            step.status = StepStatus.RUNNING
            if emit:
                await emit("plan.step_start", {
                    "plan_id": plan.id,
                    "step_id": step.id,
                    "description": step.description,
                    "tool": step.tool,
                })

            if not step.tool:
                step.status = StepStatus.DONE
                step.result = "(step sem tool — pulado)"
                continue

            try:
                result = await tool_executor(step.tool, step.args)
                # result pode ser ToolResult ou dict
                content = getattr(result, "content", None) or (result.get("content", "") if isinstance(result, dict) else str(result))
                ok = getattr(result, "ok", True) if hasattr(result, "ok") else True
                if ok:
                    plan.mark_done(step.id, content[:500])
                else:
                    plan.mark_failed(step.id, content[:500])
            except Exception as exc:
                log.warning(f"step {step.id} falhou: {exc!r}")
                plan.mark_failed(step.id, str(exc)[:500])

            if emit:
                await emit("plan.step_done", {
                    "plan_id": plan.id,
                    "step_id": step.id,
                    "status": step.status.value,
                    "result": (step.result or step.error or "")[:300],
                })

        plan.status = "done" if plan.is_complete() else "failed"
        self._history.append(plan)
        if plan is self.active_plan:
            self.active_plan = None
        return plan

    def parse_llm_response(self, text: str) -> Plan | None:
        """Tenta extrair um plano de uma resposta do LLM (JSON no texto)."""
        # Tentar JSON direto
        try:
            data = json.loads(text)
            if "goal" in data and "steps" in data:
                return self.new_plan(goal=data["goal"], steps=data["steps"])
        except (json.JSONDecodeError, KeyError):
            pass

        # Tentar JSON dentro de ```json ... ```
        import re
        m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                if "goal" in data and "steps" in data:
                    return self.new_plan(goal=data["goal"], steps=data["steps"])
            except (json.JSONDecodeError, KeyError):
                pass

        return None
