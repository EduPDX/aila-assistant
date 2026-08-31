"""Converte um GraphStore no payload que a UI do subconsciente consome
(nós + arestas + comunidades). Comunidade:
  - code      → pacote (2 primeiros segmentos do qualname): aila.core, aila.agents…
  - knowledge → o campo community do nó, senão o type.
Só metadados estruturais; nenhum conteúdo sensível.
"""

from __future__ import annotations

import hashlib
from typing import Any


def _community_of(node: dict[str, Any], kind: str) -> str:
    if kind == "code":
        q = (node.get("attrs") or {}).get("qualname") or node.get("label") or ""
        parts = str(q).split(".")
        return ".".join(parts[:2]) if len(parts) >= 2 else (parts[0] or "geral")
    return str(node.get("community") or node.get("type") or "geral")


def _knowledge_communities(nodes: list[dict], edges: list[dict]) -> tuple[dict[str, str], dict[str, str]]:
    """Comunidades determinísticas por componentes conectados.

    O Knowledge Graph não grava comunidades próprias. Agrupar só por ``type``
    fazia quase tudo cair em "concept". Aqui cada ilha conectada vira um tema,
    nomeado pelo seu nó mais central; isolados continuam agrupados por tipo.
    """
    by_id = {n["id"]: n for n in nodes}
    adj: dict[str, set[str]] = {nid: set() for nid in by_id}
    for edge in edges:
        a, b = edge["source"], edge["target"]
        if a in adj and b in adj:
            adj[a].add(b)
            adj[b].add(a)
    assignment: dict[str, str] = {}
    labels: dict[str, str] = {}
    seen: set[str] = set()
    for start in sorted(by_id):
        if start in seen:
            continue
        stack, component = [start], []
        seen.add(start)
        while stack:
            cur = stack.pop()
            component.append(cur)
            for nxt in adj[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        if len(component) == 1 and not adj[start]:
            typ = by_id[start].get("type") or "concept"
            cid, label = f"isolated:{typ}", "Conceitos isolados"
        else:
            hub = max(component, key=lambda nid: (
                len(adj[nid]), float(by_id[nid].get("importance") or 0),
                str(by_id[nid].get("label") or nid)))
            digest = hashlib.sha1("|".join(sorted(component)).encode()).hexdigest()[:8]
            cid, label = f"theme:{digest}", str(by_id[hub].get("label") or "Tema")
        labels[cid] = label
        assignment.update((nid, cid) for nid in component)
    return assignment, labels


def to_view(store, kind: str = "code", limit: int = 1500) -> dict[str, Any]:
    sub = store.subgraph(limit=limit)                 # {nodes, edges} (dicts)
    nodes, edges = sub["nodes"], sub["edges"]

    deg: dict[str, int] = {}
    for e in edges:
        deg[e["source"]] = deg.get(e["source"], 0) + 1
        deg[e["target"]] = deg.get(e["target"], 0) + 1

    knowledge_assignment, knowledge_labels = ({}, {})
    if kind == "knowledge":
        knowledge_assignment, knowledge_labels = _knowledge_communities(nodes, edges)
    comm_count: dict[str, int] = {}
    out_nodes = []
    for n in nodes:
        c = knowledge_assignment.get(n["id"]) if kind == "knowledge" else _community_of(n, kind)
        c = c or "geral"
        comm_count[c] = comm_count.get(c, 0) + 1
        out_nodes.append({
            "id": n["id"], "label": n.get("label") or n["id"], "type": n.get("type", ""),
            "community": c, "degree": deg.get(n["id"], 0),
            "importance": round(float(n.get("importance") or 0), 3),
            "confidence": round(float(n.get("confidence") or 0), 3),
        })

    node_ids = {n["id"] for n in out_nodes}
    out_edges = [
        {"source": e["source"], "target": e["target"], "relation": e.get("relation", ""),
         "weight": float(e.get("weight") or 1), "confidence": float(e.get("confidence") or 0)}
        for e in edges if e["source"] in node_ids and e["target"] in node_ids
    ]
    communities = sorted(
        ({"id": c, "label": knowledge_labels.get(c, c), "count": k} for c, k in comm_count.items()),
        key=lambda x: -x["count"],
    )
    return {
        "kind": kind, "nodes": out_nodes, "edges": out_edges, "communities": communities,
        "counts": {"nodes": len(out_nodes), "edges": len(out_edges),
                   "communities": len(communities),
                   "types": _count_by(out_nodes, "type"),
                   "relations": _count_by(out_edges, "relation")},
    }


def _count_by(items: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "—")
        counts[value] = counts.get(value, 0) + 1
    return counts
