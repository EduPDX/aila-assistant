"""Context Manager (Fase G) — quanto de "mim" cabe neste modelo.

Mandar identidade + personalidade + corpo + memória inteiros a cada turno sufoca
uma janela de 8k (os modelos locais) e ainda dilui a instrução: num modelo
pequeno, prompt longo REDUZ a aderência. Aqui o contexto é montado por
PRIORIDADE e cortado por orçamento.

Prioridade (o que sobrevive quando aperta):
  1. ESTADO agora (corpo + atividade) — curto e é o que evita a 3ª pessoa;
  2. IDENTIDADE + estilo — quem ela é e como fala;
  3. MEMÓRIA — útil, mas é a primeira a ser cortada.

Determinístico e sem LLM.
"""

from __future__ import annotations

#: chars por token (aprox. pt/en) — só p/ dimensionar o orçamento
_CHARS_PER_TOKEN = 3.5
#: fatia da janela reservada à auto-representação (o resto é conversa+ferramentas)
_FATIA_LOCAL = 0.12
_FATIA_NUVEM = 0.20


def budget_for(num_ctx: int, *, local: bool = True) -> int:
    """Orçamento (em chars) para os blocos do Cognitive Core."""
    janela = max(1024, int(num_ctx or 8192)) * _CHARS_PER_TOKEN
    fatia = _FATIA_LOCAL if local else _FATIA_NUVEM
    return int(janela * fatia)


def _cortar(texto: str, limite: int) -> str:
    """Corta preservando o começo (onde está o essencial)."""
    t = (texto or "").strip()
    if limite <= 0 or not t:
        return ""
    if len(t) <= limite:
        return t
    return t[: max(0, limite - 1)].rstrip() + "…"


def build_blocks(
    *,
    state_block: str = "",
    identity_block: str = "",
    memory_block: str = "",
    budget_chars: int,
) -> list[str]:
    """Blocos de sistema a injetar no turno, já dentro do orçamento.

    Retorna na ordem em que devem aparecer. Blocos vazios são omitidos — não
    poluir o contexto vale mais do que preencher espaço.
    """
    restante = max(0, int(budget_chars))
    saida: list[str] = []

    for bloco in (state_block, identity_block):          # 1º e 2º: nunca cortados
        b = (bloco or "").strip()
        if b and restante > 0:
            saida.append(b)
            restante -= len(b)

    mem = (memory_block or "").strip()                    # 3º: cabe no que sobrou
    if mem and restante > 80:                             # < 80 chars não diz nada útil
        saida.append(_cortar(mem, restante))
    return saida
