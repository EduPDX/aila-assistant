"""Ajuste de janela de contexto: compacta resultados de ferramenta ANTIGOS para
caber no orçamento de tokens (num_ctx pequeno não trunca system/plano no meio
de um turno agêntico) e prepara resultados para reinjeção (corte + embrulho
anti prompt-injection de fontes de terceiros). Funções puras — extraídas de
engine.py (Fase 2). Re-exportado pelo engine para compatibilidade."""
from __future__ import annotations

from aila.security.injection import is_untrusted_source, wrap_external

MAX_TOOL_RESULT_CHARS = 3000


def _clip_for_context(content: str, limit: int = MAX_TOOL_RESULT_CHARS) -> str:
    """Corta um resultado grande mantendo início e fim (onde costuma estar o
    mais relevante: topo de páginas, erros no fim de comandos)."""
    content = content or ""
    if len(content) <= limit:
        return content
    head = content[: limit * 2 // 3]
    tail = content[-(limit // 3):]
    omitted = len(content) - len(head) - len(tail)
    return f"{head}\n…[{omitted} caracteres omitidos]…\n{tail}"


def _safe_tool_context(name: str, content: str) -> str:
    """Prepara o resultado de uma tool para REINJEÇÃO no contexto do modelo:
    corta o tamanho e, se a fonte for de TERCEIROS (web/arquivo/comando),
    embrulha como DADO externo (anti prompt-injection)."""
    clipped = _clip_for_context(content)
    if is_untrusted_source(name):
        return wrap_external(clipped, source=name)
    return clipped


#: chars por token (aprox. p/ pt/en/código) — só p/ estimar o orçamento da janela.
_CHARS_PER_TOKEN = 3.5


def _fit_context_window(
    msgs: list[dict], *, budget_chars: int, keep_recent_tools: int, stub_min: int = 80,
) -> list[dict]:
    """Mantém a janela de mensagens dentro de um orçamento de caracteres, COMPACTANDO
    os resultados de ferramenta ANTIGOS (role='tool', já usados pelo modelo) e
    preservando system/user/assistant e os ``keep_recent_tools`` resultados mais
    recentes. Evita que um modelo de num_ctx pequeno trunque silenciosamente o
    system prompt/plano no meio de um turno agêntico longo.

    Não muta a lista/dicts de entrada (devolve cópia quando compacta). Se ainda
    estourar após compactar tudo que podia, devolve o melhor esforço."""
    total = sum(len(m.get("content") or "") for m in msgs)
    if budget_chars <= 0 or total <= budget_chars:
        return msgs
    tool_idx = [i for i, m in enumerate(msgs) if m.get("role") == "tool"]
    protect = set(tool_idx[-keep_recent_tools:]) if keep_recent_tools > 0 else set()
    out = [dict(m) for m in msgs]                     # cópia rasa (não muta entrada)
    for i in tool_idx:                                # do mais ANTIGO p/ o recente
        if total <= budget_chars:
            break
        if i in protect:
            continue
        content = out[i].get("content") or ""
        if len(content) <= stub_min:
            continue
        name = out[i].get("name") or "tool"
        stub = f"[resultado de {name} compactado p/ caber no contexto: {len(content)} chars omitidos]"
        total -= len(content) - len(stub)
        out[i]["content"] = stub
    return out
