"""Retrieval híbrido (Fase 3).

Combina, em vez de só top-k vetorial:
  1. VETORIAL   — similaridade de cosseno (MemoryStore.search).
  2. ENTIDADES  — nós do Knowledge Graph cujo label aparece na query.
  3. TRAVERSAL  — vizinhança (k-hop) das entidades → nós relacionados.
  4. LIGAÇÃO    — memórias ligadas a esses nós (coluna `entities`).
  5. RE-RANK    — fusão ponderada: vetorial + proximidade no grafo + sinais
                  (importance, confidence). Query nomeia UMA coisa → o grafo
                  traz as RELACIONADAS.
  6. Marca last_recalled — RECALL NÃO REFORÇA (ajuste v2).

Degrada com elegância: sem grafo (ou grafo vazio), vira top-k vetorial + sinais.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from aila.memory.store import MemoryHit

if TYPE_CHECKING:
    from aila.cognition.graph.graph_store import GraphStore
    from aila.memory.store import MemoryStore

# pesos da fusão (vetorial domina; grafo desempata/expande; sinais ajustam)
_W_VEC, _W_GRAPH, _W_IMP, _W_CONF = 0.55, 0.30, 0.10, 0.05


def _entities_of(row: dict[str, Any]) -> set[str]:
    v = row.get("entities")
    if not v:
        return set()
    if isinstance(v, list):
        return set(v)
    try:
        return set(json.loads(v))
    except (ValueError, TypeError):
        return set()


class HybridRetriever:
    def __init__(self, store: MemoryStore, graph: GraphStore | None = None) -> None:
        self.store = store
        self.graph = graph

    async def retrieve(
        self, query: str, *, top_k: int = 6, min_score: float = 0.0,
        context: dict | None = None,
    ) -> list[MemoryHit]:
        # 1) vetorial (over-fetch para o re-rank ter material)
        vec = await self.store.search(query, top_k=top_k * 3, min_score=min_score)
        vec_score = {h.id: h.score for h in vec}

        # 2-3) entidades da query + vizinhança no grafo
        ent_ids: list[str] = []
        neigh: set[str] = set()
        if self.graph is not None:
            ent_ids = self.graph.match_entities(query)
            for e in ent_ids:
                nb = self.graph.neighborhood(e, depth=1)
                neigh |= {n["id"] for n in nb["nodes"]}
            neigh -= set(ent_ids)

        # 4) memórias ligadas às entidades/vizinhos
        linked = set(ent_ids) | neigh
        graph_rows = self.store.by_entities(list(linked)) if linked else []

        # pool de candidatos (vetorial ∪ grafo), enriquecido com sinais
        pool: dict[int, dict] = {}
        for h in vec:
            pool[h.id] = self.store.get(h.id) or {
                "id": h.id, "text": h.text, "kind": h.kind, "created_at": h.created_at,
            }
        for r in graph_rows:
            pool.setdefault(r["id"], r)

        # 5) fusão + re-rank
        ent_set, neigh_set = set(ent_ids), neigh
        ctx_ents = set((context or {}).get("entities", []))
        scored: list[tuple[float, int, dict]] = []
        whys: dict[int, dict] = {}              # decomposição p/ observabilidade (subconsciente/Inspector)
        for mid, row in pool.items():
            ents = _entities_of(row)
            gscore = 1.0 if (ent_set & ents) else (0.6 if (neigh_set & ents) else 0.0)
            imp = float(row.get("importance") if row.get("importance") is not None else 0.5)
            conf = float(row.get("confidence") if row.get("confidence") is not None else 1.0)
            vec_c = _W_VEC * vec_score.get(mid, 0.0)
            graph_c = _W_GRAPH * gscore
            ctx_c = 0.1 if (ctx_ents & ents) else 0.0    # bônus de contexto (projeto/tarefa atual)
            sig_c = _W_IMP * imp + _W_CONF * conf
            final = vec_c + graph_c + ctx_c + sig_c
            if row.get("status") in ("archived", "superseded"):
                final -= 0.5                    # desprioriza memórias aposentadas
            comps = {"vec": round(vec_c, 3), "graph": round(graph_c, 3),
                     "ctx": round(ctx_c, 3), "signals": round(sig_c, 3)}
            # driver = por que ESTA memória subiu (o maior contribuinte do score)
            whys[mid] = {**comps, "driver": max(comps, key=lambda k: comps[k])}
            scored.append((final, mid, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        # 6) marca last_recalled — NÃO reforça (ajuste v2)
        self.store.mark_recalled([mid for _f, mid, _r in top])

        return [
            MemoryHit(
                id=mid, text=row.get("text", "") or "", kind=row.get("kind", "fact") or "fact",
                score=round(f, 4), created_at=row.get("created_at", "") or "",
                importance=float(row.get("importance") if row.get("importance") is not None else 0.5),
                confidence=float(row.get("confidence") if row.get("confidence") is not None else 1.0),
                why=whys.get(mid),
            )
            for f, mid, row in top
        ]
