"""Barramento de eventos assíncrono — a espinha dorsal da comunicação
entre módulos (core, agentes, voz, visão, avatar, UI).

Padrão publish/subscribe. Qualquer módulo pode emitir um evento e qualquer
outro pode escutá-lo, sem acoplamento direto.

Eventos canônicos (veja docs/ARCHITECTURE.md):
    user.message          UI  -> core
    assistant.token       core -> UI          (streaming)
    assistant.message     core -> UI
    agent.invoked         core -> UI
    agent.result          agent -> core
    permission.request    security -> UI
    permission.response   UI -> security
    avatar.state          core -> avatar
    voice.transcript      voice -> core
    system.status         *    -> UI
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from aila.core.logging import get_logger

log = get_logger("event_bus")

Handler = Callable[["Event"], Awaitable[None]]


@dataclass(slots=True)
class Event:
    """Mensagem que trafega pelo barramento."""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class EventBus:
    """Pub/sub assíncrono, com suporte a wildcard ``*``."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Handler) -> None:
        """Inscreve um handler. Use ``"*"`` para receber todos os eventos."""
        self._subscribers[event_type].append(handler)
        log.debug(f"handler inscrito em '{event_type}'")

    def unsubscribe(self, event_type: str, handler: Handler) -> None:
        if handler in self._subscribers.get(event_type, []):
            self._subscribers[event_type].remove(handler)

    async def publish(self, event: Event) -> None:
        """Entrega o evento a todos os handlers relevantes, em paralelo."""
        handlers = list(self._subscribers.get(event.type, []))
        handlers += list(self._subscribers.get("*", []))
        if not handlers:
            return
        results = await asyncio.gather(
            *(self._safe_call(h, event) for h in handlers),
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, Exception):
                log.error(f"handler falhou em '{event.type}': {r!r}")

    async def emit(
        self, event_type: str, payload: dict[str, Any] | None = None, source: str = "core"
    ) -> None:
        """Atalho para criar e publicar um evento."""
        await self.publish(Event(type=event_type, payload=payload or {}, source=source))

    @staticmethod
    async def _safe_call(handler: Handler, event: Event) -> None:
        await handler(event)


# Instância global compartilhada pelo processo.
bus = EventBus()
