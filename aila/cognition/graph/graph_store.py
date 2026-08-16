"""GraphStore — motor de grafo nativo e leve (SQLite + índice de adjacência em
RAM). Serve ao Knowledge Graph e ao Code Graph (distinguidos pelo ``type`` dos
nós). Sem dependência externa (sem networkx): mantemos as deps mínimas e o bundle
leve. Grafos single-user são pequenos → BFS em dicts é instantâneo.

Persistência: tabelas ``kg_node``/``kg_edge`` (arestas DIRECIONADAS, únicas por
(source,target,relation)). Índice em RAM (``_out``/``_in``) é construído lazy e
mantido incremental em cada upsert/delete → traversal/vizinhança/caminho O(vizinhos).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aila.cognition.graph.models import GraphEdge, GraphNode
from aila.core.logging import get_logger

log = get_logger("graph")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS kg_node (
    id            TEXT PRIMARY KEY,
    type          TEXT NOT NULL,
    label         TEXT NOT NULL,
    attrs         TEXT,
    importance    REAL DEFAULT 0.5,
    confidence    REAL DEFAULT 1.0,
    community     INTEGER,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    last_recalled TEXT
);
CREATE TABLE IF NOT EXISTS kg_edge (
    id         TEXT PRIMARY KEY,
    source     TEXT NOT NULL,
    target     TEXT NOT NULL,
    relation   TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    weight     REAL DEFAULT 1.0,
    provenance TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(source, target, relation)
);
CREATE INDEX IF NOT EXISTS idx_edge_source ON kg_edge(source);
CREATE INDEX IF NOT EXISTS idx_edge_target ON kg_edge(target);
CREATE INDEX IF NOT EXISTS idx_node_type   ON kg_node(type);
"""

_NODE_COLS = "id, type, label, attrs, importance, confidence, community, created_at, updated_at, last_recalled"
_EDGE_COLS = "id, source, target, relation, confidence, weight, provenance, created_at"


def edge_id(source: str, target: str, relation: str) -> str:
    """Id determinístico da aresta → upsert idempotente."""
    return hashlib.sha1(f"{source}|{relation}|{target}".encode()).hexdigest()[:16]


def _dump(v: Any) -> str | None:
    return None if v is None else json.dumps(v, ensure_ascii=False)


class GraphStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)            # não usar `self.path` (colide c/ o método path())
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()
        # índice de adjacência em RAM: node -> [(neighbor, relation, weight, edge_id)]
        self._out: dict[str, list[tuple[str, str, float, str]]] = {}
        self._in: dict[str, list[tuple[str, str, float, str]]] = {}
        self._loaded = False

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    # ------------------------------------------------------------------ #
    def _ensure_index(self) -> None:
        if self._loaded:
            return
        self._out.clear(); self._in.clear()
        for r in self.conn.execute("SELECT source, target, relation, weight, id FROM kg_edge"):
            self._add_adj(r["source"], r["target"], r["relation"], r["weight"], r["id"])
        self._loaded = True

    def _add_adj(self, src: str, tgt: str, rel: str, w: float, eid: str) -> None:
        self._out.setdefault(src, []).append((tgt, rel, w, eid))
        self._in.setdefault(tgt, []).append((src, rel, w, eid))

    def _edges_of(self, node: str, direction: str) -> list[tuple[str, str, float, str]]:
        """Vizinhos de um nó. direction: 'out' | 'in' | 'both'."""
        out = self._out.get(node, []) if direction in ("out", "both") else []
        inc = self._in.get(node, []) if direction in ("in", "both") else []
        return out + inc

    # --------------------------- upsert -------------------------------- #
    def upsert_node(
        self, node_id: str, type: str, label: str, *, attrs: dict | None = None,
        importance: float | None = None, confidence: float | None = None,
    ) -> str:
        """Cria ou atualiza um nó (preserva created_at; atualiza updated_at)."""
        now = self._now()
        existing = self.conn.execute("SELECT id FROM kg_node WHERE id = ?", (node_id,)).fetchone()
        if existing:
            sets, vals = ["label = ?", "type = ?", "updated_at = ?"], [label, type, now]
            if attrs is not None: sets.append("attrs = ?"); vals.append(_dump(attrs))
            if importance is not None: sets.append("importance = ?"); vals.append(importance)
            if confidence is not None: sets.append("confidence = ?"); vals.append(confidence)
            vals.append(node_id)
            self.conn.execute(f"UPDATE kg_node SET {', '.join(sets)} WHERE id = ?", vals)
        else:
            self.conn.execute(
                "INSERT INTO kg_node (id, type, label, attrs, importance, confidence, "
                "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (node_id, type, label, _dump(attrs or {}),
                 importance if importance is not None else 0.5,
                 confidence if confidence is not None else 1.0, now, now),
            )
        self.conn.commit()
        return node_id

    def upsert_edge(
        self, source: str, target: str, relation: str, *,
        confidence: float = 1.0, weight: float = 1.0, provenance: dict | None = None,
    ) -> str:
        """Cria ou reforça uma aresta (única por source/target/relation)."""
        eid = edge_id(source, target, relation)
        now = self._now()
        self.conn.execute(
            "INSERT INTO kg_edge (id, source, target, relation, confidence, weight, provenance, created_at) "
            "VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(source, target, relation) DO UPDATE SET "
            "confidence = excluded.confidence, weight = excluded.weight, "
            "provenance = COALESCE(excluded.provenance, kg_edge.provenance)",
            (eid, source, target, relation, confidence, weight, _dump(provenance), now),
        )
        self.conn.commit()
        if self._loaded:                      # mantém o índice incremental
            self._out.setdefault(source, []); self._in.setdefault(target, [])
            if not any(e[3] == eid for e in self._out[source]):
                self._add_adj(source, target, relation, weight, eid)
        return eid

    # ----------------------------- leitura ----------------------------- #
    def get_node(self, node_id: str) -> GraphNode | None:
        r = self.conn.execute(f"SELECT {_NODE_COLS} FROM kg_node WHERE id = ?", (node_id,)).fetchone()
        return GraphNode.from_row(dict(r)) if r else None

    def get_edge(self, eid: str) -> GraphEdge | None:
        r = self.conn.execute(f"SELECT {_EDGE_COLS} FROM kg_edge WHERE id = ?", (eid,)).fetchone()
        return GraphEdge.from_row(dict(r)) if r else None

    def neighborhood(self, node_id: str, depth: int = 1, direction: str = "both") -> dict[str, list]:
        """Subgrafo em torno de um nó (BFS até `depth`). Retorna {nodes, edges} (dicts)."""
        self._ensure_index()
        visited = {node_id}
        frontier = {node_id}
        edge_ids: set[str] = set()
        for _ in range(max(1, depth)):
            nxt: set[str] = set()
            for n in frontier:
                for (m, _rel, _w, eid) in self._edges_of(n, direction):
                    edge_ids.add(eid)
                    if m not in visited:
                        visited.add(m); nxt.add(m)
            frontier = nxt
            if not frontier:
                break
        nodes = [n.to_dict() for i in visited if (n := self.get_node(i))]
        edges = [e.to_dict() for eid in edge_ids if (e := self.get_edge(eid))]
        return {"nodes": nodes, "edges": edges}

    def path(self, source: str, target: str, max_depth: int = 6) -> list[str]:
        """Menor caminho (BFS) source→target (ignora direção). [] se não houver."""
        self._ensure_index()
        if source == target:
            return [source]
        prev: dict[str, str | None] = {source: None}
        frontier = [source]
        for _ in range(max_depth):
            nxt: list[str] = []
            for n in frontier:
                for (m, _rel, _w, _eid) in self._edges_of(n, "both"):
                    if m not in prev:
                        prev[m] = n
                        if m == target:
                            out = [m]
                            while prev[out[-1]] is not None:
                                out.append(prev[out[-1]])  # type: ignore[arg-type]
                            return list(reversed(out))
                        nxt.append(m)
            frontier = nxt
            if not frontier:
                break
        return []

    def match_entities(self, text: str, limit: int = 20) -> list[str]:
        """Ids de nós cujo ``label`` aparece no texto (case-insensitive). Labels
        mais LONGOS (mais específicos) primeiro. Base leve p/ o retrieval híbrido."""
        t = (text or "").lower()
        if not t:
            return []
        matched = [(r["id"], r["label"]) for r in
                   self.conn.execute("SELECT id, label FROM kg_node")
                   if r["label"] and r["label"].lower() in t]
        matched.sort(key=lambda il: len(il[1]), reverse=True)
        return [i for i, _l in matched[:limit]]

    def related(self, node_id: str, limit: int = 10) -> list[dict]:
        """Vizinhos diretos ordenados por peso da aresta (desc)."""
        self._ensure_index()
        seen: dict[str, float] = {}
        for (m, _rel, w, _eid) in self._edges_of(node_id, "both"):
            seen[m] = max(seen.get(m, 0.0), w)
        top = sorted(seen.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        return [n.to_dict() for nid, _w in top if (n := self.get_node(nid))]

    def subgraph(self, *, focus: str | None = None, depth: int = 2, types: set[str] | None = None,
                 limit: int = 300) -> dict[str, list]:
        """Subgrafo p/ a UI: em torno de `focus` (se dado) ou o grafo todo (limitado)."""
        if focus:
            return self.neighborhood(focus, depth=depth)
        q = f"SELECT {_NODE_COLS} FROM kg_node"
        if types:
            marks = ",".join("?" * len(types))
            rows = self.conn.execute(f"{q} WHERE type IN ({marks}) LIMIT ?", (*types, limit)).fetchall()
        else:
            rows = self.conn.execute(f"{q} ORDER BY importance DESC LIMIT ?", (limit,)).fetchall()
        nodes = [GraphNode.from_row(dict(r)).to_dict() for r in rows]
        ids = {n["id"] for n in nodes}
        erows = self.conn.execute(f"SELECT {_EDGE_COLS} FROM kg_edge").fetchall()
        edges = [GraphEdge.from_row(dict(r)).to_dict() for r in erows
                 if r["source"] in ids and r["target"] in ids]
        return {"nodes": nodes, "edges": edges}

    # ----------------------------- escrita ----------------------------- #
    def touch(self, node_id: str) -> None:
        """Marca last_recalled do nó (não altera importance — sinais independentes)."""
        self.conn.execute("UPDATE kg_node SET last_recalled = ? WHERE id = ?", (self._now(), node_id))
        self.conn.commit()

    def delete_node(self, node_id: str) -> None:
        self.conn.execute("DELETE FROM kg_node WHERE id = ?", (node_id,))
        self.conn.execute("DELETE FROM kg_edge WHERE source = ? OR target = ?", (node_id, node_id))
        self.conn.commit()
        self._loaded = False        # reconstrói o índice na próxima consulta

    def counts(self) -> dict[str, Any]:
        n = self.conn.execute("SELECT COUNT(*) FROM kg_node").fetchone()[0]
        e = self.conn.execute("SELECT COUNT(*) FROM kg_edge").fetchone()[0]
        by_type = {r["type"]: r["c"] for r in
                   self.conn.execute("SELECT type, COUNT(*) c FROM kg_node GROUP BY type")}
        return {"nodes": int(n), "edges": int(e), "by_type": by_type}

    def close(self) -> None:
        self.conn.close()
