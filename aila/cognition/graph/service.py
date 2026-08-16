"""Serviço de grafos p/ a UI do subconsciente (lazy, cacheado).

Dois grafos (ajuste v2: relacionados, não fundidos):
  - code      → Code Graph da própria Aila (real; construído sob demanda em
                data/code_graph.db a partir de aila/).
  - knowledge → Knowledge Graph do que a Aila aprende das conversas (populado
                pela consolidação; pode começar vazio até ela ser plugada).

Não instancia nada no import — só quando /api/graph é chamado a 1ª vez.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aila.core.logging import get_logger

if TYPE_CHECKING:
    from aila.cognition.graph.graph_store import GraphStore

log = get_logger("graph_service")


class GraphService:
    def __init__(self) -> None:
        self._code: GraphStore | None = None
        self._know: GraphStore | None = None

    def code_store(self) -> GraphStore:
        if self._code is None:
            from aila.cognition.graph import CodeGraph, GraphStore
            from aila.core.config import PROJECT_ROOT, data_path

            st = GraphStore(data_path("code_graph.db"))
            if st.counts()["nodes"] == 0:
                rep = CodeGraph(st, PROJECT_ROOT).build(subdir="aila")
                log.info(f"code graph construído p/ a UI: {rep}")
            st.recompute_importance()   # importância=grau → a amostra do mini pega os hubs
            self._code = st
        return self._code

    def knowledge_store(self) -> GraphStore:
        if self._know is None:
            from aila.cognition.graph import GraphStore
            from aila.core.config import data_path

            self._know = GraphStore(data_path("knowledge.db"))
        return self._know

    def view(self, kind: str = "code", limit: int = 1500) -> dict[str, Any]:
        from aila.cognition.graph.view import to_view

        store = self.knowledge_store() if kind == "knowledge" else self.code_store()
        return to_view(store, "knowledge" if kind == "knowledge" else "code", limit)


_service: GraphService | None = None


def get_service() -> GraphService:
    global _service
    if _service is None:
        _service = GraphService()
    return _service
