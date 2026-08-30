"""Testes E2E do laço principal — user_text → engine.process() → resposta.

Semente da rede de ponta a ponta (Master Plan, Fase 3): dirige o
``AilaEngine`` real montado por ``build_engine`` com um ``FakeLLM`` determinístico
(sem Ollama, sem rede), cobrindo os dois caminhos essenciais:

  1. conversa feliz  — o modelo responde texto puro;
  2. laço de ferramenta — o modelo pede UMA tool, que executa e realimenta a
     resposta final.

Estes testes existem para PROTEGER o refactor do engine (Fase 2): qualquer
extração de responsabilidade tem de manter o contrato observável abaixo
(eventos emitidos + texto retornado) intacto.
"""

from __future__ import annotations

import asyncio

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
