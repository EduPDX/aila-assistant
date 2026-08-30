"""Parsing de tool-call em TEXTO: modelos que emitem a chamada de ferramenta
como prosa/JSON (ex.: qwen-coder) em vez do campo nativo. Funções puras —
extraídas de engine.py (Fase 2). O engine re-exporta os símbolos para
compatibilidade (testes e chamadas existentes importam de aila.core.engine)."""
from __future__ import annotations

import json
import re
from typing import Any


def _iter_json_objects(text: str) -> list[dict]:
    """Extrai objetos JSON de nível superior de um texto (varredura de chaves)."""
    objs: list[dict] = []
    depth, start = 0, -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    val = json.loads(text[start : i + 1], strict=False)
                    if isinstance(val, dict):
                        objs.append(val)
                except json.JSONDecodeError:
                    pass
                start = -1
    return objs


def extract_text_tool_calls(text: str, registry: Any) -> list[dict]:
    """Fallback p/ modelos que emitem a tool-call como TEXTO (ex.: qwen-coder).

    Reconhece objetos JSON com ``{"tool"|"name", "args"|"arguments"}`` cujo nome
    é uma ferramenta registrada, devolvendo no formato nativo do Ollama.
    """
    calls: list[dict] = []
    for obj in _iter_json_objects(text):
        name = obj.get("tool") or obj.get("name")
        args = obj.get("args")
        if args is None:
            args = obj.get("arguments") or obj.get("parameters") or {}
        if not isinstance(name, str) or registry.get(name) is None:
            continue
        if isinstance(args, str):
            try:
                args = json.loads(args, strict=False)
            except json.JSONDecodeError:
                args = {}
        calls.append({"function": {"name": name, "arguments": args}})
    return calls


def strip_tool_call_text(text: str) -> str:
    """Remove blocos de código cercados (onde o JSON da tool-call costuma vir),
    deixando só a prosa que o modelo escreveu antes/depois."""
    return re.sub(r"```[\s\S]*?```", "", text).strip()


_FORMAT_ECHO_RX = re.compile(
    r"<function[-_ ]?name>|<args[-_ ]?json[-_ ]?object>|<nome[_ ]?exato>|<args?>|"
    r"respostas? ser[ãa]o formatad|ser[ãa]o? formatad[ao]s? como|"
    r"para (realizar|executar) a[çc][õo]es.*formatad|"
    # o modelo "narrando" o mecanismo de ferramentas em vez de responder ao usuário
    r"none of the (functions|tools)|tool palette|nenhuma das (fun[çc][õo]es|ferramentas) "
    r"(fornecidas|dispon[íi]veis)|no function call can be", re.IGNORECASE)


def _looks_like_json_toolcall(text: str) -> bool:
    """True se o texto é (essencialmente) uma tool-call em JSON crua — p/ NUNCA
    mostrar isso ao usuário como se fosse resposta. Reconhece {...} de topo com
    chaves de ferramenta (name/tool + arguments/args), com ou sem cerca ```."""
    t = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.MULTILINE).strip()
    if not t.startswith(("{", "[")):
        return False
    has_keys = ('"name"' in t or '"tool"' in t) and ('"arguments"' in t or '"args"' in t)
    if has_keys:
        return True
    for obj in _iter_json_objects(t):            # parseou como objeto de tool-call?
        if (obj.get("name") or obj.get("tool")) and (
                "arguments" in obj or "args" in obj or "parameters" in obj):
            return True
    return False


_INTENT_RX = re.compile(
    r"\b(vou|vamos|deixa eu|deixe-me|preciso|irei|let me|i['’]?ll|i will|"
    r"i['’]?m going to|i am going to|first[, ]|primeiro)\b", re.IGNORECASE)
_ACTION_RX = re.compile(
    r"\b(arquivo|ler|leio|abrir|escrever|editar|criar|rodar|executar|comando|"
    r"pesquisar|buscar|grep|testar|teste|file|read|write|edit|run|execute|"
    r"command|search|lint)\b", re.IGNORECASE)


def _looks_like_missed_toolcall(text: str, registry: Any) -> bool:
    """True quando o modelo NARROU uma ação (intenção de usar ferramenta) mas não
    emitiu a tool-call — sinal p/ dar UM empurrão em vez de encerrar o turno cedo.
    Conservador: prefere não incomodar uma resposta final legítima (só nudge 1x)."""
    t = (text or "").strip()
    if not t:
        return False
    # 1) tentou emitir o JSON da tool-call (fragmento malformado / não casou)
    if ('"tool"' in t or '"name"' in t or "```json" in t) and "{" in t:
        return True
    # 2) nomeou uma ferramenta registrada existente (nomes 'ns.acao' são distintivos)
    if any(tool.name in t for tool in registry.all()):
        return True
    # 3) verbo de intenção + contexto de ação em texto CURTO (anúncio, não resposta longa)
    return bool(len(t) <= 200 and _INTENT_RX.search(t) and _ACTION_RX.search(t))
