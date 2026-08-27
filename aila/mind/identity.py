"""Carga da identidade/personalidade persistentes (Fase B).

A identidade da Aila NÃO vive num prompt: vive em ``config/identity.yaml``,
versionado, com override opcional em ``config/identity.local.yaml`` (não
versionado — preferências pessoais). Ausente o arquivo, usa os padrões do
código: a Aila nunca fica sem identidade.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from aila.core.logging import get_logger
from aila.mind.schemas import Identity, PersonalityTraits

log = get_logger("mind")

IDENTITY_FILE = "identity.yaml"
IDENTITY_LOCAL = "identity.local.yaml"


def _config_dir() -> Path:
    from aila.core.config import PROJECT_ROOT

    return PROJECT_ROOT / "config"


def _read(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        log.warning(f"identidade: falha lendo {path.name} ({exc!r}) — usando padrões")
        return {}
    return data if isinstance(data, dict) else {}


def load_identity(config_dir: str | Path | None = None) -> tuple[Identity, PersonalityTraits]:
    """Devolve (Identity, PersonalityTraits). Base + override local; campos
    inválidos são ignorados (nunca derruba o boot por config torta)."""
    base_dir = Path(config_dir) if config_dir else _config_dir()
    data: dict[str, Any] = {}
    for name in (IDENTITY_FILE, IDENTITY_LOCAL):
        p = base_dir / name
        if p.is_file():
            merged = _read(p)
            for key in ("identity", "personality"):
                if isinstance(merged.get(key), dict):
                    data.setdefault(key, {}).update(merged[key])

    try:
        identity = Identity(**(data.get("identity") or {}))
    except Exception as exc:  # noqa: BLE001 - config inválida não derruba a Aila
        log.warning(f"identidade inválida ({exc!r}) — usando padrão")
        identity = Identity()
    try:
        personality = PersonalityTraits(**(data.get("personality") or {}))
    except Exception as exc:  # noqa: BLE001
        log.warning(f"personalidade inválida ({exc!r}) — usando padrão")
        personality = PersonalityTraits()
    return identity, personality
