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

from typing import Awaitable, Callable

from aila.core.config import SecurityConfig
from aila.core.logging import get_logger
from aila.security.audit import AuditLog

log = get_logger("permissions")

# Função que pergunta ao usuário e resolve True/False.
ConfirmFn = Callable[[str, dict], Awaitable[bool]]


class PermissionDenied(Exception):
    """Ação bloqueada por política de segurança ou recusa do usuário."""


class PermissionManager:
    def __init__(self, cfg: SecurityConfig, audit: AuditLog) -> None:
        self.cfg = cfg
        self.audit = audit
        self._confirm: ConfirmFn | None = None

    def set_confirm_handler(self, fn: ConfirmFn) -> None:
        """Registra o callback que pede confirmação ao usuário."""
        self._confirm = fn

    def is_write_action(self, action: str) -> bool:
        # Convenção: ações de leitura terminam em .read/.list/.search/.get
        read_suffixes = (".read", ".list", ".search", ".get", ".info", ".analyze")
        return not action.endswith(read_suffixes)

    async def check(self, action: str, agent: str, params: dict) -> None:
        """Autoriza (ou não) uma ação. Levanta ``PermissionDenied`` se negada."""
        # 1. Modo somente-leitura
        if self.cfg.read_only and self.is_write_action(action):
            self.audit.record(action, agent, params, "blocked:read_only", allowed=False)
            raise PermissionDenied(
                f"Ação '{action}' bloqueada: sistema em modo somente-leitura. "
                f"Desative com AILA_SECURITY__READ_ONLY=false."
            )

        # 2. Ações destrutivas => confirmação
        if self.cfg.confirm_destructive and action in self.cfg.destructive_actions:
            if self._confirm is None:
                self.audit.record(
                    action, agent, params, "blocked:no_confirm_handler", allowed=False
                )
                raise PermissionDenied(
                    f"Ação destrutiva '{action}' requer confirmação, mas nenhum "
                    f"handler de confirmação está registrado."
                )
            approved = await self._confirm(action, params)
            if not approved:
                self.audit.record(action, agent, params, "denied:user", allowed=False)
                raise PermissionDenied(f"Usuário recusou a ação '{action}'.")

        self.audit.record(action, agent, params, "authorized", allowed=True)
