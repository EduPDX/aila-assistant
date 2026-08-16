"""Consolidação de memória — o "dreaming" (Fase 4), CONSERVADOR (ajuste v2).

A Aila NÃO "decide o que é verdade". O processo é determinístico e baseado em
EVIDÊNCIA; roda como background task em ociosidade (ou sob demanda), com budget.

Pipeline:
  1. DECAY      — arquiva memórias ativas com `expiration` vencida (nunca apaga).
  2. DEDUP      — funde quase-duplicatas (cosseno alto, mesmo kind): elege uma
                  canônica (mais reforçada/antiga), aposenta as outras (superseded),
                  anexa-as como `evidence[]` e reforça a canônica (cada duplicata é
                  UMA evidência — reforço só com evidência, ajuste v2).
  3. GRAFO      — de entidades co-ocorrentes nas memórias: cria nós; cria arestas
                  `relates_to` SÓ quando a co-ocorrência atinge `min_evidence`
                  (hipótese vira aresta apenas COM evidência), com provenance.
  4. IMPORTÂNCIA— recalcula (grau normalizado) no grafo.
  5. EVENTOS    — memory.consolidated / graph.updated (auditável).

Um hook LLM (``propose_fn``) fica reservado p/ propor hipóteses adicionais no
futuro — sempre passando pelo mesmo crivo de evidência. Não é necessário aqui.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from itertools import combinations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aila.cognition.graph.graph_store import GraphStore
    from aila.core.event_bus import EventBus
    from aila.memory.store import MemoryStore

from aila.core.logging import get_logger

log = get_logger("consolidation")


class Consolidator:
    def __init__(
        self, store: MemoryStore, graph: GraphStore, bus: EventBus | None = None, *,
        dup_threshold: float = 0.92, min_evidence: int = 2,
    ) -> None:
        self.store = store
        self.graph = graph
        self.bus = bus
        self.dup_threshold = dup_threshold
        self.min_evidence = min_evidence

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    async def consolidate(self, *, limit: int = 500) -> dict[str, Any]:
        report = {"archived": 0, "merged": 0, "nodes": 0, "edges": 0}
        report["archived"] = self.store.archive_expired(self._now())
        report["merged"] = self._dedup()
        report["nodes"], report["edges"] = self._build_graph(limit)
        self.graph.recompute_importance()
        if self.bus is not None:
            try:
                await self.bus.emit("memory.consolidated", dict(report), source="consolidation")
                await self.bus.emit("graph.updated", self.graph.counts(), source="consolidation")
            except Exception as exc:  # noqa: BLE001 - o bus nunca deve quebrar a consolidação
                log.warning(f"bus falhou na consolidação: {exc!r}")
        log.info(f"consolidação: {report}")
        return report

    # ------------------------------------------------------------------ #
    def _dedup(self) -> int:
        """Funde quase-duplicatas (mesmo kind, cosseno ≥ threshold)."""
        ids, kinds, reinf, mat = self.store.vectors("active")
        if mat is None or len(ids) < 2:
            return 0
        sim = mat @ mat.T
        n = len(ids)
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for i in range(n):
            for j in range(i + 1, n):
                if kinds[i] == kinds[j] and float(sim[i, j]) >= self.dup_threshold:
                    parent[find(j)] = find(i)

        clusters: dict[int, list[int]] = defaultdict(list)
        for i in range(n):
            clusters[find(i)].append(i)

        merged = 0
        for members in clusters.values():
            if len(members) < 2:
                continue
            # canônica = mais reforçada, depois mais antiga (menor id)
            members.sort(key=lambda k: (-reinf[k], ids[k]))
            canon, dups = members[0], members[1:]
            dup_ids = [ids[d] for d in dups]
            self.store.add_evidence(ids[canon], dup_ids)
            self.store.reinforce(ids[canon], len(dups))      # evidência ⇒ reforço
            for d in dups:
                self.store.supersede(ids[d])                 # aposenta (não apaga)
            merged += len(dups)
        return merged

    def _build_graph(self, limit: int) -> tuple[int, int]:
        """Cria nós (entidades observadas) e arestas relates_to (co-ocorrência ≥
        min_evidence). Hipótese vira aresta apenas COM evidência."""
        rows = self.store.active_with_entities(limit)
        ent_count: Counter = Counter()
        cooc: Counter = Counter()
        prov: dict[tuple[str, str], list[int]] = defaultdict(list)
        for r in rows:
            try:
                ents = sorted(set(json.loads(r["entities"]) or []))
            except (ValueError, TypeError):
                ents = []
            for a in ents:
                ent_count[a] += 1
            for a, b in combinations(ents, 2):
                cooc[(a, b)] += 1
                prov[(a, b)].append(r["id"])

        for ent in ent_count:
            typ = "user" if str(ent).lower() == "user" else "concept"
            self.graph.upsert_node(str(ent), typ, str(ent))

        edges = 0
        for (a, b), cnt in cooc.items():
            if cnt >= self.min_evidence:
                self.graph.upsert_edge(
                    a, b, "relates_to", weight=float(cnt),
                    confidence=min(1.0, 0.5 + 0.1 * cnt),
                    provenance={"cooccurrence": cnt, "evidence": prov[(a, b)][:10]},
                )
                edges += 1
        return len(ent_count), edges
