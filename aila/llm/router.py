"""Model Router — decide QUAL provedor/modelo usar para cada tarefa.

Fica entre o Agent Core (engine) e os provedores de LLM. O engine descreve a
tarefa (``RouteTask``) e o router devolve o ``LLMBackend`` adequado — sem o
engine saber qual provedor é.

FASE 1 (agora): **passthrough** — sempre devolve o provedor padrão (o backend
local atual). Comportamento idêntico ao de hoje. A estrutura já suporta vários
provedores nomeados (``providers``) e escolha por capacidade/offline nas fases
seguintes (roteamento inteligente + fallback + modo offline/híbrido).
"""

from __future__ import annotations

from dataclasses import dataclass

from aila.core.logging import get_logger
from aila.llm.base import LLMBackend

log = get_logger("router")


@dataclass(slots=True)
class RouteTask:
    """Descrição da tarefa para o router decidir o modelo.

    Preenchida com o que o engine já sabe (tipo, se usa ferramentas/visão etc.).
    """

    kind: str = "chat"          # chat | code | vision | plan | embed
    needs_tools: bool = False
    needs_vision: bool = False
    prefer_local: bool = False  # tarefa sensível → forçar local
    est_context: int = 0        # tokens estimados do contexto


class ModelRouter:
    """Seleciona um ``LLMBackend`` por tarefa. Fase 1: passthrough."""

    def __init__(
        self,
        default: LLMBackend,
        providers: dict[str, LLMBackend] | None = None,
    ) -> None:
        self.default = default
        # provedores nomeados disponíveis (Fase 3+: openai/gemini/...). Sempre
        # inclui o default para que o router possa consultá-lo pelo nome.
        self.providers: dict[str, LLMBackend] = {default.name: default}
        if providers:
            self.providers.update(providers)

    def select(self, task: RouteTask | None = None) -> LLMBackend:
        """Devolve o provedor para a tarefa. Fase 1: sempre o padrão."""
        return self.default

    def model_for(self, task: RouteTask | None = None) -> str | None:
        """Modelo específico a usar (None = usa o default_model do provedor)."""
        return None
