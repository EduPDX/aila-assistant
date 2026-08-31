"""Projeção segura dos modelos para a Cognitive Scene.

Esta camada traduz inventário, configuração e telemetria em uma representação
visual. Ela nunca expõe chaves, URLs, prompts ou mensagens.
"""

from __future__ import annotations

import math
import re
from typing import Any

_PARAMS = re.compile(r"(?:^|[-_/ :])([0-9]+(?:\.[0-9]+)?)b(?:$|[-_/ :])", re.I)


def _size_hint(model: str, disk_mb: int = 0) -> float:
    """Escala logarítmica limitada: 3B e 550B coexistem sem destruir a cena."""
    match = _PARAMS.search(model)
    if match:
        billions = max(0.5, float(match.group(1)))
    elif disk_mb:
        billions = max(0.5, disk_mb / 650.0)
    else:
        billions = 4.0
    return round(max(0.72, min(1.48, 0.62 + math.log10(billions + 1) * 0.34)), 2)


def build_infrastructure_snapshot(
    engine: Any,
    inventory: Any,
    *,
    active_provider: str = "local",
) -> dict[str, Any]:
    """Compõe o contrato público consumido pelo salão holográfico."""
    health = engine.health.snapshot()
    perf = engine.telemetry.snapshot()
    racks: list[dict[str, Any]] = []
    active_local_model = getattr(engine.llm, "default_model", engine.settings.llm.model)
    active_local_norm = active_local_model if ":" in active_local_model else f"{active_local_model}:latest"

    for state in inventory.states:
        telemetry = perf.get(state.name, {})
        racks.append({
            "id": f"ollama:{state.name}",
            "provider": "local",
            "label": state.name,
            "location": "local",
            "status": "active" if active_provider in {"local", "ollama"} and state.name == active_local_norm
            else "ready" if state.installed else "offline",
            "scale": _size_hint(state.name, state.disk_mb),
            "roles": list(state.roles),
            "loaded": state.loaded,
            "vram_mb": state.vram_mb,
            "disk_mb": state.disk_mb,
            "tps": telemetry.get("tps"),
        })

    from aila.llm.openai_compat import PROVIDER_DEFAULTS

    for name, cfg in engine.settings.providers.items():
        if not cfg.api_key:
            continue
        defaults = PROVIDER_DEFAULTS.get(name, {})
        model = cfg.model or defaults.get("model", name)
        circuit = health.get(name, {})
        state = str(circuit.get("state", "closed")).lower()
        available = bool(cfg.enabled and name in engine.router.providers and state != "open")
        telemetry = perf.get(model, perf.get(name, {}))
        racks.append({
            "id": f"cloud:{name}",
            "provider": name,
            "label": model,
            "location": "cloud",
            "status": "active" if active_provider == name else "ready" if available else "offline",
            "scale": _size_hint(model),
            "roles": ["vision"] if bool(cfg.vision or defaults.get("vision")) else ["chat"],
            "loaded": available,
            "vram_mb": 0,
            "disk_mb": 0,
            "tps": telemetry.get("tps"),
        })

    racks.sort(key=lambda rack: (rack["location"] != "local", rack["label"].lower()))
    return {"active_provider": active_provider, "racks": racks}
