"""Política de permissões — níveis de risco por ação + níveis de autonomia.

NÍVEIS DE RISCO (por ação):
    SAFE     — executa automaticamente (leituras, pesquisa, análise).
    REVIEW   — confirma se ``confirm_review`` (default: não).
    DANGER   — confirma se ``confirm_destructive`` (default: sim).
    BLOCKED  — nunca executada pelo agente.

NÍVEIS DE AUTONOMIA (do usuário, 1..5) — destravam categorias de ação:
    L1 ASSISTANT    — só conversa + ferramentas de leitura.
    L2 EXECUTOR     — + agir no computador/arquivos (mouse/teclado/comandos).
    L3 DEVELOPER    — + executar/mexer em código.
    L4 AUTONOMOUS   — + tarefas multi-etapa autônomas (limites no engine).
    L5 SELF-IMPROVE — + trabalhar no próprio código (isolado, com validação).

Toda a política é CONFIGURÁVEL (SecurityConfig): nível de autonomia, overrides
de nível por ação, mínimos de autonomia por prefixo e lista de bloqueio.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aila.core.config import SecurityConfig

SAFE, REVIEW, DANGER, BLOCKED = "safe", "review", "danger", "blocked"

_READ_SUFFIXES = (".read", ".list", ".search", ".get", ".info", ".analyze")

# nível MÍNIMO de autonomia por prefixo de ação (escrita). Leituras = 1 sempre.
_MIN_AUTONOMY: list[tuple[str, int]] = [
    ("code.write", 5),                             # auto-modificar o próprio código → L5
    ("code.run", 3), ("code.execute", 3), ("code.test", 3),   # executar/testar código → L3
    ("git.branch", 3), ("git.checkout", 3),        # git (backup/rollback) → L3
    ("git.commit", 3), ("git.stash", 3),
    ("computer.", 2),                              # controlar o PC → L2
    ("file.write", 2), ("file.move", 2),
    ("file.delete", 2), ("file.overwrite", 2),
    ("terminal.", 2),
]

AUTONOMY_NAMES = {1: "assistant", 2: "executor", 3: "developer",
                  4: "autonomous", 5: "self-improve"}


class PermissionPolicy:
    def __init__(self, cfg: SecurityConfig) -> None:
        self.cfg = cfg

    @property
    def autonomy(self) -> int:
        return max(1, min(5, getattr(self.cfg, "autonomy_level", 3)))

    @staticmethod
    def is_read(action: str) -> bool:
        return action.endswith(_READ_SUFFIXES)

    def classify(self, action: str) -> str:
        """Nível de risco da ação (override da config > listas > heurística)."""
        override = (self.cfg.action_levels or {}).get(action)
        if override in (SAFE, REVIEW, DANGER, BLOCKED):
            return override
        if action in (self.cfg.blocked_actions or []):
            return BLOCKED
        if action in (self.cfg.destructive_actions or []):
            return DANGER
        if self.is_read(action):
            return SAFE
        return REVIEW

    def min_autonomy(self, action: str) -> int:
        """Nível mínimo de autonomia para a ação (leituras = 1)."""
        if self.is_read(action):
            return 1
        for prefix, lvl in (self.cfg.min_autonomy or {}).items():
            if action.startswith(prefix):
                return lvl
        for prefix, lvl in _MIN_AUTONOMY:
            if action.startswith(prefix):
                return lvl
        return 2   # escrita não catalogada → precisa de pelo menos L2
