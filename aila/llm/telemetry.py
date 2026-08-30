"""PerfTelemetry — desempenho REAL por modelo (medir p/ depois decidir).

Resource Intelligence R8. Fecha o ciclo "medir" da frente: quanto cada modelo
realmente entrega em ESTE PC. Antes só havia `backend.last_tps` (um número global
da última geração, para o painel). Aqui isso vira histórico POR MODELO:
throughput (tokens/s), latência até o 1º token (TTFT, o que o usuário sente) e
taxa de fallback (quantas vezes aquele modelo falhou/foi trocado).

São dados para as fases seguintes decidirem com base no real (R9 lifecycle, R10
prioridade de fundo) e para a UI (R11) mostrar. Este módulo só ACUMULA — não
decide nada. Médias por EWMA (peso ao recente) para refletir o estado atual da
máquina sem guardar série longa.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from aila.core.logging import get_logger

log = get_logger("telemetry")

#: peso do dado mais recente na média móvel (0..1). 0.3 = suaviza sem enterrar mudanças.
_ALPHA = 0.3


def _ewma(prev: float, x: float, *, first: bool, alpha: float = _ALPHA) -> float:
    """Média móvel exponencial. A 1ª amostra assume o valor cheio (sem viés do zero)."""
    return x if first else alpha * x + (1 - alpha) * prev


@dataclass(slots=True)
class ModelPerf:
    """Desempenho acumulado de um modelo. EWMA = reflete o estado ATUAL da máquina."""

    model: str
    gens: int = 0             # gerações concluídas
    tps_ewma: float = 0.0     # tokens/s (throughput)
    tps_samples: int = 0      # gerações com tps medido (>0)
    ttft_ewma_ms: float = 0.0  # latência até o 1º token (ms)
    ttft_samples: int = 0
    fallbacks: int = 0        # vezes que este modelo falhou/foi trocado
    last_ts: float = 0.0


class PerfTelemetry:
    """Acumula desempenho por nome de modelo. `clock` injetável p/ teste."""

    def __init__(self, *, alpha: float = _ALPHA, clock=time.monotonic) -> None:
        self._alpha = alpha
        self._clock = clock
        self._m: dict[str, ModelPerf] = {}

    def _get(self, model: str) -> ModelPerf:
        p = self._m.get(model)
        if p is None:
            p = self._m[model] = ModelPerf(model)
        return p

    def record_generation(self, model: str, *, tps: float = 0.0, ttft_ms: float = 0.0) -> None:
        """Registra uma geração concluída. `tps`/`ttft_ms` <= 0 são ignorados (o
        provedor pode não reportar), mas a geração ainda conta em `gens`."""
        if not model:
            return
        p = self._get(model)
        p.gens += 1
        if tps and tps > 0:
            p.tps_samples += 1
            p.tps_ewma = _ewma(p.tps_ewma, tps, first=p.tps_samples == 1, alpha=self._alpha)
        if ttft_ms and ttft_ms > 0:
            p.ttft_samples += 1
            p.ttft_ewma_ms = _ewma(p.ttft_ewma_ms, ttft_ms,
                                   first=p.ttft_samples == 1, alpha=self._alpha)
        p.last_ts = self._clock()

    def record_fallback(self, model: str) -> None:
        """Este modelo falhou (exceção ou resposta vazia) e o turno trocou de modelo."""
        if model:
            self._get(model).fallbacks += 1

    def snapshot(self) -> dict:
        """Foto por modelo p/ UI/diagnóstico (R11). `fallback_rate` = falhas / tentativas."""
        out: dict[str, dict] = {}
        for name, p in self._m.items():
            attempts = p.gens + p.fallbacks
            out[name] = {
                "gens": p.gens,
                "tps": round(p.tps_ewma, 1),
                "ttft_ms": round(p.ttft_ewma_ms, 0),
                "fallbacks": p.fallbacks,
                "fallback_rate": round(p.fallbacks / attempts, 3) if attempts else 0.0,
            }
        return out
