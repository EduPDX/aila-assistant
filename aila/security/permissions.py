"""Gerenciador de permissões.

Regras aplicadas antes de QUALQUER ação de agente:

1. Modo somente-leitura (``read_only``): bloqueia toda ação que escreve,
   apaga ou executa.
2. Ações destrutivas: exigem confirmação explícita do usuário (fluxo
   assíncrono via event bus / callback).

O fluxo de confirmação é injetado de fora (a UI decide como perguntar), então
este módulo não conhece a interface — apenas orquestra a decisão.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from aila.core.config import SecurityConfig
from aila.core.logging import get_logger
from aila.security.audit import AuditLog
from aila.security.policy import AUTONOMY_NAMES, BLOCKED, DANGER, REVIEW, PermissionPolicy

log = get_logger("permissions")

# Função que pergunta ao usuário e resolve True/False.
ConfirmFn = Callable[[str, dict], Awaitable[bool]]


class PermissionDenied(Exception):
    """Ação bloqueada por política de segurança ou recusa do usuário."""


class PermissionManager:
    def __init__(self, cfg: SecurityConfig, audit: AuditLog) -> None:
        self.cfg = cfg
        self.audit = audit
        self.policy = PermissionPolicy(cfg)
        self._confirm: ConfirmFn | None = None

    def set_confirm_handler(self, fn: ConfirmFn) -> None:
        """Registra o callback que pede confirmação ao usuário."""
        self._confirm = fn

    def is_write_action(self, action: str) -> bool:
        return not self.policy.is_read(action)

    def _deny(self, action, agent, params, reason: str, msg: str) -> None:
        self.audit.record(action, agent, params, reason, allowed=False)
        raise PermissionDenied(msg)

    async def check(self, action: str, agent: str, params: dict) -> None:
        """Autoriza (ou não) uma ação, combinando: modo somente-leitura, nível
        de AUTONOMIA (capacidade destravada) e NÍVEL DE RISCO (confirmação)."""
        # 1. Modo somente-leitura (master override)
        if self.cfg.read_only and self.is_write_action(action):
            self._deny(action, agent, params, "blocked:read_only",
                       f"Ação '{action}' bloqueada: modo somente-leitura "
                       f"(AILA_SECURITY__READ_ONLY=false p/ liberar).")

        # 2. Nível de autonomia: a categoria da ação está destravada?
        need = self.policy.min_autonomy(action)
        if self.policy.autonomy < need:
            self._deny(action, agent, params, f"blocked:autonomy<{need}",
                       f"Ação '{action}' exige autonomia nível {need} "
                       f"({AUTONOMY_NAMES.get(need, need)}); atual: {self.policy.autonomy}.")

        # 3. Nível de risco
        level = self.policy.classify(action)
        if level == BLOCKED:
            self._deny(action, agent, params, "blocked:policy",
                       f"Ação '{action}' está bloqueada pela política.")

        needs_confirm = (level == DANGER and self.cfg.confirm_destructive) or \
                        (level == REVIEW and self.cfg.confirm_review)
        if needs_confirm:
            if self._confirm is None:
                self._deny(action, agent, params, "blocked:no_confirm_handler",
                           f"Ação '{action}' ({level}) requer confirmação, mas não há handler.")
            if not await self._confirm(action, params):
                self._deny(action, agent, params, "denied:user",
                           f"Usuário recusou a ação '{action}'.")

        self.audit.record(action, agent, params, f"authorized:{level}", allowed=True)
