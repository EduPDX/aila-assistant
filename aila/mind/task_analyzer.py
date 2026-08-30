"""Analisador de tarefa (Fase H) — estima a COMPLEXIDADE do pedido, sem LLM.

O router escolhia o modelo pelo "tipo" (chat/code); faltava a DIFICULDADE. Aqui,
por regras determinísticas (instantâneas, testáveis, sem gastar VRAM), estimamos
quão pesada é a tarefa — para o pedido trivial cair no modelo pequeno/rápido e o
raciocínio pesado ir para o modelo maior, quando fizer sentido.

Princípio (itens 14/15): o router escolhe QUAL FERRAMENTA COGNITIVA usar — a Aila
continua a mesma. Complexidade não muda a identidade, só o "cérebro" emprestado.
"""

from __future__ import annotations

import re

#: pistas de RACIOCÍNIO (comparar, justificar, analisar a fundo) → tarefa pesada
_REASONING_RX = re.compile(
    r"\b(compar\w+|analis\w+|avali\w+|justif\w+|explique\s+(em\s+)?detalh\w+|"
    r"por\s*que|porqu[êe]|pr[óo]s\s+e\s+contras|vantagens?\s+e\s+desvantagens?|"
    r"passo\s+a\s+passo|demonstr\w+|prov\w+|calcul\w+|racioc\w+|estrat[ée]gi\w+|"
    r"trade[- ]?off|implica\w+|consequ[êe]nci\w+|otimiz\w+|arquitet\w+)\b",
    re.IGNORECASE)

#: pistas de tarefa TRIVIAL (fato curto, saudação, sim/não)
_TRIVIAL_RX = re.compile(
    r"^\s*(oi+|ol[áa]|bom dia|boa (tarde|noite)|obrigad[oa]|valeu|tchau|"
    r"que horas|qual\s+(a|o|é)\s+\w+\??|quem\s+é\s+\w+\??|quanto\s+é\s+[\d\s+\-*/]+)\s*[?.!]*\s*$",
    re.IGNORECASE)


def estimate_complexity(text: str) -> float:
    """Complexidade 0..1 (0 = trivial, 1 = pesada). Determinístico."""
    t = (text or "").strip()
    if not t:
        return 0.0
    if _TRIVIAL_RX.match(t):
        return 0.05

    palavras = len(t.split())
    score = min(palavras / 60.0, 0.45)                 # tamanho (até 0.45)
    if _REASONING_RX.search(t):
        score += 0.40                                  # exige raciocínio
    if "```" in t or re.search(r"\bc[óo]digo\b", t, re.IGNORECASE):
        score += 0.15                                  # envolve código
    perguntas = t.count("?")
    if perguntas >= 2:
        score += 0.15                                  # múltiplas perguntas
    if re.search(r"\b(e\s+tamb[ée]m|al[ée]m\s+disso|depois|em\s+seguida|primeiro.*depois)\b",
                 t, re.IGNORECASE):
        score += 0.10                                  # multi-etapa
    return round(min(score, 1.0), 3)


def analyze(text: str) -> dict:
    """Resumo da tarefa para o router: complexidade + se pede raciocínio pesado."""
    c = estimate_complexity(text)
    return {
        "complexity": c,
        "trivial": c <= 0.12,
        "reasoning": c >= 0.7 or bool(_REASONING_RX.search(text or "")),
    }
