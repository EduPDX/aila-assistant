"""Plan/Execute — modelo de plano + executor com aprovação do usuário.

Permite que a Aila mostre um PLANO antes de executar tarefas complexas,
ganhando confiança do usuário. O plano é gerado pelo LLM como JSON estruturado,
apresentado na UI (cognitive scene ou chat), e executado passo a passo após
aprovação.

Fluxo:
    1. Usuário pede algo complexo
    2. LLM gera plano (steps + tools + args)
    3. UI mostra o plano (thinking animation)
    4. Usuário aprova / rejeita / edita
    5. Executor roda cada step, reporta progresso
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStep(BaseModel):
    """Um passo individual do plano."""
    id: str                               # ex.: "step_1"
    description: str                      # texto legível: "Ler o arquivo main.py"
    tool: str | None = None               # tool a executar (ex.: "file.read")
    args: dict[str, Any] = Field(default_factory=dict)   # argumentos da tool
    depends_on: list[str] = Field(default_factory=list)   # IDs dos steps anteriores
    status: StepStatus = StepStatus.PENDING
    result: str | None = None             # resultado da execução
    error: str | None = None


class Plan(BaseModel):
    """Um plano completo: sequência de passos para atingir um objetivo."""
    id: str                               # UUID curto
    goal: str                             # objetivo resumido
    steps: list[PlanStep] = Field(default_factory=list)
    status: str = "pending"               # pending|approved|running|done|failed|cancelled
    created_at: float = 0.0               # timestamp

    def to_event_payload(self) -> dict:
        return self.model_dump(mode="json")

    def next_pending(self) -> PlanStep | None:
        """Retorna o próximo step pendente cujas dependências foram satisfeitas."""
        done_ids = {s.id for s in self.steps if s.status in (StepStatus.DONE, StepStatus.SKIPPED)}
        for step in self.steps:
            if step.status != StepStatus.PENDING:
                continue
            if all(dep in done_ids for dep in step.depends_on):
                return step
        return None

    def is_complete(self) -> bool:
        return all(s.status in (StepStatus.DONE, StepStatus.SKIPPED, StepStatus.FAILED)
                   for s in self.steps)

    def mark_done(self, step_id: str, result: str = "") -> None:
        for s in self.steps:
            if s.id == step_id:
                s.status = StepStatus.DONE
                s.result = result
                return

    def mark_failed(self, step_id: str, error: str = "") -> None:
        for s in self.steps:
            if s.id == step_id:
                s.status = StepStatus.FAILED
                s.error = error
                return


# ---- Prompt para o LLM gerar planos ----

PLAN_SYSTEM_PROMPT = """\
Você é um assistente de IA que cria PLANOS antes de executar tarefas complexas.

Quando o usuário pede algo que envolve múltiplos passos, responda APENAS com um JSON
(decode) contendo o plano. Não explique em texto — o JSON É a resposta.

Formato do JSON:
{
  "goal": "objetivo curto",
  "steps": [
    {
      "id": "step_1",
      "description": "o que este passo faz (legível)",
      "tool": "nome_da_tool",
      "args": {"param": "valor"},
      "depends_on": []
    }
  ]
}

Regras:
- Cada step DEVE ter uma tool válida (file.read, file.edit, file.grep, code.execute, etc.)
- depends_on lista IDs de steps que DEVEM terminar ANTES deste
- Se steps são independentes, depends_on = [] (podem rodar em paralelo)
- Máximo 10 steps por plano
- Descrições em português, claras e curtas
- NÃO inclua texto fora do JSON
"""
