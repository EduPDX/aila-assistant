"""Observabilidade sobre o Event Bus — logging estruturado + rastreador de estado.

Assina o barramento e reage a eventos SEM acoplar o engine a esses consumidores
(o engine só publica; quem quiser, escuta). Base p/ o Task Manager (Fase 8) e
p/ a UI ler a atividade recente. NUNCA registra segredos/conteúdo sensível — só
metadados de controle (estado, tool, provedor, permissão).
"""

from __future__ import annotations

from collections import Counter, deque
from typing import TYPE_CHECKING, Any

from aila.core.logging import get_logger

if TYPE_CHECKING:
    from aila.core.event_bus import Event, EventBus

log = get_logger("events")

# eventos COGNITIVOS (Fase 9): a "atividade mental" da Aila — alimentam o
# mini-subconsciente e a aba 🧠 do Bloco C. Só metadados (nunca o conteúdo).
_COGNITIVE = (
    "memory.recalled", "memory.consolidated", "graph.updated",
    "guardrail.triggered", "skill.ran",
)

# eventos "de controle" que valem observar (sem spam de token nem conteúdo cru)
_TRACK = (
    "aila.state", "agent.invoked", "agent.result", "model.selected",
    "permission.request", "permission.response", "avatar.behavior", "error",
    "task.created", "task.state", *_COGNITIVE,
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
    if etype in ("task.created", "task.state"):
        return {"id": p.get("id"), "state": p.get("state"), "progress": p.get("progress")}
    if etype == "error":
        return {"message": str(p.get("message", ""))[:120]}
    # --- cognitivos (só contagens/tipos; NUNCA o texto da memória) ---
    if etype == "memory.recalled":
        return {"count": len(p.get("items", []) or [])}
    if etype == "memory.consolidated":
        return {k: p.get(k, 0) for k in ("archived", "merged", "nodes", "edges")}
    if etype == "graph.updated":
        return {"nodes": p.get("nodes"), "edges": p.get("edges")}
    if etype == "guardrail.triggered":
        return {"kinds": list(p.get("kinds", []) or [])}   # tipos, não valores
    if etype == "skill.ran":
        return {"skill": p.get("skill"), "ok": p.get("ok"), "steps": p.get("steps")}
    return {}


class AgentStateTracker:
    """Mantém o estado atual do agente + um anel de eventos recentes."""

    def __init__(self, capacity: int = 120) -> None:
        self.recent: deque[dict[str, Any]] = deque(maxlen=capacity)
        self.state: str = "IDLE"
        self.provider: str = "local"
        # totais acumulados dos eventos cognitivos (lifetime; barato)
        self.cognitive: Counter[str] = Counter()

    async def on_event(self, event: Event) -> None:
        if event.type not in _TRACK:
            return
        summary = _summarize(event.type, event.payload)
        self.recent.append({"type": event.type, "t": event.timestamp, **summary})
        if event.type == "aila.state" and event.payload.get("status"):
            self.state = event.payload["status"]
        elif event.type == "model.selected" and event.payload.get("provider"):
            self.provider = event.payload["provider"]
        elif event.type in _COGNITIVE:
            self.cognitive[event.type] += 1

    def events(self, n: int = 40) -> list[dict[str, Any]]:
        return list(self.recent)[-n:]

    def cognitive_summary(self, n: int = 20) -> dict[str, Any]:
        """Feed do "subconsciente" p/ a UI: totais acumulados + últimos eventos
        cognitivos (memória/grafo/guardrail/skill). Só metadados, sem conteúdo."""
        recent = [e for e in self.recent if e["type"] in _COGNITIVE][-n:]
        return {
            "totals": {k: self.cognitive.get(k, 0) for k in _COGNITIVE},
            "recent": recent,
        }


async def _log_event(event: Event) -> None:
    log.info(f"· {event.type} {_summarize(event.type, event.payload)}")


def attach_observability(bus: EventBus, tracker: AgentStateTracker | None = None) -> AgentStateTracker:
    """Inscreve o tracker + logging nos eventos de controle. Devolve o tracker."""
    tracker = tracker or AgentStateTracker()
    for et in _TRACK:
        bus.subscribe(et, tracker.on_event)
        bus.subscribe(et, _log_event)
    return tracker
