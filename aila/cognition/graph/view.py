"""Converte um GraphStore no payload que a UI do subconsciente consome
(nós + arestas + comunidades). Comunidade:
  - code      → pacote (2 primeiros segmentos do qualname): aila.core, aila.agents…
  - knowledge → o campo community do nó, senão o type.
Só metadados estruturais; nenhum conteúdo sensível.
"""

from __future__ import annotations

from typing import Any


def _community_of(node: dict[str, Any], kind: str) -> str:
    if kind == "code":
        q = (node.get("attrs") or {}).get("qualname") or node.get("label") or ""
        parts = str(q).split(".")
        return ".".join(parts[:2]) if len(parts) >= 2 else (parts[0] or "geral")
    return str(node.get("community") or node.get("type") or "geral")


def to_view(store, kind: str = "code", limit: int = 1500) -> dict[str, Any]:
    sub = store.subgraph(limit=limit)                 # {nodes, edges} (dicts)
    nodes, edges = sub["nodes"], sub["edges"]

    deg: dict[str, int] = {}
    for e in edges:
        deg[e["source"]] = deg.get(e["source"], 0) + 1
        deg[e["target"]] = deg.get(e["target"], 0) + 1

    comm_count: dict[str, int] = {}
    out_nodes = []
    for n in nodes:
        c = _community_of(n, kind)
        comm_count[c] = comm_count.get(c, 0) + 1
        out_nodes.append({
            "id": n["id"], "label": n.get("label") or n["id"], "type": n.get("type", ""),
            "community": c, "degree": deg.get(n["id"], 0),
        })

    node_ids = {n["id"] for n in out_nodes}
    out_edges = [
        {"source": e["source"], "target": e["target"], "relation": e.get("relation", "")}
        for e in edges if e["source"] in node_ids and e["target"] in node_ids
    ]
    communities = sorted(
        ({"id": c, "label": c, "count": k} for c, k in comm_count.items()),
        key=lambda x: -x["count"],
    )
    return {
        "kind": kind, "nodes": out_nodes, "edges": out_edges, "communities": communities,
        "counts": {"nodes": len(out_nodes), "edges": len(out_edges),
                   "communities": len(communities)},
    }
