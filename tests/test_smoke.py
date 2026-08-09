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


def test_vision_agent_sends_image(tmp_path: Path):
    """Vision Agent codifica a imagem em base64 e a envia ao modelo (RO permitido)."""
    from aila.agents.base import AgentDeps
    from aila.agents.vision_agent import VisionAgent

    captured = {}

    class FakeLLM:
        async def complete(self, messages, *, model=None, **kw):
            captured["messages"] = messages
            captured["model"] = model
            return "uma imagem de teste"

    s = get_settings()
    s.security.read_only = True  # visão deve funcionar mesmo em somente-leitura
    audit = AuditLog(tmp_path / "a.jsonl")
    pm = PermissionManager(s.security, audit)
    sandbox = PathSandbox(tmp_path / "ws")
    deps = AgentDeps(settings=s, permissions=pm, sandbox=sandbox, llm=FakeLLM())
    tools = {t.name: t for t in VisionAgent(deps).tools()}

    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d494844520000000100000001010600000"
        "01f15c4890000000a49444154789c6300010000050001"
    )
    (sandbox.root / "img.png").write_bytes(png)

    async def go():
        r = await tools["vision.analyze_image"].handler({"path": "img.png"})
        assert r.ok
        assert "images" in captured["messages"][0]
        assert captured["model"]  # usa o modelo de visão configurado
        err = await tools["vision.analyze_image"].handler({"path": "nao.png"})
        assert not err.ok  # imagem inexistente -> erro amigável

    asyncio.run(go())


def test_lipsync_envelope(tmp_path: Path):
    """A envoltória de amplitude acompanha o volume do áudio (boca abre/fecha)."""
    import math
    import wave

    from aila.avatar.lipsync import amplitude_envelope

    # WAV sintético: 1s de silêncio + 1s de tom alto (deve dar boca fechada->aberta)
    sr = 16000
    path = tmp_path / "tone.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        frames = bytearray()
        for _ in range(sr):  # silêncio
            frames += (0).to_bytes(2, "little", signed=True)
        for i in range(sr):  # tom
            val = int(30000 * math.sin(2 * math.pi * 220 * i / sr))
            frames += val.to_bytes(2, "little", signed=True)
        w.writeframes(bytes(frames))

    env, dur = amplitude_envelope(str(path), fps=30)
    assert 1.9 < dur < 2.1
    assert min(env) < 0.1 and max(env) > 0.8   # varia de fechada a aberta


def test_osc_avatar_bridge_mapping():
    """A ponte OSC mapeia o AvatarState para os endereços /aila/* corretos."""
    pytest.importorskip("pythonosc")
    from aila.avatar.emotion_engine import EmotionEngine
    from aila.avatar.osc_bridge import OSCAvatarBridge

    sent = []

    class FakeClient:
        def send_message(self, addr, val):
            sent.append((addr, val))

    bridge = OSCAvatarBridge.__new__(OSCAvatarBridge)  # sem abrir socket
    bridge.client = FakeClient()
    bridge.send(EmotionEngine().from_text("Pronto, funcionou!").to_event_payload())

    addrs = {a for a, _ in sent}
    assert {"/aila/emotion", "/aila/gesture", "/aila/animation", "/aila/speech",
            "/aila/intensity"} <= addrs
    assert ("/aila/emotion", "happy") in sent


def test_web_search_parser():
    """O parser do DuckDuckGo extrai título, URL real e resumo (sem rede)."""
    from aila.agents.web_agent import WebAgent, _real_url

    # o DDG embrulha o link real no parâmetro uddg de um redirect
    assert _real_url("//duckduckgo.com/l/?uddg=https%3A%2F%2Fpython.org%2Fx&rut=z") == \
        "https://python.org/x"

    page = """
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexemplo.com%2Fa&rut=1">
      Primeiro <b>Resultado</b></a>
    <a class="result__snippet" href="x">Resumo do primeiro &amp; tal.</a>
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexemplo.com%2Fb&rut=2">Segundo</a>
    <a class="result__snippet" href="y">Resumo dois.</a>
    """
    out = WebAgent._parse_results(page, 5)
    assert len(out) == 2
    assert out[0]["title"] == "Primeiro Resultado"
    assert out[0]["url"] == "https://exemplo.com/a"
    assert out[0]["snippet"] == "Resumo do primeiro & tal."
    assert out[1]["url"] == "https://exemplo.com/b"


def test_text_tool_call_fallback():
    """Modelos que emitem a tool-call como TEXTO (ex.: qwen-coder) são parseados."""
    from aila.core.engine import extract_text_tool_calls, strip_tool_call_text

    class Reg:
        def get(self, n):
            return object() if n in {"web.search", "computer.run_command"} else None

    reg = Reg()
    # formato name/arguments dentro de bloco cercado (o que o app mostrou)
    txt = 'Vou buscar.\n```json\n{"name": "web.search", "arguments": {"query": "IA"}}\n```'
    calls = extract_text_tool_calls(txt, reg)
    assert calls == [{"function": {"name": "web.search", "arguments": {"query": "IA"}}}]
    # formato tool/args, bare
    calls2 = extract_text_tool_calls('{"tool":"computer.run_command","args":{"command":"Get-Date"}}', reg)
    assert calls2[0]["function"]["name"] == "computer.run_command"
    # nome desconhecido é ignorado (não vira tool-call)
    assert extract_text_tool_calls('{"tool":"inexistente","args":{}}', reg) == []
    # a prosa sobra depois de remover o bloco de código
    assert strip_tool_call_text(txt) == "Vou buscar."


def test_behavior_planner_reads_meaning():
    """O Behavior Planner deriva intenção/gesto/olhar do SIGNIFICADO + tools."""
    from aila.avatar.behavior_planner import BehaviorPlanner

    p = BehaviorPlanner()
    # saudação -> gesto de aceno
    g = p.plan("Olá! Como posso ajudar?")
    assert g.intent == "greeting" and g.gestures[0].type == "wave"
    # tool de busca -> intenção search, olhar deslocado
    s = p.plan("Aqui estão as novidades.", tools_used=["web.search"])
    assert s.intent == "search" and s.gaze == "wander"
    # tool de código -> coding, olhar na tela, menos energia
    c = p.plan("Segue o código.", tools_used=["code.generate", "code.run"])
    assert c.intent == "coding" and c.gaze == "screen" and c.motion.amplitude < 1.0
    # erro -> intenção error, emoção confusa, olhar baixo
    e = p.plan("Desculpe, deu um erro.")
    assert e.intent == "error" and e.gaze == "down"
    # duração estimada cresce com o tamanho do texto
    assert p.plan("x" * 300).est_speech_seconds > p.plan("oi").est_speech_seconds

    # F5: timeline — vários gestos, cada um no tempo da palavra (crescente)
    tl = p.plan("Olá! Recomendo isso. Perfeito, funcionou!")
    types = [g.type for g in tl.gestures]
    assert "wave" in types and "hand_explain" in types and "thumbs_up" in types
    times = [g.at_time for g in tl.gestures]
    assert times == sorted(times) and times[0] == 0.0  # ordenados; saudação em t=0
    assert p.plan("Não, de jeito nenhum.").gestures[0].type == "shake"
    assert p.plan("Sim, com certeza.").gestures[0].type == "nod"


def test_clip_tool_result_for_context():
    """Resultados grandes de ferramenta são cortados (cabeça+cauda) p/ não
    entupir o contexto; pequenos passam intactos."""
    from aila.core.engine import _clip_for_context

    assert _clip_for_context("curto") == "curto"          # pequeno: intacto
    big = "A" * 5000 + "ZFIM"
    clipped = _clip_for_context(big, limit=1200)
    assert len(clipped) < len(big)
    assert clipped.startswith("A")                        # mantém o início
    assert clipped.endswith("ZFIM")                       # mantém o fim
    assert "omitidos" in clipped                          # marca o corte


def test_speech_text_strips_code_and_markdown():
    """O TTS não deve falar código nem os '#'/marcações de markdown."""
    from aila.api.voice import speech_text

    md = "Claro! Veja:\n```python\nx=1  # comenta\n```\n## Título\n* item **b** e `cod` e [x](https://a.com)."
    out = speech_text(md)
    assert "```" not in out and "#" not in out and "*" not in out and "`" not in out
    assert "https://" not in out
    assert "x=1" not in out          # o código em si não é falado
    assert "Claro! Veja:" in out and "Título" in out and "item b" in out


def test_web_search_filters_ads():
    """Anúncios do DuckDuckGo (y.js/ad_domain) são descartados; orgânicos ficam."""
    from aila.agents.web_agent import WebAgent, _is_ad

    assert _is_ad("//duckduckgo.com/y.js?ad_domain=x&ad_provider=bing")
    assert not _is_ad("//duckduckgo.com/l/?uddg=https%3A%2F%2Freal.com")
    page = (
        '<a class="result__a" href="//duckduckgo.com/y.js?ad_domain=loja.com&ad_type=txad">Anúncio</a>'
        '<a class="result__snippet" href="x">compre já</a>'
        '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fnoticia.com%2Fia&rut=1">Notícia real</a>'
        '<a class="result__snippet" href="y">resumo da notícia</a>'
    )
    out = WebAgent._parse_results(page, 5)
    assert len(out) == 1                       # só o orgânico
    assert out[0]["url"] == "https://noticia.com/ia"
    assert out[0]["title"] == "Notícia real"


def test_web_search_is_readonly_allowed(tmp_path: Path):
    """web.search/web.fetch são leitura: permitidas mesmo em modo somente-leitura."""
    from aila.security.permissions import PermissionManager

    s = get_settings()
    s.security.read_only = True
    pm = PermissionManager(s.security, AuditLog(tmp_path / "a.jsonl"))

    async def go():
        await pm.check("web.search", "web", {"query": "x"})   # não levanta
        await pm.check("web.page.get", "web", {"url": "x"})    # não levanta

    asyncio.run(go())


def test_binary_agent_triage(tmp_path: Path):
    """Triagem de binário funciona em modo somente-leitura (identify/entropy)."""
    from aila.agents.base import AgentDeps
    from aila.agents.binary_agent import BinaryAgent

    s = get_settings()
    s.security.read_only = True
    audit = AuditLog(tmp_path / "a.jsonl")
    pm = PermissionManager(s.security, audit)
    sandbox = PathSandbox(tmp_path / "ws")
    deps = AgentDeps(settings=s, permissions=pm, sandbox=sandbox, llm=None)
    tools = {t.name: t for t in BinaryAgent(deps).tools()}

    (sandbox.root / "fake.exe").write_bytes(b"MZ" + bytes(range(256)) * 4)

    async def go():
        r = await tools["binary.identify"].handler({"path": "fake.exe"})
        assert r.ok and "Windows" in r.content
        r = await tools["binary.entropy"].handler({"path": "fake.exe"})
        assert r.ok and "Entropia" in r.content
        # sem Ghidra configurado -> erro amigável, não exceção
        r = await tools["binary.decompile"].handler({"path": "fake.exe"})
        assert not r.ok and "Ghidra" in r.content

    asyncio.run(go())


def test_tts_sapi_synthesis(tmp_path: Path):
    """No Windows, o TTS SAPI gera um WAV não-vazio (a Aila fala)."""
    import sys

    if sys.platform != "win32":
        pytest.skip("SAPI só existe no Windows")
    from aila.voice.tts import TextToSpeech

    out = TextToSpeech(engine="sapi").synthesize("Teste de voz da Aila.", tmp_path / "v.wav")
    assert out.exists() and out.stat().st_size > 1000


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
