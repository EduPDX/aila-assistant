"""Registro de PROJETOS externos com code graph próprio.

Cada projeto que o usuário anexa (uma pasta local) ganha:
  - data/projects/<slug>/code_graph.db  → o Code Graph daquele projeto
  - uma entrada em data/projects/index.json com os metadados

Local-first: o backend LÊ a pasta local direto (mesma máquina) e só varre .py —
nunca escreve no projeto do usuário. O construtor é o mesmo CodeGraph da Aila,
que já aceita um root arbitrário.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from aila.core.config import data_path
from aila.core.logging import get_logger

log = get_logger("projects")

_SLUG = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    s = _SLUG.sub("-", name.lower()).strip("-")
    return s or "projeto"


class ProjectRegistry:
    """Lista/adiciona/remove projetos e serve o GraphStore de cada um."""

    def __init__(self) -> None:
        self.root = Path(data_path("data/projects"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"
        self._stores: dict[str, Any] = {}   # slug -> GraphStore (lazy, cacheado)

    # ------------------------------------------------------------- índice
    def _load(self) -> list[dict]:
        if not self.index_path.exists():
            return []
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return []

    def _save(self, items: list[dict]) -> None:
        self.index_path.write_text(json.dumps(items, ensure_ascii=False, indent=2),
                                   encoding="utf-8")

    def list(self) -> list[dict]:
        return self._load()

    def get(self, slug: str) -> dict | None:
        return next((p for p in self._load() if p["slug"] == slug), None)

    # ------------------------------------------------------------- ativo
    # O projeto ATIVO é aquele em que a Aila está "trabalhando": as ferramentas
    # de code graph do code_agent passam a consultar o grafo dele (não o da Aila).
    @property
    def _active_path(self) -> Path:
        return self.root / "active"

    def active(self) -> str | None:
        try:
            s = self._active_path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return s if s and self.get(s) else None

    def set_active(self, slug: str | None) -> str | None:
        if slug and not self.get(slug):
            raise KeyError(slug)
        self._active_path.write_text(slug or "", encoding="utf-8")
        return slug or None

    def rebuild(self, slug: str) -> dict:
        """Reconstrói o grafo do projeto a partir da pasta registrada."""
        meta = self.get(slug)
        if not meta:
            raise KeyError(slug)
        return self.add(meta["path"], meta.get("name"))

    def _unique_slug(self, base: str, items: list[dict]) -> str:
        slug, taken, i = base, {p["slug"] for p in items}, 2
        while slug in taken:
            slug, i = f"{base}-{i}", i + 1
        return slug

    # ------------------------------------------------------------- store
    def store(self, slug: str):
        """GraphStore (cacheado) do projeto — p/ visualização/consulta."""
        if slug not in self._stores:
            from aila.cognition.graph import GraphStore

            db = self.root / slug / "code_graph.db"
            if not db.exists():
                raise FileNotFoundError(f"projeto '{slug}' sem grafo")
            self._stores[slug] = GraphStore(db)
        return self._stores[slug]

    # ------------------------------------------------------------- add/build
    def add(self, path: str, name: str | None = None) -> dict:
        """Valida a pasta, constrói o Code Graph e registra. Idempotente por
        caminho: reanexar a MESMA pasta reconstrói o grafo do projeto existente."""
        from aila.cognition.graph import CodeGraph, GraphStore

        src = Path(path).expanduser()
        if not src.exists() or not src.is_dir():
            raise NotADirectoryError(f"não é uma pasta válida: {path}")
        src = src.resolve()

        items = self._load()
        existing = next((p for p in items if p.get("path") == str(src)), None)
        slug = existing["slug"] if existing else \
            self._unique_slug(_slugify(name or src.name), items)

        proj_dir = self.root / slug
        proj_dir.mkdir(parents=True, exist_ok=True)
        db = proj_dir / "code_graph.db"
        # reconstrói do zero (grafo é derivado da pasta). FECHA o store cacheado
        # antes de apagar o .db — no Windows um arquivo aberto não pode ser removido.
        old = self._stores.pop(slug, None)
        if old is not None:
            old.close()
        for ext in ("", "-wal", "-shm"):
            Path(f"{db}{ext}").unlink(missing_ok=True)

        st = GraphStore(db)
        t0 = time.time()
        rep = CodeGraph(st, src).build()
        st.recompute_importance()
        counts = st.counts()
        st.close()

        meta = {
            "slug": slug,
            "name": name or (existing or {}).get("name") or src.name,
            "path": str(src),
            "nodes": counts["nodes"],
            "edges": counts["edges"],
            "by_type": counts.get("by_type", {}),
            "files": rep.get("files", 0),
            "built_ms": int((time.time() - t0) * 1000),
            "created_at": (existing or {}).get("created_at") or _now(),
            "updated_at": _now(),
        }
        items = [p for p in items if p["slug"] != slug]
        items.append(meta)
        self._save(items)
        log.info(f"projeto '{slug}' construído: {counts} de {src}")
        return meta

    def remove(self, slug: str) -> bool:
        import shutil

        items = self._load()
        if not any(p["slug"] == slug for p in items):
            return False
        st = self._stores.pop(slug, None)
        if st is not None:
            st.close()
        shutil.rmtree(self.root / slug, ignore_errors=True)
        if self.active() == slug:          # removeu o ativo → volta p/ o código da Aila
            self.set_active(None)
        self._save([p for p in items if p["slug"] != slug])
        return True


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


_registry: ProjectRegistry | None = None


def get_registry() -> ProjectRegistry:
    global _registry
    if _registry is None:
        _registry = ProjectRegistry()
    return _registry
