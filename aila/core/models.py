"""ModelManager — o INVENTÁRIO dos modelos: papéis, estado e footprint.

Resource Intelligence R3. A Aila usa vários modelos em papéis distintos (chat,
código, rápido, visão, embed). Este módulo responde, num instante: quais papéis
existem, para que modelo cada um aponta, quais estão INSTALADOS no Ollama, quais
estão CARREGADOS agora (ocupando VRAM) e quanto cada um pesa — além de quando o
Ollama vai LIBERAR o que está quente (o `expires_at` do keep_alive).

Read-only: só OBSERVA. Não carrega, não descarrega, não decide roteamento — isso
é responsabilidade do Ollama (carga) e das fases seguintes (R5 routing, R9
lifecycle). Aqui a Aila só passa a SABER o que tem e o que custa.

Fontes REAIS (nenhuma estimativa):
  • Ollama `/api/tags` — modelos instalados e tamanho em disco.
  • Ollama `/api/ps`   — modelos carregados, `size_vram` e `expires_at`.
Ollama fora do ar → inventário ainda lista os papéis (installed/loaded = False).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx

from aila.core.logging import get_logger

log = get_logger("models")

_MB = 1024 * 1024


def _norm(name: str) -> str:
    """Normaliza o nome p/ casar config × Ollama: sem tag explícita, assume :latest."""
    return name if ":" in name else f"{name}:latest"


def roles_from_settings(settings) -> dict[str, str]:
    """Mapa papel→modelo a partir das settings. Papel sem modelo definido é omitido
    (ex.: `fast_model` vazio herda o chat — não vira papel próprio no inventário)."""
    llm = settings.llm
    roles = {
        "chat": llm.model,
        "code": llm.code_model,
        "vision": llm.vision_model,
        "embed": settings.memory.embed_model,
    }
    if llm.fast_model:
        roles["fast"] = llm.fast_model
    return {r: m for r, m in roles.items() if m}


@dataclass(slots=True)
class ModelState:
    """Um modelo do inventário e o que se sabe dele agora."""

    name: str
    roles: list[str]              # papéis que apontam p/ este modelo (pode ser >1)
    installed: bool = False       # aparece no /api/tags?
    loaded: bool = False          # aparece no /api/ps (quente, ocupando VRAM)?
    vram_mb: int = 0              # footprint carregado (0 se não está quente)
    disk_mb: int = 0             # tamanho em disco (0 se desconhecido)
    expires_in_s: int | None = None  # segundos até o Ollama liberar; None se n/d


@dataclass(slots=True)
class ModelInventory:
    """Foto do parque de modelos. Serializável para UI/eventos."""

    states: list[ModelState] = field(default_factory=list)
    ollama_ok: bool = False
    loaded_vram_mb: int = 0       # soma dos footprints carregados

    def by_role(self, role: str) -> ModelState | None:
        return next((s for s in self.states if role in s.roles), None)

    def loaded(self) -> list[ModelState]:
        return [s for s in self.states if s.loaded]

    def to_dict(self) -> dict:
        return {
            "ollama_ok": self.ollama_ok,
            "loaded_vram_mb": self.loaded_vram_mb,
            "models": [
                {
                    "name": s.name, "roles": s.roles,
                    "installed": s.installed, "loaded": s.loaded,
                    "vram_mb": s.vram_mb, "disk_mb": s.disk_mb,
                    "expires_in_s": s.expires_in_s,
                }
                for s in self.states
            ],
        }


def _expires_in_s(raw: str | None) -> int | None:
    """Converte o ISO `expires_at` do Ollama em segundos a partir de agora. Um modelo
    com keep_alive infinito reporta um ano-zero/data absurda → tratamos como None."""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.year < 2000:  # Ollama usa data sentinela p/ "sem expiração"
        return None
    delta = (dt - datetime.now(UTC)).total_seconds()
    return max(0, int(delta))


async def _probe_ps(base_url: str, timeout: float = 3.0) -> dict[str, dict] | None:
    """Modelos carregados: nome→{vram_mb, expires_in_s}. Ollama fora → None."""
    try:
        async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout) as c:
            r = await c.get("/api/ps")
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, ValueError):
        return None
    out: dict[str, dict] = {}
    for m in data.get("models", []):
        name = _norm(m.get("name", "?"))
        out[name] = {
            "vram_mb": int(m.get("size_vram", 0)) // _MB,
            "expires_in_s": _expires_in_s(m.get("expires_at")),
        }
    return out


async def _probe_tags(base_url: str, timeout: float = 3.0) -> dict[str, int] | None:
    """Modelos instalados: nome→tamanho em disco (MB). Ollama fora → None."""
    try:
        async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout) as c:
            r = await c.get("/api/tags")
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, ValueError):
        return None
    return {
        _norm(m.get("name", "?")): int(m.get("size", 0)) // _MB
        for m in data.get("models", [])
    }


class ModelManager:
    """Compõe o inventário a partir dos papéis (config) + estado real (Ollama).

    Read-only. Recebe o mapa papel→modelo (injetável p/ teste); em produção use
    ``roles_from_settings(get_settings())``.
    """

    def __init__(self, roles: dict[str, str], base_url: str = "http://127.0.0.1:11434") -> None:
        self.base_url = base_url
        # agrupa papéis por modelo: um mesmo modelo pode servir a mais de um papel.
        self._by_model: dict[str, list[str]] = {}
        for role, model in roles.items():
            self._by_model.setdefault(_norm(model), []).append(role)

    async def inventory(self) -> ModelInventory:
        tags = await _probe_tags(self.base_url)
        ps = await _probe_ps(self.base_url)
        ollama_ok = tags is not None or ps is not None
        tags = tags or {}
        ps = ps or {}

        states: list[ModelState] = []
        loaded_total = 0
        # 1) todos os modelos com papel declarado (aparecem mesmo se não instalados).
        seen: set[str] = set()
        for model, roles in self._by_model.items():
            seen.add(model)
            hot = ps.get(model)
            vram = hot["vram_mb"] if hot else 0
            loaded_total += vram
            states.append(ModelState(
                name=model, roles=list(roles),
                installed=model in tags, loaded=hot is not None,
                vram_mb=vram, disk_mb=tags.get(model, 0),
                expires_in_s=hot["expires_in_s"] if hot else None,
            ))
        # 2) modelos carregados SEM papel na config (alguém carregou por fora).
        for model, hot in ps.items():
            if model in seen:
                continue
            loaded_total += hot["vram_mb"]
            states.append(ModelState(
                name=model, roles=[], installed=model in tags, loaded=True,
                vram_mb=hot["vram_mb"], disk_mb=tags.get(model, 0),
                expires_in_s=hot["expires_in_s"],
            ))
        return ModelInventory(states=states, ollama_ok=ollama_ok, loaded_vram_mb=loaded_total)
