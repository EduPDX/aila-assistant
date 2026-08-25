"""Limites de execução — anti-loop para laços de ferramentas autônomos.

Duas proteções complementares ao teto de iterações (``MAX_TOOL_ITERS``):

    - ORÇAMENTO: número máximo de chamadas de ferramenta num laço/tarefa
      (evita que um replanejamento em cascata rode centenas de tools).
    - REPETIÇÃO: se o modelo chama a MESMA ferramenta com os MESMOS argumentos
      repetidamente, ele está preso num loop — cortamos e devolvemos um erro
      instruindo-o a mudar de estratégia.

``CallBudget.check`` é chamado ANTES de executar cada tool; devolve ``None`` se
pode seguir, ou uma mensagem de erro (string) se estourou o limite.
"""

from __future__ import annotations

import json


# Ferramentas de LEITURA/exploração que é NORMAL chamar muitas vezes num turno
# (com args diferentes: caminhos, símbolos). Isentas do teto por-nome.
_REPEATABLE = frozenset({
    "code.read_file", "file.read", "file.grep", "file.glob", "code.map",
    "code.definition", "code.callers", "code.callees", "code.impact",
})


class CallBudget:
    def __init__(self, max_total: int = 20, max_repeat: int = 3,
                 max_per_tool: int = 6) -> None:
        self.max_total = max_total
        self.max_repeat = max_repeat
        self.max_per_tool = max_per_tool
        self.total = 0
        self.exhausted = False        # teto TOTAL batido → o engine encerra o turno
        self._counts: dict[str, int] = {}
        self._by_name: dict[str, int] = {}

    @staticmethod
    def _sig(name: str, args: dict) -> str:
        try:
            blob = json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            blob = str(args)
        return f"{name}:{blob}"

    def check(self, name: str, args: dict) -> str | None:
        """Registra a intenção de chamar ``name(args)``. Devolve mensagem de erro
        se o orçamento/repetição estourou; senão ``None``."""
        if self.total >= self.max_total:
            self.exhausted = True
            return (
                f"Limite de {self.max_total} chamadas de ferramenta atingido nesta "
                "tarefa. Pare de usar ferramentas e conclua com o que já tem."
            )
        sig = self._sig(name, args)
        seen = self._counts.get(sig, 0)
        if seen >= self.max_repeat:
            return (
                f"Você já chamou '{name}' com os mesmos argumentos {seen} vezes — "
                "isso é um loop. NÃO repita; mude a estratégia ou conclua."
            )
        # Teto por-nome: pega o loop em que o modelo VARIA os args triviamente
        # (placeholders, queries quase iguais) p/ escapar do teto por-assinatura.
        by_name = self._by_name.get(name, 0)
        if name not in _REPEATABLE and by_name >= self.max_per_tool:
            return (
                f"Você já chamou '{name}' {by_name} vezes neste turno — está preso "
                "num loop. PARE de usar essa ferramenta e responda ao usuário com o "
                "que já tem, em linguagem natural."
            )
        self._counts[sig] = seen + 1
        self._by_name[name] = by_name + 1
        self.total += 1
        return None
