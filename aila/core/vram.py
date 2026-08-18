"""Planejador de VRAM — trata os 8 GB da GPU como um ORÇAMENTO explícito.

Fase 1 (este módulo): só MEDIR e MOSTRAR. Zero mudança de comportamento.
A ideia vem do `kimi-k3-in-c`: computar o custo de memória *up front* e reportá-lo,
em vez de descobrir o estouro no meio (lá o KV-cache; aqui a perda de contexto
WebGL do avatar sob pressão de VRAM). Medir antes de otimizar — nas fases
seguintes o avatar reage à pressão e a engine recusa carregar modelo que não cabe.

Duas fontes REAIS, nenhuma estimativa:
  1. `nvidia-smi` — total/usado/livre da GPU (roda em thread; ausente → no-op).
  2. Ollama `/api/ps` — `size_vram` de cada modelo carregado (chat + embed).

O estado é um "dial" em degraus a partir do headroom (VRAM livre):
  🟢 verde  > YELLOW_MB   folga confortável
  🟡 amarelo RED..YELLOW  apertando
  🔴 vermelho < RED_MB    no limite (fases futuras degradam/recusam aqui)
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from dataclasses import asdict, dataclass, field

import httpx

from aila.core.logging import get_logger

log = get_logger("vram")

# Limiares de headroom (MB). Calibrados para a RTX 4060 (8 GB) com avatar ligado.
YELLOW_MB = 1024   # abaixo disso, começa a apertar
RED_MB = 384       # abaixo disso, está no limite (risco de perder o contexto WebGL)

# Folga mínima para carregar um SEGUNDO modelo local (~7B, ~5 GB) sem estourar.
# Abaixo disso, o pré-voo da visão encolhe o avatar antes do pico (Fase 3).
VISION_HEADROOM_MB = 5000

_MB = 1024 * 1024


@dataclass(slots=True)
class GpuInfo:
    total_mb: int
    used_mb: int
    free_mb: int


@dataclass(slots=True)
class VramPlan:
    """Foto do orçamento de VRAM num instante. Serializável para a UI/eventos."""

    available: bool = False           # nvidia-smi respondeu?
    total_mb: int = 0
    used_mb: int = 0
    free_mb: int = 0
    models_mb: int = 0                # soma de size_vram dos modelos no Ollama
    models: list[dict] = field(default_factory=list)  # [{name, vram_mb}]
    headroom_mb: int = 0              # VRAM livre = o que sobra p/ crescer
    state: str = "unknown"            # green | yellow | red | unknown

    def to_dict(self) -> dict:
        return asdict(self)


def _probe_gpu_blocking() -> GpuInfo | None:
    """Lê a VRAM via nvidia-smi. Bloqueante — chamar com asyncio.to_thread."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "--query-gpu=memory.total,memory.used,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),  # sem janela no Windows
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    # Uma linha por GPU; a Aila roda numa (RTX 4060) → primeira linha.
    parts = [p.strip() for p in out.stdout.strip().splitlines()[0].split(",")]
    if len(parts) < 3:
        return None
    try:
        total, used, free = (int(float(x)) for x in parts[:3])
    except ValueError:
        return None
    return GpuInfo(total_mb=total, used_mb=used, free_mb=free)


async def _probe_models(base_url: str, timeout: float = 3.0) -> tuple[int, list[dict]]:
    """Modelos carregados no Ollama e sua VRAM, via /api/ps. Falha → (0, [])."""
    try:
        async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout) as c:
            r = await c.get("/api/ps")
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, ValueError):
        return 0, []
    total = 0
    models: list[dict] = []
    for m in data.get("models", []):
        vram_mb = int(m.get("size_vram", 0)) // _MB
        models.append({"name": m.get("name", "?"), "vram_mb": vram_mb})
        total += vram_mb
    return total, models


def classify(headroom_mb: int) -> str:
    """Degrau do 'dial' a partir do headroom."""
    if headroom_mb > YELLOW_MB:
        return "green"
    if headroom_mb > RED_MB:
        return "yellow"
    return "red"


class VramPlanner:
    """Sonda GPU + Ollama e devolve um VramPlan. Read-only (Fase 1)."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self.base_url = base_url

    async def measure(self) -> VramPlan:
        gpu = await asyncio.to_thread(_probe_gpu_blocking)
        models_mb, models = await _probe_models(self.base_url)
        if gpu is None:
            # Sem nvidia-smi: ainda reportamos o que o Ollama diz, mas sem estado.
            return VramPlan(available=False, models_mb=models_mb, models=models)
        return VramPlan(
            available=True,
            total_mb=gpu.total_mb, used_mb=gpu.used_mb, free_mb=gpu.free_mb,
            models_mb=models_mb, models=models,
            headroom_mb=gpu.free_mb, state=classify(gpu.free_mb),
        )
