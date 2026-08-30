"""Model Router — decide QUAL provedor/modelo usar para cada tarefa.

Fica entre o Agent Core (engine) e os provedores de LLM. O engine descreve a
tarefa (``RouteTask``); o router devolve o provedor adequado — sem o engine
saber qual é.

- ``enabled: false`` (default) → **passthrough**: sempre o provedor padrão
  (local). Comportamento idêntico ao de hoje.
- ``enabled: true`` → escolhe por tipo de tarefa (``rules``), filtrando por
  capacidade (visão/tools), disponibilidade (registrado) e privacidade (no
  modo OFFLINE, só provedores locais). Devolve uma CADEIA de fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from aila.core.logging import get_logger
from aila.llm.base import LLMBackend

if TYPE_CHECKING:
    from aila.core.config import RoutingConfig
    from aila.llm.health import HealthRegistry
    from aila.security.network_policy import NetworkPolicy

log = get_logger("router")


@dataclass(slots=True)
class RouteTask:
    """Descrição da tarefa para o router decidir o modelo."""

    kind: str = "chat"          # chat | code | vision | reasoning | plan
    needs_tools: bool = False
    needs_vision: bool = False
    prefer_local: bool = False  # tarefa sensível → forçar local
    est_context: int = 0
    complexity: float = 0.0     # 0..1 (Fase H) — trivial→3B, pesada→maior


class ModelRouter:
    def __init__(
        self,
        default: LLMBackend,
        providers: dict[str, LLMBackend] | None = None,
        config: RoutingConfig | None = None,
        network: NetworkPolicy | None = None,
        health: HealthRegistry | None = None,
    ) -> None:
        self.default = default
        self.config = config
        self.network = network
        # circuit-breaker por provedor (R4). None → sem filtro de saúde (comportamento
        # idêntico ao anterior). Só PULA provedores extras; nunca esvazia a cadeia.
        self.health = health
        # provedores nomeados (inclui o default como "local" e pelo nome real).
        self.providers: dict[str, LLMBackend] = {default.name: default}
        if providers:
            self.providers.update(providers)

    def _resolve(self, name: str) -> LLMBackend | None:
        if name in ("local", "default"):
            return self.default
        return self.providers.get(name)

    def _allowed(self, be: LLMBackend, task: RouteTask) -> bool:
        caps = be.capabilities()
        # privacidade: no modo offline (ou tarefa sensível), só provedores locais
        if (self.network is not None and self.network.is_offline) or task.prefer_local:
            if not caps.local:
                return False
        if task.needs_vision and not caps.vision:
            return False
        if task.needs_tools and not caps.tools:
            return False
        return True

    def chain(self, task: RouteTask | None = None) -> list[LLMBackend]:
        """Ordem de provedores a tentar (fallback). Sempre termina no default
        se ele for permitido."""
        task = task or RouteTask()
        cfg = self.config
        if cfg is None or not cfg.enabled:
            return [self.default]

        names = cfg.rules.get(task.kind) or [cfg.default]
        out: list[LLMBackend] = []
        for name in names:
            be = self._resolve(name)
            if be and be not in out and self._allowed(be, task) and self._healthy(be):
                out.append(be)
        # garante o local como último fallback (se permitido)
        if self.default not in out and self._allowed(self.default, task):
            out.append(self.default)
        return out or [self.default]

    def _healthy(self, be: LLMBackend) -> bool:
        """Provedor não está em cooldown? Sem HealthRegistry, todos passam. O default
        NUNCA é filtrado aqui — o fallback local garantido é adicionado à parte."""
        if self.health is None or be is self.default:
            return True
        return self.health.available(be.name)

    def select(self, task: RouteTask | None = None) -> LLMBackend:
        """Melhor provedor para a tarefa (o primeiro da cadeia)."""
        return self.chain(task)[0]
