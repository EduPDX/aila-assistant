"""Métricas reais do sistema para o painel de status.

CPU/RAM via ``psutil``; GPU/VRAM via ``nvidia-smi`` (subprocess, sem dependência
extra). Tudo tolerante a ausência — o painel só mostra o que der pra medir.
"""

from __future__ import annotations

import subprocess
import time

import psutil

from aila.core.logging import get_logger

log = get_logger("metrics")

_START = time.monotonic()
_gpu_cache: dict | None = None
_gpu_cache_ts = 0.0


def uptime_seconds() -> int:
    return int(time.monotonic() - _START)


def _read_gpu() -> dict | None:
    """Lê a GPU NVIDIA via nvidia-smi (cacheado ~2s). None se indisponível."""
    global _gpu_cache, _gpu_cache_ts
    now = time.monotonic()
    if _gpu_cache is not None and now - _gpu_cache_ts < 2.0:
        return _gpu_cache
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,memory.free,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if out.returncode != 0 or not out.stdout.strip():
            _gpu_cache, _gpu_cache_ts = None, now
            return None
        name, util, used, total, free, temp = [p.strip() for p in out.stdout.strip().splitlines()[0].split(",")]
        # 'state' = o "dial" de VRAM (verde/amarelo/vermelho) a partir do headroom;
        # a UI colore a barra por ele. É a Fase 1 do planejador (só medir/mostrar).
        from aila.core.vram import classify
        _gpu_cache = {
            "name": name,
            "util": float(util),
            "vram_used_mb": float(used),
            "vram_total_mb": float(total),
            "vram_free_mb": float(free),
            "state": classify(int(float(free))),
            "temp": float(temp),
        }
    except (OSError, ValueError, subprocess.TimeoutExpired):
        _gpu_cache = None
    _gpu_cache_ts = now
    return _gpu_cache


def collect(engine=None) -> dict:
    """Snapshot das métricas. ``engine`` (opcional) fornece modelo e tokens/s."""
    vm = psutil.virtual_memory()
    data: dict = {
        "cpu": psutil.cpu_percent(interval=None),
        "ram": {
            "used_gb": round(vm.used / 1e9, 1),
            "total_gb": round(vm.total / 1e9, 1),
            "percent": vm.percent,
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
