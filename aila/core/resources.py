"""ResourceManager — a foto UNIFICADA de recursos e sua PRESSÃO.

Resource Intelligence R2. O `HardwareMonitor` (R1) mede GPU e sistema em cru;
aqui juntamos os dois num único `ResourceSnapshot` e traduzimos para uma escala
de pressão comum — NORMAL / ELEVATED / HIGH / CRITICAL — que as fases seguintes
(routing consciente de recurso, OOM prevention, prioridade de fundo) vão CONSULTAR
para decidir. Este módulo NÃO decide nada: só mede e classifica.

Duas dimensões, uma pressão:
  • GPU  — a partir do headroom de VRAM (o mesmo 'dial' de `vram.classify`,
           só que o vermelho se parte em HIGH/CRITICAL no fim da folga).
  • RAM  — a partir do %uso da memória de sistema (psutil).
A pressão geral é a PIOR das duas: um recurso apertado já basta para apertar tudo.
GPU ausente (sem nvidia-smi) não inventa pressão — fica NORMAL e a RAM manda.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from aila.core.hardware import GpuReading, HardwareMonitor, SystemReading, monitor
from aila.core.logging import get_logger
from aila.core.vram import RED_MB, YELLOW_MB

log = get_logger("resources")

# Fim da folga de VRAM: abaixo disto o 'vermelho' do dial vira CRITICAL (não só HIGH).
GPU_CRITICAL_MB = 128

# Limiares de %uso da RAM de sistema. Acima de HIGH o SO começa a paginar/travar.
RAM_ELEVATED_PCT = 75.0
RAM_HIGH_PCT = 85.0
RAM_CRITICAL_PCT = 93.0


class Pressure(IntEnum):
    """Escala de pressão de recurso, ordenada por severidade (NORMAL < ... < CRITICAL).

    IntEnum de propósito: ``max(a, b)`` dá a pior das duas, e comparações
    (``p >= Pressure.HIGH``) leem como um limiar. ``.name.lower()`` serializa p/ a UI.
    """

    NORMAL = 0
    ELEVATED = 1
    HIGH = 2
    CRITICAL = 3


def gpu_pressure(headroom_mb: int) -> Pressure:
    """Pressão de GPU a partir do headroom (VRAM livre). Alinha com `vram.classify`:
    verde→NORMAL, amarelo→ELEVATED; o vermelho se divide em HIGH e, no fim, CRITICAL."""
    if headroom_mb > YELLOW_MB:
        return Pressure.NORMAL
    if headroom_mb > RED_MB:
        return Pressure.ELEVATED
    if headroom_mb > GPU_CRITICAL_MB:
        return Pressure.HIGH
    return Pressure.CRITICAL


def ram_pressure(percent: float) -> Pressure:
    """Pressão de RAM a partir do %uso da memória de sistema."""
    if percent < RAM_ELEVATED_PCT:
        return Pressure.NORMAL
    if percent < RAM_HIGH_PCT:
        return Pressure.ELEVATED
    if percent < RAM_CRITICAL_PCT:
        return Pressure.HIGH
    return Pressure.CRITICAL


@dataclass(slots=True)
class ResourceSnapshot:
    """Recursos num instante + pressão traduzida. Serializável para UI/eventos."""

    gpu: GpuReading | None
    system: SystemReading
    gpu_pressure: Pressure
    ram_pressure: Pressure
    pressure: Pressure          # geral = a pior das duas
    gpu_available: bool

    def to_dict(self) -> dict:
        g = self.gpu
        return {
            "pressure": self.pressure.name.lower(),
            "gpu_available": self.gpu_available,
            "gpu": None if g is None else {
                "name": g.name, "util": g.util, "temp": g.temp,
                "vram_used_mb": g.used_mb, "vram_total_mb": g.total_mb,
                "vram_free_mb": g.free_mb, "pressure": self.gpu_pressure.name.lower(),
            },
            "ram": {
                "used_gb": self.system.ram_used_gb,
                "total_gb": self.system.ram_total_gb,
                "percent": self.system.ram_percent,
                "pressure": self.ram_pressure.name.lower(),
            },
            "cpu_percent": self.system.cpu_percent,
        }


class ResourceManager:
    """Compõe um ResourceSnapshot a partir do HardwareMonitor. Read-only.

    Sem estado próprio de política — só orquestra a leitura e a classificação.
    O cache vive no HardwareMonitor (a GPU); a RAM é barata e sempre fresca.
    """

    def __init__(self, hw: HardwareMonitor | None = None) -> None:
        self._hw = hw or monitor

    @staticmethod
    def _compose(gpu: GpuReading | None, sysr: SystemReading) -> ResourceSnapshot:
        """Classifica uma leitura crua (GPU+sistema) em pressões e a pior das duas."""
        g_press = gpu_pressure(int(gpu.free_mb)) if gpu is not None else Pressure.NORMAL
        r_press = ram_pressure(sysr.ram_percent)
        return ResourceSnapshot(
            gpu=gpu, system=sysr,
            gpu_pressure=g_press, ram_pressure=r_press,
            pressure=max(g_press, r_press), gpu_available=gpu is not None,
        )

    def snapshot(self, *, fresh: bool = False) -> ResourceSnapshot:
        return self._compose(self._hw.gpu(fresh=fresh), self._hw.system())

    async def snapshot_async(self, *, fresh: bool = False) -> ResourceSnapshot:
        return self._compose(await self._hw.gpu_async(fresh=fresh), self._hw.system())


#: gerente de processo compartilhado — a foto unificada de recursos p/ quem precisar.
resources = ResourceManager()
