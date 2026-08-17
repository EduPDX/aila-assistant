"""Armazenamento de memória de longo prazo com busca semântica.

Cada memória é um texto + seu embedding. A busca é por **similaridade de
cosseno** (numpy) sobre todos os vetores — brute-force, mais que suficiente
para uso local single-user (milhares de memórias em milissegundos).

A função de embedding é **injetada** (``embed_fn``), então este módulo não
depende do backend de LLM diretamente e pode ser testado com vetores falsos.

Embeddings são gravados como bytes float32 (compacto) no SQLite.
"""

from __future__ import annotations

import json
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

# Colunas COGNITIVAS (Fase 1) — adicionadas por migração ADITIVA (ALTER TABLE)
# para não quebrar bancos existentes. `kind` continua sendo o "type" cognitivo
# (não duplicamos com uma coluna `type`). Três sinais INDEPENDENTES (ajuste v2):
# confidence (confiável?) · importance (relevante?) · reinforcement (confirmado?).
_COGNITIVE_COLUMNS: list[tuple[str, str]] = [
    ("source", "TEXT"),                        # user | web | tool:<name> | consolidation | code
    ("provenance", "TEXT"),                    # JSON {origin, url?, tool?, session_id, ...}
    ("entities", "TEXT"),                      # JSON[] — ids de nós do Knowledge Graph
    ("evidence", "TEXT"),                      # JSON[] — ids de memórias/eventos de suporte
    ("confidence", "REAL DEFAULT 1.0"),        # 0..1
    ("importance", "REAL DEFAULT 0.5"),        # 0..1
    ("reinforcement", "INTEGER DEFAULT 0"),    # sobe só com evidência nova / confirmação
    ("last_recalled", "TEXT"),                 # atualizado no recall — recall NÃO reforça
    ("expiration", "TEXT"),                    # decay p/ fatos temporários
    ("status", "TEXT DEFAULT 'active'"),       # active | archived | superseded
]


def _dump(value: object) -> str | None:
    """Serializa listas/dicts para JSON (ou None)."""
    return None if value is None else json.dumps(value, ensure_ascii=False)


@dataclass(slots=True)
class MemoryHit:
    id: int
    text: str
    kind: str
    score: float
    created_at: str
    importance: float = 0.5     # sinais cognitivos (preenchidos pelo retrieval híbrido)
    confidence: float = 1.0


class MemoryStore:
    def __init__(self, db_path: str | Path, embed_fn: EmbedFn) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.embed_fn = embed_fn
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self._migrate()                 # adiciona colunas cognitivas se faltarem (aditivo)
        self.conn.commit()
        # cache do índice (id, texto, matriz normalizada) p/ busca rápida
        self._cache: tuple[list[int], list[str], list[str], np.ndarray] | None = None

    def _migrate(self) -> None:
        """Migração aditiva idempotente: cria as colunas cognitivas que faltam.
        Bancos antigos (só as 7 colunas base) ganham as novas com DEFAULT — as
        memórias existentes continuam válidas."""
        existing = {r[1] for r in self.conn.execute("PRAGMA table_info(memories)").fetchall()}
        for name, decl in _COGNITIVE_COLUMNS:
            if name not in existing:
                self.conn.execute(f"ALTER TABLE memories ADD COLUMN {name} {decl}")

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
    async def add(
        self, text: str, kind: str = "chat", session_id: int | None = None, *,
        source: str | None = None, confidence: float = 1.0, importance: float = 0.5,
        provenance: dict | None = None, entities: list | None = None,
        evidence: list | None = None, expiration: str | None = None,
        status: str = "active",
    ) -> int:
        """Grava uma memória. Os metadados cognitivos são opcionais (defaults),
        então chamadas antigas ``add(text, kind, session_id)`` seguem idênticas."""
        text = (text or "").strip()
        if not text:
            return -1
        vecs = await self.embed_fn([text])
        if not vecs:
            raise RuntimeError("embed_fn não retornou vetores")
        vec = np.asarray(vecs[0], dtype=np.float32)
        cur = self.conn.execute(
            "INSERT INTO memories (text, kind, session_id, dim, embedding, created_at, "
            "source, confidence, importance, reinforcement, provenance, entities, evidence, "
            "expiration, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (text, kind, session_id, len(vec), vec.tobytes(), self._now(),
             source, confidence, importance, 0, _dump(provenance), _dump(entities),
             _dump(evidence), expiration, status),
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

    def set_entities(self, mem_id: int, entities: list) -> None:
        self.conn.execute("UPDATE memories SET entities = ? WHERE id = ?",
                          (_dump(entities), int(mem_id)))
        self.conn.commit()

    def recent_empty_entities(self, limit: int = 8) -> list[dict]:
        """Memórias episódicas ativas SEM entidades (p/ enriquecer via LLM em
        background). Mais recentes primeiro → o usuário vê os tópicos novos logo."""
        rows = self.conn.execute(
            "SELECT id, text FROM memories WHERE status='active' AND kind='chat' "
            "AND (entities IS NULL OR entities='' OR entities='[]') "
            "AND length(text) > 60 "               # pula saudações triviais
            "ORDER BY id DESC LIMIT ?", (int(limit),),
        ).fetchall()
        return [dict(r) for r in rows]

    def count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0])

    def clear(self) -> None:
        self.conn.execute("DELETE FROM memories")
        self.conn.commit()
        self._invalidate()

    # ------------------- cognitivo (Fase 1) ------------------- #
    _FULL_COLS = ("id, text, kind, session_id, created_at, source, provenance, entities, "
                  "evidence, confidence, importance, reinforcement, last_recalled, "
                  "expiration, status")

    def get(self, mem_id: int) -> dict | None:
        """Linha completa (sem o BLOB de embedding) — base p/ o model Memory."""
        r = self.conn.execute(
            f"SELECT {self._FULL_COLS} FROM memories WHERE id = ?", (mem_id,)
        ).fetchone()
        return dict(r) if r else None

    def by_entities(self, node_ids: list[str], limit: int = 40) -> list[dict]:
        """Memórias ligadas a algum dos nós do grafo (coluna JSON `entities`).
        Match por LIKE sobre o JSON — suficiente p/ o volume single-user."""
        if not node_ids:
            return []
        clauses = " OR ".join(["entities LIKE ?"] * len(node_ids))
        params: list = [f'%"{nid}"%' for nid in node_ids]
        params.append(limit)
        rows = self.conn.execute(
            f"SELECT {self._FULL_COLS} FROM memories WHERE ({clauses}) LIMIT ?", params
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_recalled(self, ids: list[int]) -> None:
        """Marca ``last_recalled``. NÃO reforça (ajuste v2: recuperar ≠ reforçar —
        evita loop de erro em que uma memória errada 'ganha' importância só por
        ser recuperada)."""
        if not ids:
            return
        now = self._now()
        self.conn.executemany(
            "UPDATE memories SET last_recalled = ? WHERE id = ?", [(now, i) for i in ids]
        )
        self.conn.commit()

    def reinforce(self, mem_id: int, delta: int = 1) -> None:
        """Reforço EXPLÍCITO (evidência nova / confirmação do usuário) — nunca no recall."""
        self.conn.execute(
            "UPDATE memories SET reinforcement = COALESCE(reinforcement, 0) + ? WHERE id = ?",
            (delta, mem_id),
        )
        self.conn.commit()

    def set_signals(
        self, mem_id: int, *, confidence: float | None = None,
        importance: float | None = None, status: str | None = None,
        expiration: str | None = None,
    ) -> None:
        """Atualiza sinais independentes (confidence/importance/status/expiration)."""
        sets, vals = [], []
        for col, val in (("confidence", confidence), ("importance", importance),
                         ("status", status), ("expiration", expiration)):
            if val is not None:
                sets.append(f"{col} = ?")
                vals.append(val)
        if not sets:
            return
        vals.append(mem_id)
        self.conn.execute(f"UPDATE memories SET {', '.join(sets)} WHERE id = ?", vals)
        self.conn.commit()

    def vectors(self, status: str = "active") -> tuple[list[int], list[str], list[int], np.ndarray | None]:
        """(ids, kinds, reinforcement, matriz normalizada) das memórias de um status.
        Base p/ a deduplicação da consolidação."""
        rows = self.conn.execute(
            "SELECT id, kind, reinforcement, embedding FROM memories WHERE status = ?", (status,)
        ).fetchall()
        if not rows:
            return [], [], [], None
        ids = [r["id"] for r in rows]
        kinds = [r["kind"] for r in rows]
        reinf = [int(r["reinforcement"] or 0) for r in rows]
        mat = self._normalize(np.vstack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows]))
        return ids, kinds, reinf, mat

    def archive_expired(self, now: str) -> int:
        """Decay: arquiva memórias ativas com expiration vencida. Devolve quantas."""
        cur = self.conn.execute(
            "UPDATE memories SET status = 'archived' WHERE status = 'active' "
            "AND expiration IS NOT NULL AND expiration < ?", (now,)
        )
        self.conn.commit()
        self._invalidate()
        return cur.rowcount

    def supersede(self, mem_id: int) -> None:
        """Aposenta uma memória (duplicata) — NUNCA apaga (auditável/reversível)."""
        self.conn.execute("UPDATE memories SET status = 'superseded' WHERE id = ?", (mem_id,))
        self.conn.commit()
        self._invalidate()

    def add_evidence(self, mem_id: int, evidence_ids: list[int]) -> None:
        """Anexa ids de suporte à coluna `evidence` (união, sem duplicar)."""
        row = self.conn.execute("SELECT evidence FROM memories WHERE id = ?", (mem_id,)).fetchone()
        cur: list = []
        if row and row["evidence"]:
            try:
                cur = json.loads(row["evidence"])
            except (ValueError, TypeError):
                cur = []
        merged = list(dict.fromkeys([*cur, *evidence_ids]))
        self.conn.execute("UPDATE memories SET evidence = ? WHERE id = ?",
                          (json.dumps(merged), mem_id))
        self.conn.commit()

    def active_with_entities(self, limit: int = 500) -> list[dict]:
        """Memórias ativas que já têm entidades (p/ popular o grafo)."""
        rows = self.conn.execute(
            "SELECT id, entities FROM memories WHERE status = 'active' AND entities IS NOT NULL "
            "ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self.conn.close()
