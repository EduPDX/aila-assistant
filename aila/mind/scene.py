"""Vocabulário da Cognitive Scene → nomes legíveis (Fase M).

A cena 3D nomeia seus objetos de forma semântica ('analysis', 'panel_memory'…).
Isso é ótimo internamente, mas na FALA vira "estou apontando para panel_memory".
Aqui traduzimos o id do objeto para um nome natural em pt-BR, para o Body State
descrever a interação em primeira pessoa de forma humana.

É a ponte do item 21: Scene Object → InteractionTarget → BodyState (com nome
real). Puro mapeamento, sem lógica de cena.
"""

from __future__ import annotations

#: id do objeto/alvo da cena → como a Aila se refere a ele falando
_NOMES: dict[str, str] = {
    "analysis": "o gráfico",
    "panel_analysis": "o gráfico",
    "data": "os dados",
    "memory": "o painel de memória",
    "panel_memory": "o painel de memória",
    "search": "os resultados da busca",
    "search_panel": "os resultados da busca",
    "monitor": "o monitor",
    "main_monitor": "o monitor",
    "a tela": "a tela",
    "": "",
}

#: tipo de interação (id) → verbo em 1ª pessoa
_ACOES: dict[str, str] = {
    "point": "apontando para",
    "pointing": "apontando para",
    "inspect": "examinando",
    "select": "selecionando",
    "touch": "mexendo em",
    "look": "olhando para",
}


def readable_target(target: str) -> str:
    """Nome natural de um objeto da cena ('' quando desconhecido/vazio)."""
    t = (target or "").strip()
    return _NOMES.get(t, _NOMES.get(t.lower(), t))


def readable_action(action: str) -> str:
    """Verbo de interação em 1ª pessoa (padrão: 'olhando para')."""
    return _ACOES.get((action or "").strip().lower(), "olhando para")
