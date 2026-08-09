"""Observabilidade sobre o Event Bus — logging estruturado + rastreador de estado.

Assina o barramento e reage a eventos SEM acoplar o engine a esses consumidores
(o engine só publica; quem quiser, escuta). Base p/ o Task Manager (Fase 8) e
p/ a UI ler a atividade recente. NUNCA registra segredos/conteúdo sensível — só
metadados de controle (estado, tool, provedor, permissão).
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

from aila.core.logging import get_logger

if TYPE_CHECKING:
    from aila.core.event_bus import Event, EventBus

log = get_logger("events")

# eventos "de controle" que valem observar (sem spam de token nem conteúdo cru)
_TRACK = (
    "aila.state", "agent.invoked", "agent.result", "model.selected",
    "permission.request", "permission.response", "avatar.behavior", "error",
)


def _summarize(etype: str, p: dict[str, Any]) -> dict[str, Any]:
    """Resumo enxuto e SEM dados sensíveis (sem args/keys/conteúdo)."""
    if etype == "agent.invoked":
        return {"tool": p.get("tool")}
    if etype == "agent.result":
        return {"tool": p.get("tool"), "ok": p.get("ok")}
    if etype == "model.selected":
        return {"provider": p.get("provider"), "fallback": p.get("fallback", False)}
    if etype == "aila.state":
        return {"status": p.get("status"), "tool": p.get("tool")}
    if etype == "avatar.behavior":
        return {"emotion": p.get("emotion"), "intent": p.get("intent")}
    if etype == "permission.request":
        return {"action": p.get("action")}
    if etype == "error":
        return {"message": str(p.get("message", ""))[:120]}
    return {}


class AgentStateTracker:
    """Mantém o estado atual do agente + um anel de eventos recentes."""

    def __init__(self, capacity: int = 120) -> None:
        self.recent: deque[dict[str, Any]] = deque(maxlen=capacity)
        self.state: str = "IDLE"
        self.provider: str = "local"

    async def on_event(self, event: Event) -> None:
        if event.type not in _TRACK:
            return
        self.recent.append({
            "type": event.type, "t": event.timestamp, **_summarize(event.type, event.payload),
        })
        if event.type == "aila.state" and event.payload.get("status"):
            self.state = event.payload["status"]
        elif event.type == "model.selected" and event.payload.get("provider"):
            self.provider = event.payload["provider"]

    def events(self, n: int = 40) -> list[dict[str, Any]]:
        return list(self.recent)[-n:]


async def _log_event(event: Event) -> None:
    log.info(f"· {event.type} {_summarize(event.type, event.payload)}")


def attach_observability(bus: EventBus, tracker: AgentStateTracker | None = None) -> AgentStateTracker:
    """Inscreve o tracker + logging nos eventos de controle. Devolve o tracker."""
    tracker = tracker or AgentStateTracker()
    for et in _TRACK:
        bus.subscribe(et, tracker.on_event)
        bus.subscribe(et, _log_event)
    return tracker
