"""Adapta as mensagens do contexto para provedores externos.

O contexto usa o estilo Ollama: ``{role:"tool", name, content}`` e o turno do
assistente com ``tool_calls``. A API OpenAI exige ``tool_call_id`` ligando
resultado↔chamada — frágil de manter entre provedores. Para provedores
EXTERNOS, convertemos o histórico de ferramentas em TEXTO neutro (o modelo
entende, e o parser de tool-call em texto do engine captura novas chamadas).
Para o provedor LOCAL, nada muda (usa o formato nativo).
"""

from __future__ import annotations

import json
from typing import Any


def _fmt_call(call: dict[str, Any]) -> str:
    fn = call.get("function", {})
    args = fn.get("arguments", "")
    if isinstance(args, dict):
        args = json.dumps(args, ensure_ascii=False)
    return f"{fn.get('name', '?')}({args})"


def to_provider_messages(messages: list[dict[str, Any]], local: bool) -> list[dict[str, Any]]:
    """Devolve as mensagens no formato aceito pelo provedor.

    local=True → inalteradas (formato nativo Ollama). local=False → normaliza
    o histórico de ferramentas para texto (compatível com qualquer provedor).
    """
    if local:
        return messages
    out: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role")
        if role == "tool":
            name = m.get("name") or "ferramenta"
            out.append({"role": "user", "content": f"[resultado de {name}]\n{m.get('content', '')}"})
        elif role == "assistant" and m.get("tool_calls"):
            desc = "; ".join(_fmt_call(c) for c in m["tool_calls"])
            content = (m.get("content") or "").strip()
            content = (content + ("\n" if content else "") + f"[chamando ferramenta: {desc}]").strip()
            out.append({"role": "assistant", "content": content})
        else:
            out.append(m)   # system/user/assistant simples já são compatíveis
    return out
