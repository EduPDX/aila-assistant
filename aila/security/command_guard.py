"""Guard de comandos de terminal — allowlist/denylist + classificação de risco.

Camada de segurança EXTRA (defesa em profundidade) sobre o ``computer.run_command``.
Mesmo que o usuário confirme e esteja em autonomia alta, alguns comandos são
CATASTRÓFICOS (apagar o disco, desligar o Defender, baixar-e-executar) e nunca
devem rodar automaticamente. Este guard:

    - BLOCKED : nunca executado pelo agente (denylist).
    - DANGER  : destrutivo/perigoso — segue o fluxo normal (confirmação).
    - SAFE    : leitura conhecida (Get-*, echo, dir, …) — informativo.
    - REVIEW  : o resto (segue o fluxo normal).

O guard NÃO substitui as permissões: ele apenas adiciona um piso de bloqueio.
Tudo é configurável (``SecurityConfig.command_denylist``/``command_allowlist``);
o usuário pode acrescentar padrões, mas os embutidos protegem por padrão.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aila.core.config import SecurityConfig

SAFE, REVIEW, DANGER, BLOCKED = "safe", "review", "danger", "blocked"

# Padrões CATASTRÓFICOS → BLOCKED (regex, motivo). Focados em Windows/PowerShell,
# mas cobrem equivalentes POSIX comuns. Case-insensitive.
_DENY: list[tuple[str, str]] = [
    (r"\bformat(-volume)?\b", "formatação de disco"),
    (r"\bdiskpart\b|\bclear-disk\b|\bmkfs\b", "operação destrutiva de disco"),
    (r"rm\s+-rf?\s+[/~]", "remoção recursiva da raiz"),
    (r"\bdel\s+/[a-z/ ]*s\b|\brmdir\s+/s\b", "remoção recursiva forçada"),
    (r"remove-item[^|>\n]*-recurse[^|>\n]*-force[^|>\n]*"
     r"(c:\\?($|\s|\\)|\$env:systemroot|\\windows|[a-z]:\\\s*$)",
     "remoção recursiva de diretório de sistema/raiz"),
    (r"\bshutdown\b|\brestart-computer\b|\bstop-computer\b", "desligar/reiniciar o PC"),
    (r"\bbcdedit\b", "alteração do gerenciador de boot"),
    (r"vssadmin\s+delete|wbadmin\s+delete|\bcipher\s+/w", "apagar backups/shadow copies"),
    (r"\breg\s+delete\b|remove-item(property)?\s+[^\n]*hk(lm|cu|cr|u)",
     "exclusão no registro do Windows"),
    (r"(set|new)-itemproperty\s+[^\n]*hklm", "escrita no registro (HKLM)"),
    (r"set-mppreference[^\n]*-disable|add-mppreference[^\n]*exclusion",
     "desligar/burlar o Windows Defender"),
    (r"netsh\s+advfirewall|set-netfirewallprofile[^\n]*disabled", "desligar o firewall"),
    (r"(invoke-webrequest|iwr|curl|wget)[^\n|]*\|\s*(iex|invoke-expression|bash|sh|cmd)",
     "baixar-e-executar (pipe para interpretador)"),
    (r"downloadstring|downloadfile\s*\(", "baixar-e-executar código remoto"),
    (r"net\s+user\s+[^\n]*/add|new-localuser|add-localgroupmember[^\n]*administr",
     "criação/elevação de conta"),
    (r"schtasks\s+/create|new-scheduledtask|sc\s+(delete|config)\b",
     "persistência (tarefa/serviço)"),
]

# Prefixos/cmdlets de LEITURA conhecidos → SAFE (informativos).
_SAFE_PREFIXES: tuple[str, ...] = (
    "get-", "echo ", "write-output", "write-host", "dir", "ls", "cat ",
    "type ", "select-", "measure-", "test-path", "resolve-path", "where-",
    "sort-", "format-table", "format-list", "out-string", "hostname",
    "whoami", "date", "systeminfo", "ipconfig", "ping ", "tree", "pwd",
    "$psversiontable", "getmac",
)

# Sinais de destrutividade → DANGER (não bloqueia; confirmação normal cuida).
_DANGER = re.compile(
    r"\bremove-item\b|\brm\s|\bdel\s|\bmove-item\b|\brename-item\b|"
    r"\bstop-process\b|\bkill\b|\bset-content\b|\bclear-content\b|\bnew-item\b|"
    r"\bstop-service\b|\brestart-service\b|>\s*\S",
    re.IGNORECASE,
)


class CommandGuard:
    def __init__(self, cfg: SecurityConfig | None = None) -> None:
        extra_deny = list(getattr(cfg, "command_denylist", None) or [])
        self._deny = [(re.compile(p, re.IGNORECASE), why) for p, why in _DENY]
        self._deny += [(re.compile(p, re.IGNORECASE), "denylist (config)") for p in extra_deny]
        self._allow = tuple(
            p.lower() for p in (getattr(cfg, "command_allowlist", None) or ())
        )

    def classify(self, command: str) -> tuple[str, str]:
        """Devolve (risco, motivo) para o comando."""
        cmd = (command or "").strip()
        if not cmd:
            return REVIEW, "comando vazio"
        low = cmd.lower()
        for rx, why in self._deny:
            if rx.search(low):
                return BLOCKED, why
        if low.startswith(self._allow) and self._allow:
            return SAFE, "allowlist (config)"
        if low.startswith(_SAFE_PREFIXES):
            return SAFE, "comando de leitura"
        if _DANGER.search(cmd):
            return DANGER, "comando destrutivo"
        return REVIEW, "comando não classificado"

    def is_blocked(self, command: str) -> tuple[bool, str]:
        risk, why = self.classify(command)
        return risk == BLOCKED, why
