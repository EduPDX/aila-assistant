"""Modelos do grafo (nó e aresta) — servem tanto ao Knowledge Graph quanto ao
Code Graph (distinguidos pelo ``type`` do nó). Puramente dados."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


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
class GraphNode:
    id: str
    type: str                                       # user|person|project|concept|task|skill|tool|model|agent|file|function|...
    label: str
    attrs: dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5
    confidence: float = 1.0
    community: int | None = None
    created_at: str = ""
    updated_at: str = ""
    last_recalled: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> GraphNode:
        return cls(
            id=row["id"], type=row["type"], label=row.get("label", "") or "",
            attrs=_load(row.get("attrs"), {}),
            importance=float(row.get("importance") if row.get("importance") is not None else 0.5),
            confidence=float(row.get("confidence") if row.get("confidence") is not None else 1.0),
            community=row.get("community"),
            created_at=row.get("created_at", "") or "", updated_at=row.get("updated_at", "") or "",
            last_recalled=row.get("last_recalled"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "type": self.type, "label": self.label, "attrs": self.attrs,
            "importance": round(self.importance, 3), "confidence": round(self.confidence, 3),
            "community": self.community, "created_at": self.created_at,
            "updated_at": self.updated_at, "last_recalled": self.last_recalled,
        }


@dataclass(slots=True)
class GraphEdge:
    id: str
    source: str
    target: str
    relation: str                                   # prefers|works_on|uses|contains|imports|calls|relates_to|...
    confidence: float = 1.0
    weight: float = 1.0
    provenance: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> GraphEdge:
        return cls(
            id=row["id"], source=row["source"], target=row["target"],
            relation=row.get("relation", "") or "",
            confidence=float(row.get("confidence") if row.get("confidence") is not None else 1.0),
            weight=float(row.get("weight") if row.get("weight") is not None else 1.0),
            provenance=_load(row.get("provenance"), {}), created_at=row.get("created_at", "") or "",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "source": self.source, "target": self.target,
            "relation": self.relation, "confidence": round(self.confidence, 3),
            "weight": round(self.weight, 3), "provenance": self.provenance,
            "created_at": self.created_at,
        }
