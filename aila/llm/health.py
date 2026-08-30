"""HealthRegistry — circuit-breaker por provedor (saúde ENTRE turnos).

Resource Intelligence R4. O engine já tem um `failed` set POR turno (não fica
batendo no mesmo provedor quebrado dentro de uma resposta). Isto adiciona a
memória ENTRE turnos: um provedor que falha seguidas vezes entra em COOLDOWN e o
router para de oferecê-lo por um tempo — depois deixa uma tentativa de prova
(half-open) e, se voltar, reabilita. Assim a Aila não insiste num modelo/endpoint
morto turno após turno, mas se recupera sozinha quando ele volta.

Estados (circuit-breaker clássico):
  • CLOSED    — saudável, disponível.
  • OPEN      — falhou demais; indisponível até o cooldown passar.
  • HALF_OPEN — cooldown passou; UMA tentativa de prova é permitida. Sucesso →
                CLOSED; falha → OPEN de novo (reinicia o cooldown).

SÓ rastreia saúde: não decide roteamento nem privacidade. O router CONSULTA
(`available`) e o engine REPORTA (`record_success`/`record_failure`). Regra de
segurança preservada em quem consulta: nunca deixar a cadeia vazia — a saúde só
PULA provedores extras, jamais remove o fallback local garantido.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import IntEnum

from aila.core.logging import get_logger

log = get_logger("health")

# Falhas CONSECUTIVAS até abrir o circuito, e quanto tempo ele fica aberto.
FAIL_THRESHOLD = 3
COOLDOWN_S = 30.0


class Circuit(IntEnum):
    CLOSED = 0
    OPEN = 1
    HALF_OPEN = 2


@dataclass(slots=True)
class ProviderHealth:
    """Saúde de um provedor. `fails` é a contagem de falhas CONSECUTIVAS."""

    name: str
    state: Circuit = Circuit.CLOSED
    fails: int = 0
    opened_at: float = 0.0
    last_error: str = ""


class HealthRegistry:
    """Circuit-breakers por nome de provedor. `clock` injetável p/ testar sem dormir."""

    def __init__(
        self,
        *,
        fail_threshold: int = FAIL_THRESHOLD,
        cooldown_s: float = COOLDOWN_S,
        clock=time.monotonic,
    ) -> None:
        self._threshold = fail_threshold
        self._cooldown = cooldown_s
        self._clock = clock
        self._h: dict[str, ProviderHealth] = {}

    def _get(self, name: str) -> ProviderHealth:
        h = self._h.get(name)
        if h is None:
            h = self._h[name] = ProviderHealth(name)
        return h

    def available(self, name: str) -> bool:
        """Pode oferecer este provedor agora? OPEN dentro do cooldown → False; passado
        o cooldown, promove a HALF_OPEN e libera UMA tentativa de prova."""
        h = self._get(name)
        if h.state is Circuit.OPEN and (self._clock() - h.opened_at) >= self._cooldown:
            h.state = Circuit.HALF_OPEN
            log.info(f"provedor '{name}' saiu do cooldown → half-open (tentativa de prova)")
        return h.state is not Circuit.OPEN

    def record_success(self, name: str) -> None:
        """Fecha o circuito e zera o histórico de falhas."""
        h = self._get(name)
        if h.state is not Circuit.CLOSED or h.fails:
            log.info(f"provedor '{name}' saudável de novo → closed")
        h.state = Circuit.CLOSED
        h.fails = 0
        h.last_error = ""

    def record_failure(self, name: str, error: str = "") -> None:
        """Conta uma falha. Ao atingir o limiar (ou falhar durante a prova), abre o
        circuito e (re)inicia o cooldown."""
        h = self._get(name)
        h.fails += 1
        h.last_error = error
        if h.state is Circuit.HALF_OPEN or h.fails >= self._threshold:
            if h.state is not Circuit.OPEN:
                log.warning(
                    f"provedor '{name}' aberto (cooldown {self._cooldown:.0f}s) "
                    f"após {h.fails} falha(s): {error!r}"
                )
            h.state = Circuit.OPEN
            h.opened_at = self._clock()

    def state(self, name: str) -> Circuit:
        return self._get(name).state

    def snapshot(self) -> dict:
        """Foto p/ diagnóstico/UI: nome→{state, fails, cooldown_left_s, last_error}."""
        now = self._clock()
        out: dict[str, dict] = {}
        for name, h in self._h.items():
            left = 0.0
            if h.state is Circuit.OPEN:
                left = max(0.0, self._cooldown - (now - h.opened_at))
            out[name] = {
                "state": h.state.name.lower(),
                "fails": h.fails,
                "cooldown_left_s": round(left, 1),
                "last_error": h.last_error,
            }
        return out
