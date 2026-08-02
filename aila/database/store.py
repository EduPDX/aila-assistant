"""Armazenamento de conversas em SQLite (stdlib, zero dependências).

Guarda sessões e mensagens para o histórico da UI e, futuramente, para
alimentar a memória de longo prazo (embeddings/RAG).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from aila.core.config import PROJECT_ROOT

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class ConversationStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        path = Path(db_path) if db_path else PROJECT_ROOT / "data" / "aila.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    def create_session(self, title: str = "Nova conversa") -> int:
        cur = self.conn.execute(
            "INSERT INTO sessions (title, created_at) VALUES (?, ?)",
            (title, self._now()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_message(self, session_id: int, role: str, content: str) -> None:
        self.conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
            (session_id, role, content, self._now()),
        )
        self.conn.commit()

    def list_sessions(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_messages(self, session_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT role, content, created_at FROM messages "
            "WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self.conn.close()
