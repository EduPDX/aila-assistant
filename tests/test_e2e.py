"""Testes E2E do laço principal — user_text → engine.process() → resposta.

Rede de ponta a ponta (Master Plan, Fase 3): dirige o ``AilaEngine`` real
montado por ``build_engine`` com um ``FakeLLM`` determinístico (sem Ollama, sem
rede), cobrindo os caminhos críticos do laço:

  1. conversa feliz          — o modelo responde texto puro;
  2. laço de ferramenta      — o modelo pede UMA tool, que executa e realimenta;
  3. timeout de ferramenta   — a tool estoura o tempo → erro, o turno se recupera;
  4. negação de permissão    — ação DANGER sem handler → erro, o turno se recupera;
  5. fallback de provedor    — o 1º provedor cai → o 2º da cadeia responde;
  6. cancelamento            — cancelar o turno propaga CancelledError, sem travar;
  7. memória save/recall     — a troca é gravada e recuperada no turno seguinte.

Estes testes existem para PROTEGER o refactor do engine (Fase 2): qualquer
extração de responsabilidade tem de manter o contrato observável abaixo
(eventos emitidos + texto retornado) intacto.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

import pytest

from aila.core.config import get_settings
from aila.core.engine import build_engine
from aila.llm.base import ChatChunk, LLMBackend, ModelCapabilities
from aila.tools.schema import Tool, ToolResult


def _base_settings():
    """Config mínima e OFFLINE: sem memória (sem embeddings), sem roteamento
    externo, autonomia padrão. Cada teste parte de um estado limpo."""
    s = get_settings()
    s.memory.enabled = False        # sem embeddings/RAG neste teste
    s.routing.enabled = False       # passthrough p/ o backend local (o FakeLLM)
    s.security.autonomy_level = 3   # developer: nada bloqueia uma tool SAFE
    return s


def _collect_emit(events: list[tuple[str, dict]]):
    async def emit(ev: str, payload: dict) -> None:
        events.append((ev, payload))
    return emit


# --------------------------------------------------------------------------- #
def test_e2e_happy_path_chat():
    """Fluxo feliz: o modelo responde texto puro. O engine deve streamar tokens,
    emitir a mensagem final e devolver o texto — sem invocar ferramentas."""
    reply = "Claro! Posso ajudar com o que você precisar."

    class FakeLLM(LLMBackend):
        name = "ollama"
        default_model = "fake"

        def capabilities(self, model=None):
            return ModelCapabilities(local=True)

        async def chat(self, messages, **k):
            # streama em dois pedaços p/ exercitar o acúmulo de tokens
            yield ChatChunk(content=reply[:12])
            yield ChatChunk(content=reply[12:], done=True)

        async def complete(self, messages, **k):
            return reply

        async def list_models(self):
            return ["fake"]

        async def health(self):
            return True

    eng = build_engine(_base_settings(), FakeLLM())
    events: list[tuple[str, dict]] = []

    async def go():
        out = await eng.process("olá, tudo bem?", _collect_emit(events), mode="chat")
        # contrato: devolve o texto do modelo
        assert reply in out
        kinds = [e for e, _ in events]
        # streamou tokens e fechou com a mensagem final
        assert "assistant.token" in kinds
        assert "assistant.message" in kinds
        final = next(p for e, p in events if e == "assistant.message")
        assert reply in final["text"]
        # conversa pura: NENHUMA ferramenta foi invocada
        assert "agent.invoked" not in kinds

    asyncio.run(go())


# --------------------------------------------------------------------------- #
def test_e2e_self_model_binds_capabilities():
    """Autoconhecimento: o engine chama bind_capabilities no boot, então
    self_model.state() reporta as capacidades REAIS (derivadas das ferramentas
    registradas) em vez de uma lista vazia. Antes, state() mentia sobre si."""

    class FakeLLM(LLMBackend):
        name = "ollama"
        default_model = "fake"

        def capabilities(self, model=None):
            return ModelCapabilities(local=True)

        async def chat(self, messages, **k):
            yield ChatChunk(content="ok", done=True)

        async def complete(self, messages, **k):
            return "ok"

        async def list_models(self):
            return ["fake"]

        async def health(self):
            return True

    eng = build_engine(_base_settings(), FakeLLM())
    sm = eng.self_model
    assert sm is not None
    assert sm.capabilities.bound, "bind_capabilities deve ter rodado no boot"
    caps = sm.state().capabilities
    # há ferramentas de arquivo/código registradas por padrão → a lista NÃO é vazia
    assert caps, "state() não pode reportar capacidades vazias"
    assert all(isinstance(c, str) for c in caps)


# --------------------------------------------------------------------------- #
def test_e2e_tool_loop():
    """Laço de ferramenta: o modelo pede UMA tool na 1ª volta, o engine a executa
    e, na 2ª volta, o modelo responde o texto final. Verifica que a tool rodou
    de fato (handler chamado) e que os eventos agent.invoked/result saíram."""
    calls: list[dict] = []   # registra que o handler REALMENTE rodou

    async def _echo(args: dict) -> ToolResult:
        calls.append(args)
        return ToolResult.success(f"eco: {args.get('texto', '')}")

    echo_tool = Tool(
        name="test.echo",
        description="Ferramenta de teste: devolve o texto recebido.",
        params=[],
        handler=_echo,
        agent="test",
    )

    final_reply = "Pronto — a ferramenta respondeu."

    class ToolThenText(LLMBackend):
        """1ª chamada → pede test.echo; 2ª chamada → responde texto final."""
        name = "ollama"
        default_model = "fake"

        def __init__(self) -> None:
            self._turn = 0

        def capabilities(self, model=None):
            return ModelCapabilities(local=True, tools=True)

        async def chat(self, messages, **k):
            self._turn += 1
            if self._turn == 1:
                yield ChatChunk(
                    content="",
                    done=True,
                    tool_calls=[{
                        "function": {
                            "name": "test.echo",
                            "arguments": {"texto": "olá do teste"},
                        }
                    }],
                )
            else:
                yield ChatChunk(content=final_reply, done=True)

        async def complete(self, messages, **k):
            return final_reply

        async def list_models(self):
            return ["fake"]

        async def health(self):
            return True

    eng = build_engine(_base_settings(), ToolThenText())
    eng.agents.registry.register(echo_tool)   # injeta a tool de teste no registry
    events: list[tuple[str, dict]] = []

    async def go():
        out = await eng.process(
            "use a ferramenta de teste, por favor", _collect_emit(events), mode="auto"
        )
        # a tool foi REALMENTE executada, uma vez, com os args certos
        assert calls == [{"texto": "olá do teste"}]
        kinds = [e for e, _ in events]
        assert "agent.invoked" in kinds
        assert "agent.result" in kinds
        invoked = next(p for e, p in events if e == "agent.invoked")
        assert invoked["tool"] == "test.echo"
        result = next(p for e, p in events if e == "agent.result")
        assert result["ok"] is True and "eco: olá do teste" in result["content"]
        # e a resposta final (2ª volta do modelo) é entregue
        assert final_reply in out

    asyncio.run(go())


def test_e2e_personal_file_request_recovers_from_narration_without_writing():
    """Pedido explícito de salvar não pode terminar em mera instrução ao usuário.

    A primeira resposta narra; o engine dá um único lembrete; a segunda chama a
    tool. O executor é substituído por stub para não tocar na pasta Documentos.
    """
    turns = 0
    executed: list[tuple[str, dict]] = []

    class NarrateThenWrite(LLMBackend):
        name = "ollama"
        default_model = "fake"

        def capabilities(self, model=None):
            return ModelCapabilities(local=True, tools=True)

        async def chat(self, messages, **k):
            nonlocal turns
            turns += 1
            if turns == 1:
                yield ChatChunk(content="Aqui está o código; salve-o em Documentos.", done=True)
            elif turns == 2:
                yield ChatChunk(content="", done=True, tool_calls=[{
                    "function": {
                        "name": "file.write",
                        "arguments": {"path": "Jogo.java", "content": "class Jogo {}"},
                    }
                }])
            else:
                yield ChatChunk(content="Pronto, salvei o arquivo.", done=True)

        async def complete(self, messages, **k):
            return "Pronto, salvei o arquivo."

        async def list_models(self):
            return ["fake"]

        async def health(self):
            return True

    eng = build_engine(_base_settings(), NarrateThenWrite())

    async def fake_execute(name: str, args: dict) -> ToolResult:
        executed.append((name, args))
        return ToolResult.success("arquivo salvo")

    eng.agents.registry.execute = fake_execute

    async def go():
        out = await eng.process(
            "Crie um jogo em Java e salve em Documentos como Jogo.java",
            _collect_emit([]),
            mode="auto",
        )
        assert "Pronto" in out
        assert turns == 3
        assert len(executed) == 1
        assert executed[0][0] == "file.write"
        assert executed[0][1]["path"].endswith("Documents\\Jogo.java") or executed[0][1][
            "path"
        ].endswith("Documentos\\Jogo.java")

    asyncio.run(go())


# --------------------------------------------------------------------------- #
class _ToolThenText(LLMBackend):
    """Backend genérico: 1ª chamada pede ``tool_name``; depois responde ``final``."""
    name = "ollama"
    default_model = "fake"

    def __init__(self, tool_name: str, args: dict, final: str) -> None:
        self._turn = 0
        self._tool = tool_name
        self._args = args
        self._final = final

    def capabilities(self, model=None):
        return ModelCapabilities(local=True, tools=True)

    async def chat(self, messages, **k):
        self._turn += 1
        if self._turn == 1:
            yield ChatChunk(content="", done=True, tool_calls=[
                {"function": {"name": self._tool, "arguments": self._args}}])
        else:
            yield ChatChunk(content=self._final, done=True)

    async def complete(self, messages, **k):
        return self._final

    async def list_models(self):
        return ["fake"]

    async def health(self):
        return True


def test_e2e_tool_timeout():
    """A ferramenta estoura o tempo limite do registry → ToolResult de erro; o
    turno NÃO trava e ainda entrega a resposta final."""
    async def _slow(args: dict) -> ToolResult:
        await asyncio.sleep(1.0)
        return ToolResult.success("nunca chega aqui")

    slow_tool = Tool(name="test.slow", description="dorme", params=[],
                     handler=_slow, agent="test")
    eng = build_engine(_base_settings(), _ToolThenText("test.slow", {}, "Ok, concluído."))
    eng.agents.registry.register(slow_tool)
    eng.agents.registry.timeout = 0.2   # backstop curto p/ o teste
    events: list[tuple[str, dict]] = []

    async def go():
        out = await eng.process("use a ferramenta lenta", _collect_emit(events), mode="auto")
        result = next(p for e, p in events if e == "agent.result")
        assert result["ok"] is False and "tempo limite" in result["content"].lower()
        assert "Ok, concluído." in out          # o turno se recuperou

    asyncio.run(go())


def test_e2e_tool_denied():
    """Uma ação DANGER sem handler de confirmação → PermissionDenied vira erro de
    tool (execute captura); o modelo vê o erro e finaliza sem travar."""
    async def _danger(args: dict) -> ToolResult:
        # file.delete é DANGER (destructive); sem confirm handler → PermissionDenied
        await eng.permissions.check("file.delete", "test", {"path": "x"})
        return ToolResult.success("apagado")   # não deve chegar aqui

    tool = Tool(name="test.denyme", description="pede ação perigosa", params=[],
                handler=_danger, agent="test")
    s = _base_settings()
    s.security.confirm_destructive = True       # DANGER exige confirmação
    eng = build_engine(s, _ToolThenText("test.denyme", {}, "Não pude apagar, então parei."))
    eng.agents.registry.register(tool)
    events: list[tuple[str, dict]] = []

    async def go():
        out = await eng.process("apague o arquivo", _collect_emit(events), mode="auto")
        result = next(p for e, p in events if e == "agent.result")
        assert result["ok"] is False            # a ação foi negada
        assert "Não pude apagar" in out         # e o turno terminou com resposta natural

    asyncio.run(go())


def test_e2e_provider_fallback():
    """O 1º provedor da cadeia levanta exceção → o engine cai para o 2º provedor
    (ambos locais) e entrega a resposta dele, emitindo model.selected fallback."""
    reply = "Resposta do provedor reserva."

    class Down(LLMBackend):
        name = "ollama"          # é o 'local' (default) da cadeia
        default_model = "fake"
        def capabilities(self, model=None):
            return ModelCapabilities(local=True)
        async def chat(self, messages, **k):
            raise RuntimeError("provedor caiu")
            yield  # torna a assinatura um async generator (inalcançável)
        async def complete(self, messages, **k):
            return ""
        async def list_models(self):
            return ["fake"]
        async def health(self):
            return True

    class Backup(LLMBackend):
        name = "local2"
        default_model = "fake2"
        def capabilities(self, model=None):
            return ModelCapabilities(local=True)
        async def chat(self, messages, **k):
            yield ChatChunk(content=reply, done=True)
        async def complete(self, messages, **k):
            return reply
        async def list_models(self):
            return ["fake2"]
        async def health(self):
            return True

    s = _base_settings()
    s.routing.enabled = True
    s.routing.default = "local"
    s.routing.rules = {"chat": ["local", "local2"]}   # cai do local p/ o local2
    eng = build_engine(s, Down())
    eng.router.providers["local2"] = Backup()         # registra o reserva na cadeia
    events: list[tuple[str, dict]] = []

    async def go():
        out = await eng.process("olá", _collect_emit(events), mode="chat")
        assert reply in out
        assert any(p.get("fallback") for e, p in events if e == "model.selected")

    asyncio.run(go())


def test_e2e_cancellation():
    """Cancelar o turno em andamento propaga CancelledError e não trava o loop."""
    class Slow(LLMBackend):
        name = "ollama"
        default_model = "fake"
        def capabilities(self, model=None):
            return ModelCapabilities(local=True)
        async def chat(self, messages, **k):
            await asyncio.sleep(5)      # o cancelamento chega aqui
            yield ChatChunk(content="tarde demais", done=True)
        async def complete(self, messages, **k):
            return ""
        async def list_models(self):
            return ["fake"]
        async def health(self):
            return True

    eng = build_engine(_base_settings(), Slow())

    async def go():
        task = asyncio.create_task(eng.process("oi", _collect_emit([]), mode="chat"))
        await asyncio.sleep(0.1)        # deixa o turno começar
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(go())


def test_e2e_memory_save_and_recall():
    """Com memória ligada: a troca do 1º turno é gravada e RECUPERADA no 2º turno
    (evento memory.recalled). Isolado num DB temporário — não toca dados reais."""
    tmp = Path(tempfile.mkdtemp(prefix="aila_mem_"))
    reply = "Seu projeto favorito é a Aila, um agente local."

    class Mem(LLMBackend):
        name = "ollama"
        default_model = "fake"
        def capabilities(self, model=None):
            return ModelCapabilities(local=True)
        async def chat(self, messages, **k):
            yield ChatChunk(content=reply, done=True)
        async def complete(self, messages, **k):
            return reply
        async def embed(self, texts, model=None):
            # vetor CONSTANTE → cosseno 1.0 entre tudo → recall garantido
            return [[1.0, 0.0, 0.0] for _ in texts]
        async def list_models(self):
            return ["fake"]
        async def health(self):
            return True

    s = get_settings()
    s.memory.enabled = True
    s.memory.store_conversations = True
    s.memory.db_path = str(tmp / "mem.db")      # DB temporário isolado
    s.routing.enabled = False
    s.security.autonomy_level = 3

    eng = build_engine(s, Mem())
    # neutraliza efeitos colaterais que escreveriam em dados REAIS:
    eng.store = None                             # sem persistir conversa no DB real
    eng.kgraph = None                            # sem tocar o knowledge.db real
    eng.consolidator = None
    from aila.memory.manager import MemoryManager
    eng.mem = MemoryManager(eng.memory, graph=None)   # recall clássico (episódico)

    try:
        async def go():
            # 1º turno: fala um fato substantivo (>8 chars) → é gravado
            await eng.process("meu projeto favorito é a Aila", _collect_emit([]), mode="chat")
            assert eng.memory.count() >= 1        # gravou a troca

            # 2º turno: pergunta relacionada → deve recuperar a memória
            ev2: list[tuple[str, dict]] = []
            await eng.process("qual meu projeto favorito?", _collect_emit(ev2), mode="chat")
            assert any(e == "memory.recalled" for e, _ in ev2)

        asyncio.run(go())
    finally:
        eng.memory.close()                       # solta o lock do sqlite
        shutil.rmtree(tmp, ignore_errors=True)
