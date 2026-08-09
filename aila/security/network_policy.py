"""NetworkPolicy — gate central de saída de rede (privacidade).

Dois modos:
    OFFLINE — nada sai do PC: sem APIs externas, sem pesquisa web, sem TTS
              online. Só modelos e ferramentas locais.
    HYBRID  — permite serviços online (pesquisa, APIs externas, TTS neural).

Ferramentas e provedores CONSULTAM esta política antes de qualquer egresso.
localhost/127.0.0.1 é sempre considerado local (Ollama etc. seguem funcionando
mesmo offline). O modo pode ser trocado em tempo de execução.
"""

from __future__ import annotations

from aila.core.logging import get_logger

log = get_logger("network")

OFFLINE = "offline"
HYBRID = "hybrid"

_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "0.0.0.0")


class NetworkBlocked(Exception):
    """Operação de rede bloqueada pela política (modo offline)."""


class NetworkPolicy:
    def __init__(self, mode: str = HYBRID) -> None:
        self._mode = HYBRID
        self.set_mode(mode)

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> str:
        m = (mode or HYBRID).lower()
        self._mode = m if m in (OFFLINE, HYBRID) else HYBRID
        log.info(f"modo de rede: {self._mode}")
        return self._mode

    @property
    def is_offline(self) -> bool:
        return self._mode == OFFLINE

    @property
    def online_allowed(self) -> bool:
        return self._mode == HYBRID

    def allow_egress(self, host: str | None = None) -> bool:
        """True se pode enviar dados p/ FORA do PC. localhost é sempre permitido."""
        if host:
            h = host.lower()
            if any(h == lh or h.startswith(lh) for lh in _LOCAL_HOSTS):
                return True
        return self.online_allowed

    def guard(self, reason: str = "operação online") -> None:
        """Levanta ``NetworkBlocked`` se offline (para operações que EXIGEM rede)."""
        if self.is_offline:
            raise NetworkBlocked(f"{reason} indisponível: modo OFFLINE ativo.")
