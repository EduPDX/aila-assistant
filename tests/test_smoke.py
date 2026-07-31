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


def test_memory_store_search(tmp_path: Path):
    """Busca semântica retorna o item mais similar (embeddings falsos)."""
    from aila.memory.store import MemoryStore

    # embedding falso: bag-of-words sobre um vocabulário fixo -> vetores comparáveis
    vocab = ["python", "gato", "carro", "azul", "aila", "erro"]

    async def fake_embed(texts):
        out = []
        for t in texts:
            tl = t.lower()
            out.append([float(tl.count(w)) + 0.01 for w in vocab])
        return out

    async def go():
        mem = MemoryStore(tmp_path / "mem.db", fake_embed)
        await mem.add("gosto muito de python e programação")
        await mem.add("meu gato é azul")
        await mem.add("o carro quebrou com um erro")
        assert mem.count() == 3
        hits = await mem.search("qual linguagem python eu curto?", top_k=1)
        assert hits and "python" in hits[0].text

    asyncio.run(go())


def test_computer_agent_gating(tmp_path: Path):
    """Leitura liberada em read-only; atuação (teclado) bloqueada."""
    pytest.importorskip("pyautogui")
    from aila.agents.base import AgentDeps
    from aila.agents.computer_agent import ComputerAgent

    s = get_settings()
    s.security.read_only = True
    s.security.confirm_destructive = False
    audit = AuditLog(tmp_path / "audit.jsonl")
    pm = PermissionManager(s.security, audit)
    deps = AgentDeps(settings=s, permissions=pm, sandbox=PathSandbox(tmp_path / "ws"), llm=None)
    tools = {t.name: t for t in ComputerAgent(deps).tools()}

    async def go():
        r = await tools["computer.screen_info"].handler({})
        assert r.ok  # leitura permitida
        with pytest.raises(PermissionDenied):
            await tools["computer.type"].handler({"text": "x"})  # atuação bloqueada

    asyncio.run(go())
