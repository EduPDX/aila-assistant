"""Modelo cognitivo de memória (Fase 1).

Representação rica de uma memória, sobre o schema estendido do MemoryStore.
Mantém compat com a memória atual: o "type" cognitivo É a coluna ``kind`` do
store (não duplicamos). Os EPISODIC == "chat" (valor legado preservado).

Três sinais INDEPENDENTES (ajuste v2 — não misturar):
  * confidence    — quão CONFIÁVEL é a informação (0..1)
  * importance    — quão RELEVANTE para a Aila (0..1)
  * reinforcement — nº de CONFIRMAÇÕES/evidências; sobe SÓ com evidência nova ou
                    confirmação explícita do usuário, NUNCA por ser recuperada.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# Tipos cognitivos == coluna `kind` do store (sem duplicação).
EPISODIC = "chat"          # troca de conversa / evento (valor legado)
SEMANTIC = "semantic"      # conhecimento estruturado
PROCEDURAL = "procedural"  # como fazer algo (skills/procedimentos)
FACT = "fact"              # fato de longo prazo
PREFERENCE = "preference"  # preferência explícita do usuário
PROJECT = "project"        # informação sobre um projeto
TYPES = {EPISODIC, SEMANTIC, PROCEDURAL, FACT, PREFERENCE, PROJECT}


def _load(value: Any, default: Any) -> Any:
    if not value:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return default


@dataclass(slots=True)
class Memory:
    """Uma memória com metadados cognitivos. Construir com ``Memory.from_row``
    a partir de ``MemoryStore.get(id)``."""

    id: int
    content: str
    kind: str = FACT                                   # == coluna `kind` (o "type")
    source: str | None = None                          # user | web | tool:<n> | consolidation | code
    confidence: float = 1.0
    importance: float = 0.5
    reinforcement: int = 0
    entities: list[str] = field(default_factory=list)  # ids de nós do Knowledge Graph
    evidence: list[int] = field(default_factory=list)  # ids de memórias/eventos de suporte
    provenance: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    last_recalled: str | None = None
    expiration: str | None = None
    status: str = "active"                             # active | archived | superseded
    session_id: int | None = None

    @property
    def type(self) -> str:
        """Alias legível: o 'type' cognitivo é o ``kind``."""
        return self.kind

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Memory:
        return cls(
            id=row["id"],
            content=row.get("text", "") or "",
            kind=row.get("kind", FACT) or FACT,
            source=row.get("source"),
            confidence=float(row.get("confidence") if row.get("confidence") is not None else 1.0),
            importance=float(row.get("importance") if row.get("importance") is not None else 0.5),
            reinforcement=int(row.get("reinforcement") or 0),
            entities=_load(row.get("entities"), []),
            evidence=_load(row.get("evidence"), []),
            provenance=_load(row.get("provenance"), {}),
            created_at=row.get("created_at", "") or "",
            last_recalled=row.get("last_recalled"),
            expiration=row.get("expiration"),
            status=row.get("status", "active") or "active",
            session_id=row.get("session_id"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.kind,
            "content": self.content,
            "source": self.source,
            "confidence": round(self.confidence, 3),
            "importance": round(self.importance, 3),
            "reinforcement": self.reinforcement,
            "entities": self.entities,
            "evidence": self.evidence,
            "provenance": self.provenance,
            "created_at": self.created_at,
            "last_recalled": self.last_recalled,
            "expiration": self.expiration,
            "status": self.status,
            "session_id": self.session_id,
        }
