from __future__ import annotations

import asyncio
from pathlib import Path

from aila.core.config import get_settings
from aila.core.doctor import run_doctor
from aila.core.hardware import GpuReading
from aila.llm.base import LLMBackend


class _HealthyBackend(LLMBackend):
    async def chat(self, messages, **kwargs):
        if False:
            yield

    async def complete(self, messages, **kwargs):
        return ""

    async def list_models(self):
        return [
            "qwen2.5:7b-instruct",
            "qwen2.5-coder:7b",
            "qwen2.5:3b-instruct",
            "nomic-embed-text:latest",
        ]

    async def health(self):
        return True


def test_doctor_reports_core_health_without_secrets(tmp_path: Path):
    settings = get_settings().model_copy(deep=True)
    settings.security.sandbox_root = str(tmp_path / "workspace")
    settings.security.write_roots = [str(tmp_path)]
    gpu = GpuReading("RTX Test", 10, 8192, 2048, 6144, 45)
    checks = asyncio.run(run_doctor(settings, _HealthyBackend(), gpu=gpu))
    by_name = {check.name: check for check in checks}
    assert by_name["python"].status == "ok"
    assert by_name["ollama"].status == "ok"
    assert by_name["modelos"].status == "ok"
    assert by_name["gpu"].status == "ok"
    assert by_name["sandbox"].status == "ok"
    assert "api_key" not in str(checks).lower()


def test_doctor_flags_broad_write_root(tmp_path: Path):
    settings = get_settings().model_copy(deep=True)
    settings.security.sandbox_root = str(tmp_path)
    settings.security.write_roots = [Path.home().anchor]
    checks = asyncio.run(run_doctor(settings, _HealthyBackend(), gpu=None))
    sandbox = next(check for check in checks if check.name == "sandbox")
    assert sandbox.status == "fail"
