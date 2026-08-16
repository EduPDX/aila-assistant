"""Extração LEVE de entidades (offline, determinística) — Fase de plugagem.

Puxa de um texto os termos "entidade-like" (nomes próprios, CamelCase, nomes
pontuados tipo aila.core, termos técnicos) que servem de NÓS do Knowledge Graph.
Conservador: prefere precisão a recall. Sem LLM, sem dependência.

A consolidação (Fase 4) usa essas entidades: cria nós e liga por CO-OCORRÊNCIA
só com evidência (≥ min_evidence), então ruído que aparece uma vez não vira aresta.
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_]*(?:\.[A-Za-zÀ-ÿ0-9_]+)*")

# scaffolding da conversa + palavras comuns (pt/en) que NÃO são entidades
_STOP = {
    "usuário", "usuario", "aila", "você", "voce", "eu", "ele", "ela", "nós", "nos",
    "isso", "isto", "aquilo", "então", "entao", "porque", "como", "quando", "onde",
    "qual", "quais", "quem", "que", "para", "pra", "com", "sem", "por", "sobre",
    "uma", "uns", "umas", "dos", "das", "num", "numa", "sim", "não", "nao", "mais",
    "menos", "muito", "pouco", "também", "tambem", "já", "ainda", "the", "and", "for",
    "with", "you", "your", "this", "that", "have", "will", "can", "are", "was", "but",
    "não", "sua", "seu", "meu", "minha", "nossa", "nosso", "deu", "vai", "quer",
    "fazer", "faz", "ver", "ser", "ter", "tem", "está", "esta", "estou", "vamos",
    "bom", "boa", "certo", "certa", "agora", "aqui", "ali", "lá", "cada", "todo",
    "toda", "todos", "todas", "outro", "outra", "coisa", "coisas", "algo", "tipo",
}


def extract(text: str, max_n: int = 8) -> list[str]:
    """Entidades candidatas do texto (ordem de aparição, sem repetir, cap max_n)."""
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _TOKEN.finditer(text):
        w = m.group(0).strip("._")
        if len(w) < 3 or w.lower() in _STOP:
            continue
        camel = re.search(r"[a-z][A-Z]", w) is not None    # ModelRouter
        dotted = "." in w                                   # aila.core
        cap = w[0].isupper()                                # Nome próprio / termo
        if not (camel or dotted or cap):
            continue
        key = w.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(w)
        if len(out) >= max_n:
            break
    return out
