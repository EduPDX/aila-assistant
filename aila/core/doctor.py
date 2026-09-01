"""Diagnóstico operacional da instalação da Aila, sem expor segredos."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from aila.core.config import DATA_ROOT, Settings, data_path, get_settings
from aila.core.hardware import GpuReading, monitor
from aila.llm.base import LLMBackend
from aila.llm.registry import get_backend


@dataclass(slots=True)
class Check:
    name: str
    status: str                 # ok|warn|fail
    detail: str
    action: str = ""


def _db_check(path: Path) -> Check:
    if not path.exists():
        return Check(f"db:{path.name}", "warn", "ainda não criado", "inicie a Aila uma vez")
    try:
        uri = path.resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()
        healthy = bool(result and result[0] == "ok")
        return Check(f"db:{path.name}", "ok" if healthy else "fail", str(result[0]))
    except (OSError, sqlite3.Error) as exc:
        return Check(f"db:{path.name}", "fail", str(exc), "restaure o backup do banco")


def _model_key(name: str) -> str:
    value = (name or "").strip().casefold()
    return value[:-7] if value.endswith(":latest") else value


def _path_checks(settings: Settings) -> list[Check]:
    checks: list[Check] = []
    roots = [settings.sandbox_path(), data_path("data"), data_path("logs")]
    for root in roots:
        parent = root if root.exists() else root.parent
        writable = parent.exists() and os.access(parent, os.W_OK)
        checks.append(Check(
            f"pasta:{root.name}", "ok" if writable else "fail",
            str(root), "verifique as permissões da pasta" if not writable else "",
        ))
    free_gb = shutil.disk_usage(DATA_ROOT).free / (1024 ** 3)
    status = "ok" if free_gb >= 5 else ("warn" if free_gb >= 1 else "fail")
    checks.append(Check(
        "disco", status, f"{free_gb:.1f} GB livres em {DATA_ROOT.anchor}",
        "libere pelo menos 5 GB" if status != "ok" else "",
    ))
    broad = {str(Path.home()), Path.home().anchor, "C:\\", "E:\\", "/"}
    unsafe = [p for p in settings.security.write_roots if str(Path(p).expanduser()) in broad]
    checks.append(Check(
        "sandbox", "fail" if unsafe else "ok",
        "raízes amplas: " + ", ".join(unsafe) if unsafe else "raízes de escrita restritas",
        "remova raízes de disco/home" if unsafe else "",
    ))
    return checks


async def run_doctor(
    settings: Settings,
    backend: LLMBackend,
    *,
    gpu: GpuReading | None = None,
) -> list[Check]:
    checks = [
        Check("python", "ok" if sys.version_info >= (3, 11) else "fail", sys.version.split()[0]),
        *_path_checks(settings),
    ]
    online = await backend.health()
    checks.append(Check(
        "ollama", "ok" if online else "fail", settings.llm.base_url,
        "inicie com: ollama serve" if not online else "",
    ))
    if online:
        installed = set(await backend.list_models())
        installed_keys = {_model_key(model) for model in installed}
        required = [settings.llm.model, settings.llm.code_model, settings.memory.embed_model]
        if settings.llm.fast_model:
            required.append(settings.llm.fast_model)
        missing = [
            model for model in dict.fromkeys(required)
            if model and _model_key(model) not in installed_keys
        ]
        checks.append(Check(
            "modelos", "warn" if missing else "ok",
            "ausentes: " + ", ".join(missing) if missing else f"{len(installed)} instalados",
            "ollama pull " + missing[0] if missing else "",
        ))
    gpu = gpu if gpu is not None else await monitor.gpu_async(fresh=True)
    checks.append(Check(
        "gpu", "ok" if gpu else "warn",
        f"{gpu.name} — {gpu.free_mb:.0f}/{gpu.total_mb:.0f} MB livres" if gpu else "não detectada",
        "verifique o driver NVIDIA" if not gpu else "",
    ))
    checks.extend([
        _db_check(data_path("data/aila.db")),
        _db_check(data_path(settings.memory.db_path)),
    ])
    enabled_external = [name for name, cfg in settings.providers.items() if cfg.enabled]
    checks.append(Check(
        "provedores", "ok", f"{len(enabled_external)} externo(s) habilitado(s): "
        + (", ".join(enabled_external) if enabled_external else "nenhum"),
    ))
    return checks


async def _main(as_json: bool) -> int:
    settings = get_settings()
    backend = get_backend(settings.llm)
    try:
        checks = await run_doctor(settings, backend)
    finally:
        await backend.aclose()
    if as_json:
        print(json.dumps([asdict(check) for check in checks], ensure_ascii=False, indent=2))
    else:
        icons = {"ok": "OK", "warn": "AVISO", "fail": "FALHA"}
        for check in checks:
            line = f"[{icons[check.status]}] {check.name}: {check.detail}"
            if check.action:
                line += f" — ação: {check.action}"
            print(line)
    return 1 if any(check.status == "fail" for check in checks) else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnóstico seguro da instalação da Aila")
    parser.add_argument("--json", action="store_true", help="emite JSON")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_main(args.json)))


if __name__ == "__main__":
    main()
