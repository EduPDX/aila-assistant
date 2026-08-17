"""MemoryManager — fachada de memória MULTI-TIPO sobre o MemoryStore.

Tipos (coluna ``kind`` do store):
    episodic   — trocas de conversa / eventos (valor legado "chat").
    fact       — fatos de longo prazo (persistente).
    preference — preferências explícitas do usuário.
    project    — informações sobre o projeto.
    semantic   — conhecimento estruturado.

A memória de CURTO PRAZO é a janela de conversa (ConversationContext), não este
store persistente. Aqui ficam as memórias de longo prazo, recuperadas por
similaridade e/ou sempre injetadas (perfil do usuário).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aila.core.logging import get_logger

if TYPE_CHECKING:
    from aila.cognition.graph.graph_store import GraphStore
    from aila.memory.store import MemoryHit, MemoryStore

log = get_logger("memory")

EPISODIC = "chat"          # valor legado mantido (memórias antigas continuam válidas)
FACT = "fact"
PREFERENCE = "preference"
PROJECT = "project"
SEMANTIC = "semantic"

KINDS = {EPISODIC, FACT, PREFERENCE, PROJECT, SEMANTIC}
# conhecimento "durável" (peso alto na recuperação) vs episódico (contexto)
KNOWLEDGE = {FACT, PREFERENCE, PROJECT, SEMANTIC}
# sempre injetado no prompt (o agente "conhece" o usuário/projeto)
PROFILE = {PREFERENCE, PROJECT}


def normalize_kind(kind: str | None) -> str:
    k = (kind or FACT).lower().strip()
    if k in ("episodic", "conversation"):
        return EPISODIC
    if k in ("user", "pref", "preference"):
        return PREFERENCE
    return k if k in KINDS else FACT


class MemoryManager:
    def __init__(self, store: MemoryStore, graph: GraphStore | None = None) -> None:
        self.store = store
        self.graph = graph
        # retrieval HÍBRIDO quando há grafo; senão, o recall clássico (compat).
        self._retriever = None
        if graph is not None:
            from aila.cognition.memory.retrieval import HybridRetriever
            self._retriever = HybridRetriever(store, graph)

    async def save(self, text: str, kind: str = FACT, session_id: int | None = None) -> int:
        return await self.store.add(text, kind=normalize_kind(kind), session_id=session_id)

    async def remember_exchange(self, user_text: str, answer: str, session_id: int | None) -> int:
        """Grava a troca como memória episódica. Extrai entidades JÁ na gravação
        (heurística, offline, determinística) → o Knowledge Graph nunca nasce
        vazio. O engine refina com LLM depois, em background (qualidade melhor
        p/ prosa em PT) sem bloquear a resposta. Retorna o id da memória."""
        from aila.cognition.memory.entities import extract

        text = f"Usuário: {user_text}\nAila: {answer}"
        return await self.store.add(text, kind=EPISODIC, session_id=session_id,
                                    entities=extract(text))

    def forget(self, mem_id: int) -> None:
        self.store.delete(mem_id)

    async def recall(self, query: str, *, top_k: int = 4, min_score: float = 0.0,
                     context: dict | None = None) -> list[MemoryHit]:
        """Recuperação. Com grafo → HÍBRIDO (vetorial + entidades + traversal +
        re-rank, marca last_recalled sem reforçar). Sem grafo → multi-tipo
        (conhecimento durável primeiro, depois episódico) — comportamento legado."""
        if self._retriever is not None:
            return await self._retriever.retrieve(query, top_k=top_k, min_score=min_score,
                                                  context=context)
        know = await self.store.search(query, top_k=top_k, min_score=min_score, kinds=KNOWLEDGE)
        epi = await self.store.search(query, top_k=max(1, top_k // 2), min_score=min_score,
                                      kinds={EPISODIC})
        seen: set[int] = set()
        out = []
        for h in [*know, *epi]:
            if h.id not in seen:
                seen.add(h.id)
                out.append(h)
        return out

    def profile_block(self, limit: int = 8) -> str | None:
        """Bloco fixo de perfil (preferências + projeto) — sempre injetado."""
        rows: list[dict] = []
        for kind in PROFILE:
            rows.extend(self.store.by_kind(kind, limit))
        if not rows:
            return None
        linhas = "\n".join(f"- {r['text']}" for r in rows[:limit])
        return f"O que você sabe sobre o usuário/projeto:\n{linhas}"
