"""Métricas reais do sistema para o painel de status.

Fonte única de hardware: o ``HardwareMonitor`` (R1) — CPU/RAM (psutil) e
GPU/VRAM (nvidia-smi). Este módulo só FORMATA a leitura para a UI e aplica o
dial verde/amarelo/vermelho (``vram.classify``). Tudo tolerante a ausência: o
painel mostra apenas o que der para medir.
"""

from __future__ import annotations

import time

from aila.core.logging import get_logger

log = get_logger("metrics")

_START = time.monotonic()


def uptime_seconds() -> int:
    return int(time.monotonic() - _START)


def _read_gpu() -> dict | None:
    """GPU formatada para a UI (via HardwareMonitor, cacheado). None se indisponível.
    O 'state' é o dial de VRAM a partir do headroom; a UI colore a barra por ele."""
    from aila.core.hardware import monitor
    from aila.core.vram import classify

    r = monitor.gpu()
    if r is None:
        return None
    return {
        "name": r.name,
        "util": r.util,
        "vram_used_mb": r.used_mb,
        "vram_total_mb": r.total_mb,
        "vram_free_mb": r.free_mb,
        "state": classify(int(r.free_mb)),
        "temp": r.temp,
    }


def collect(engine=None) -> dict:
    """Snapshot das métricas. ``engine`` (opcional) fornece modelo e tokens/s."""
    from aila.core.hardware import monitor

    sysr = monitor.system()
    data: dict = {
        "cpu": sysr.cpu_percent,
        "ram": {
            "used_gb": sysr.ram_used_gb,
            "total_gb": sysr.ram_total_gb,
            "percent": sysr.ram_percent,
        },
        "gpu": _read_gpu(),
        "uptime_s": uptime_seconds(),
        "tps": 0.0,
        "model": None,
    }
    if engine is not None:
        data["tps"] = round(getattr(engine.llm, "last_tps", 0.0) or 0.0, 1)
        data["model"] = getattr(engine.llm, "default_model", None)
    return data
