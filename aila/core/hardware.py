"""HardwareMonitor — a ÚNICA porta para o hardware (nvidia-smi + psutil).

Resource Intelligence R1. Antes, `nvidia-smi` era chamado em dois lugares
(`core/vram.py` e `core/metrics.py`) com queries diferentes e caches separados.
Aqui isso vira um adapter único e testável: uma sonda de GPU (cacheada) e uma
leitura de sistema (CPU/RAM). `vram.py` e `metrics.py` passam a CONSUMIR isto,
sem mudar o que já entregam.

Só MEDE — nenhuma decisão/política mora aqui (o dial verde/amarelo/vermelho fica
em `vram.classify`; o ResourceManager virá por cima nas fases seguintes). A sonda
é injetável (`gpu_probe=`) p/ testar sem GPU: CI nunca depende de uma RTX.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import time
from dataclasses import dataclass

import psutil

from aila.core.logging import get_logger

log = get_logger("hardware")

# Query única = superconjunto do que os dois antigos sítios pediam (a de metrics).
_GPU_QUERY = "name,utilization.gpu,memory.total,memory.used,memory.free,temperature.gpu"


@dataclass(slots=True)
class GpuReading:
    """Leitura CRUA da GPU (sem política). MB e % como o nvidia-smi reporta."""

    name: str
    util: float          # utilização do núcleo, %
    total_mb: float
    used_mb: float
    free_mb: float
    temp: float          # °C


@dataclass(slots=True)
class SystemReading:
    cpu_percent: float
    ram_used_gb: float
    ram_total_gb: float
    ram_percent: float


def _probe_nvidia_blocking() -> GpuReading | None:
    """Lê a GPU via nvidia-smi (bloqueante — o monitor chama em thread quando async).
    Ausente/erro → None (nunca levanta). Sem janela de console no Windows."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, f"--query-gpu={_GPU_QUERY}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    # Uma linha por GPU; a Aila roda numa (RTX 4060) → primeira linha.
    parts = [p.strip() for p in out.stdout.strip().splitlines()[0].split(",")]
    if len(parts) < 6:
        return None
    try:
        util, total, used, free, temp = (float(x) for x in parts[1:6])
    except ValueError:
        return None
    return GpuReading(name=parts[0], util=util, total_mb=total,
                      used_mb=used, free_mb=free, temp=temp)


class HardwareMonitor:
    """Fonte única de verdade do hardware. A leitura de GPU é cacheada (subprocess
    é caro; VRAM não muda mais rápido que o poll), a de sistema é barata e direta."""

    def __init__(self, *, gpu_probe=None, cache_ttl: float = 2.0) -> None:
        self._probe = gpu_probe or _probe_nvidia_blocking
        self._ttl = cache_ttl
        self._gpu: GpuReading | None = None
        self._gpu_ts = 0.0
        self._probed = False

    def gpu(self, *, fresh: bool = False) -> GpuReading | None:
        """Leitura de GPU (cacheada ~ttl). None sem nvidia-smi. `fresh` ignora o cache."""
        now = time.monotonic()
        if not fresh and self._probed and (now - self._gpu_ts) < self._ttl:
            return self._gpu
        self._gpu = self._probe()
        self._gpu_ts = now
        self._probed = True
        return self._gpu

    async def gpu_async(self, *, fresh: bool = False) -> GpuReading | None:
        return await asyncio.to_thread(self.gpu, fresh=fresh)

    @staticmethod
    def system() -> SystemReading:
        """CPU/RAM via psutil. Barato — sem cache."""
        vm = psutil.virtual_memory()
        return SystemReading(
            cpu_percent=psutil.cpu_percent(interval=None),
            ram_used_gb=round(vm.used / 1e9, 1),
            ram_total_gb=round(vm.total / 1e9, 1),
            ram_percent=vm.percent,
        )


#: instância de processo compartilhada — o único objeto que fala com o hardware.
monitor = HardwareMonitor()
