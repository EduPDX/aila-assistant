"""Testes de fumaça: verificam que o núcleo importa e funciona sem um LLM.

Rode com:  pytest -q
Não exigem Ollama — usam um backend falso.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from aila.core.config import get_settings
from aila.security.audit import AuditLog
from aila.security.permissions import PermissionDenied, PermissionManager
from aila.security.sandbox import PathSandbox, SandboxViolation


def test_config_loads():
    s = get_settings()
    assert s.app.name
    assert s.llm.backend in {"ollama", "llamacpp"}


def test_sandbox_blocks_escape(tmp_path: Path):
    sb = PathSandbox(tmp_path)
    inside = sb.resolve("sub/file.txt")
    assert str(inside).startswith(str(tmp_path.resolve()))
    with pytest.raises(SandboxViolation):
        sb.resolve("../../etc/passwd")


def test_readonly_blocks_writes(tmp_path: Path):
    s = get_settings()
    s.security.read_only = True
    audit = AuditLog(tmp_path / "audit.jsonl")
    pm = PermissionManager(s.security, audit)

    async def go():
        await pm.check("file.read", "file", {})  # leitura: ok
        with pytest.raises(PermissionDenied):
            await pm.check("file.write", "file", {"path": "x"})  # escrita: bloqueada

    asyncio.run(go())


def test_emotion_engine():
    from aila.avatar.emotion_engine import EmotionEngine
    from aila.avatar.protocol import Emotion

    eng = EmotionEngine()
    assert eng.from_text("Encontrei um erro no traceback").emotion == Emotion.CONFUSED
    assert eng.from_text("Pronto, funcionou!").emotion == Emotion.HAPPY
