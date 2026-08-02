"""Log de auditoria append-only (JSON Lines).

Toda ação sensível (escrita de arquivo, comando, controle de mouse/teclado)
é registrada aqui, com timestamp, agente responsável, parâmetros e resultado.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aila.core.logging import get_logger

log = get_logger("audit")


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        action: str,
        agent: str,
        params: dict[str, Any],
        result: str,
        allowed: bool,
    ) -> None:
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "action": action,
            "agent": agent,
            "params": _safe(params),
            "result": result,
            "allowed": allowed,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        log.info(f"[audit] {agent}:{action} allowed={allowed} -> {result}")

    def tail(self, n: int = 50) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as fh:
            lines = fh.readlines()[-n:]
        return [json.loads(line) for line in lines if line.strip()]


def _safe(params: dict[str, Any]) -> dict[str, Any]:
    """Trunca valores muito longos para não inchar o log."""
    out: dict[str, Any] = {}
    for k, v in params.items():
        s = str(v)
        out[k] = s if len(s) <= 500 else s[:500] + "…"
    return out
