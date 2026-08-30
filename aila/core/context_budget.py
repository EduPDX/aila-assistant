"""Orçamento explícito da janela de contexto, por COMPONENTE.

Resource Intelligence R7. A janela de um modelo local (8k) é um orçamento
escasso, e hoje ela era repartida por frações independentes: 12–20% p/ os blocos
de self (`context_manager.budget_for`) e 50% p/ o histórico
(`window_budget_ratio`). Faltava contabilizar UM componente caro e invisível: os
SCHEMAS das ferramentas, que vão à parte no `backend.chat` e não entram no
`_fit_context_window`. Com muitas tools numa janela pequena, isso estoura o
`num_ctx` sem ninguém ver.

Aqui o orçamento vira explícito e MEDIDO do real: janela = system+self + tools +
histórico + reserva-p/-resposta. A regra de wiring é conservadora — o custo dos
schemas é DESCONTADO do teto do histórico, mas o novo teto só pode ser <= o atual
(um `min`): R7 apenas APERTA para evitar overflow, nunca afrouxa. Sem tools, o
número é idêntico ao de antes.

kimi-k3-in-c em espírito: orçar up-front e medir do real, em vez de descobrir o
estouro no meio do turno.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

#: chars por token (aprox. pt/en/código) — só p/ dimensionar o orçamento.
_CHARS_PER_TOKEN = 3.5


@dataclass(slots=True)
class ContextBudget:
    """Repartição explícita da janela, em CHARS. Serializável p/ log/UI."""

    num_ctx: int
    window_chars: int          # num_ctx × chars/token
    tools_chars: int           # custo REAL dos schemas de ferramentas (medido)
    reserve_chars: int         # reservado p/ a resposta do modelo
    ratio_cap_chars: int       # teto legado do histórico (window_budget_ratio)
    fit_cap_chars: int         # teto que evita overflow = window − reserve − tools
    msgs_budget_chars: int     # teto efetivo = min(ratio_cap, fit_cap)
    fits: bool                 # sobra espaço p/ mensagens (reserve+tools < janela)?

    def to_dict(self) -> dict:
        return {
            "num_ctx": self.num_ctx,
            "window_chars": self.window_chars,
            "tools_chars": self.tools_chars,
            "reserve_chars": self.reserve_chars,
            "msgs_budget_chars": self.msgs_budget_chars,
            "tightened": self.fit_cap_chars < self.ratio_cap_chars,
            "fits": self.fits,
        }


def measure_tools_chars(tools) -> int:
    """Tamanho REAL dos schemas de ferramentas (o JSON que vai ao modelo). 0 se
    não houver tools. Nunca levanta — schema não-serializável cai p/ str()."""
    if not tools:
        return 0
    try:
        return len(json.dumps(tools, ensure_ascii=False))
    except (TypeError, ValueError):
        return len(str(tools))


def plan_budget(
    *,
    num_ctx: int,
    tools_chars: int = 0,
    ratio: float = 0.5,
    answer_reserve_tokens: int = 2048,
    chars_per_token: float = _CHARS_PER_TOKEN,
) -> ContextBudget:
    """Reparte a janela por componente e devolve o teto EFETIVO do histórico.

    `msgs_budget_chars` = min(teto legado por fração, janela − reserva − tools).
    O `min` garante que R7 só aperte: sem tools (ou tools pequenas) o número é o
    de antes; tools grandes encolhem o histórico p/ o total não passar da janela."""
    window = int(max(1024, num_ctx or 8192) * chars_per_token)
    # a reserva p/ resposta nunca come mais que metade da janela (janelas minúsculas).
    reserve = min(int(answer_reserve_tokens * chars_per_token), window // 2)
    ratio_cap = int(window * ratio)
    fit_cap = max(0, window - reserve - tools_chars)
    return ContextBudget(
        num_ctx=num_ctx,
        window_chars=window,
        tools_chars=tools_chars,
        reserve_chars=reserve,
        ratio_cap_chars=ratio_cap,
        fit_cap_chars=fit_cap,
        msgs_budget_chars=min(ratio_cap, fit_cap),
        fits=(reserve + tools_chars) < window,
    )
