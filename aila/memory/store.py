"""Armazenamento de memória de longo prazo com busca semântica.

Cada memória é um texto + seu embedding. A busca é por **similaridade de
cosseno** (numpy) sobre todos os vetores — brute-force, mais que suficiente
para uso local single-user (milhares de memórias em milissegundos).

A função de embedding é **injetada** (``embed_fn``), então este módulo não
depende do backend de LLM diretamente e pode ser testado com vetores falsos.

Embeddings são gravados como bytes float32 (compacto) no SQLite.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from aila.core.logging import get_logger

log = get_logger("memory")

# embed_fn: async (list[str]) -> list[list[float]]
EmbedFn = Callable[[list[str]], Awaitable[list[list[float]]]]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    text       TEXT NOT NULL,
    kind       TEXT NOT NULL DEFAULT 'chat',
    session_id INTEGER,
    dim        INTEGER NOT NULL,
    embedding  BLOB NOT NULL,
    created_at TEXT NOT NULL
);
"""


@dataclass(slots=True)
class MemoryHit:
    id: int
    text: str
    kind: str
    score: float
    created_at: str


class MemoryStore:
    def __init__(self, db_path: str | Path, embed_fn: EmbedFn) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.embed_fn = embed_fn
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()
        # cache do índice (id, texto, matriz normalizada) p/ busca rápida
        self._cache: tuple[list[int], list[str], list[str], np.ndarray] | None = None

    # ------------------------------------------------------------------ #
    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _normalize(v: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(v, axis=-1, keepdims=True)
        return v / np.clip(norm, 1e-8, None)

    def _invalidate(self) -> None:
        self._cache = None

    # ------------------------------------------------------------------ #
    async def add(self, text: str, kind: str = "chat", session_id: int | None = None) -> int:
        text = (text or "").strip()
        if not text:
            return -1
        vecs = await self.embed_fn([text])
        if not vecs:
            raise RuntimeError("embed_fn não retornou vetores")
        vec = np.asarray(vecs[0], dtype=np.float32)
        cur = self.conn.execute(
            "INSERT INTO memories (text, kind, session_id, dim, embedding, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (text, kind, session_id, len(vec), vec.tobytes(), self._now()),
        )
        self.conn.commit()
        self._invalidate()
        return int(cur.lastrowid)

    def _load_matrix(self) -> tuple[list[int], list[str], list[str], np.ndarray] | None:
        if self._cache is not None:
            return self._cache
        rows = self.conn.execute(
            "SELECT id, text, kind, dim, embedding FROM memories"
        ).fetchall()
        if not rows:
            return None
        ids, texts, kinds, vectors = [], [], [], []
        for r in rows:
            ids.append(r["id"])
            texts.append(r["text"])
            kinds.append(r["kind"])
            vectors.append(np.frombuffer(r["embedding"], dtype=np.float32))
        matrix = self._normalize(np.vstack(vectors))
        self._cache = (ids, texts, kinds, matrix)
        return self._cache

    async def search(
        self, query: str, top_k: int = 4, min_score: float = 0.0,
        kinds: set[str] | None = None,
    ) -> list[MemoryHit]:
        loaded = self._load_matrix()
        if loaded is None:
            return []
        ids, texts, kind_arr, matrix = loaded
        qvecs = await self.embed_fn([query])
        if not qvecs:
            return []
        q = self._normalize(np.asarray(qvecs[0], dtype=np.float32).reshape(1, -1))[0]
        scores = matrix @ q  # cosseno (vetores já normalizados)
        order = np.argsort(scores)[::-1]   # todos, desc — filtramos por kind depois
        hits: list[MemoryHit] = []
        for i in order:
            if len(hits) >= top_k:
                break
            score = float(scores[i])
            if score < min_score:
                break                       # ordenado desc: os próximos são menores
            if kinds and kind_arr[i] not in kinds:
                continue
            hits.append(
                MemoryHit(id=ids[i], text=texts[i], kind=kind_arr[i], score=score,
                          created_at="")
            )
        return hits

    def delete(self, mem_id: int) -> None:
        self.conn.execute("DELETE FROM memories WHERE id = ?", (mem_id,))
        self.conn.commit()
        self._invalidate()

    async def update(self, mem_id: int, text: str) -> None:
        """Edita o texto de uma memória e reembeda."""
        text = (text or "").strip()
        if not text:
            return
        vecs = await self.embed_fn([text])
        vec = np.asarray(vecs[0], dtype=np.float32)
        self.conn.execute(
            "UPDATE memories SET text = ?, embedding = ?, dim = ? WHERE id = ?",
            (text, vec.tobytes(), len(vec), mem_id),
        )
        self.conn.commit()
        self._invalidate()

    def by_kind(self, kind: str, n: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, text, kind, created_at FROM memories WHERE kind = ? "
            "ORDER BY id DESC LIMIT ?",
            (kind, n),
        ).fetchall()
        return [dict(r) for r in rows]

    def recent(self, n: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, text, kind, created_at FROM memories ORDER BY id DESC LIMIT ?",
            (n,),
        ).fetchall()
        return [dict(r) for r in rows]

    def count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0])

    def clear(self) -> None:
        self.conn.execute("DELETE FROM memories")
        self.conn.commit()
        self._invalidate()

    def close(self) -> None:
        self.conn.close()
