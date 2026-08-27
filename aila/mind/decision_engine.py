"""Decision Engine (Fase I) — decidir a AÇÃO a partir do PEDIDO.

Hoje o comportamento do corpo é inferido do TEXTO da resposta (o Behavior
Planner lê o que o modelo escreveu e adivinha um gesto). Isso inverte a ordem
natural: o gesto vira consequência das palavras, então "agir sem falar" ou
"agir antes de responder" é impossível — e se o modelo esquecer de chamar a
ferramenta, o corpo simplesmente não se mexe.

Aqui a decisão vem do PEDIDO do usuário, por regra determinística:

    "levanta a mão direita"  →  Action(raise_right)  +  fala curta ("Assim?")

O texto continua sendo do LLM; o que deixa de depender dele é a AÇÃO.
Só decide o que é inequívoco — na dúvida, devolve nada e o fluxo segue como era.
"""

from __future__ import annotations

import re

from aila.mind.schemas import Action, Decision, Speech

#: gestos que o avatar realmente sabe fazer (espelha aila/agents/avatar_agent.py)
GESTOS_VALIDOS = frozenset({
    "wave", "raise_right", "raise_left", "raise_both", "thumbs_up", "point",
    "hand_explain", "shrug", "think", "cheer", "rest",
})

_LADO_DIR = r"(?:direit[ao]|direita)"
_LADO_ESQ = r"(?:esquerd[ao])"
_MEMBRO = r"(?:m[ãa]os?|bra[çc]os?)"

#: (regex do pedido, gesto). Ordem importa: o mais específico primeiro.
_REGRAS: tuple[tuple[str, str], ...] = (
    (rf"\b(?:levant\w+|erg\w+|sob\w+)\s+(?:a|o|as|os)?\s*{_MEMBRO}\s+{_LADO_DIR}", "raise_right"),
    (rf"\b(?:levant\w+|erg\w+|sob\w+)\s+(?:a|o|as|os)?\s*{_MEMBRO}\s+{_LADO_ESQ}", "raise_left"),
    # plural sem lado = os dois braços
    (r"\b(?:levant\w+|erg\w+|sob\w+)\s+(?:as|os)\s*(?:m[ãa]os|bra[çc]os)", "raise_both"),
    # singular sem lado = a mão dominante (direita)
    (r"\b(?:levant\w+|erg\w+|sob\w+)\s+(?:a|o)?\s*(?:m[ãa]o|bra[çc]o)", "raise_right"),
    (r"\b(?:acen\w+|d[êe]\s+tchau|tchau)\b", "wave"),
    (r"\b(?:apont\w+)\b", "point"),
    (r"\b(?:joinha|jo[ií]a|thumbs?\s*up|positivo)\b", "thumbs_up"),
    (r"\b(?:comemor\w+|vibr\w+|festej\w+)\b", "cheer"),
    (r"\b(?:d[êe]\s+de\s+ombros|encolh\w+\s+os\s+ombros)\b", "shrug"),
    (r"\b(?:pens\w+\s+(?:um\s+pouco|nisso|sobre)|fa[çc]a\s+cara\s+de\s+pensa\w+)\b", "think"),
    (r"\b(?:abaix\w+|relax\w+|descans\w+)\s+(?:os?|as?)?\s*" + _MEMBRO, "rest"),
)
_COMPILADAS = tuple((re.compile(p, re.IGNORECASE), g) for p, g in _REGRAS)


def decide_gesture(user_text: str) -> str | None:
    """Gesto pedido explicitamente pelo usuário (None se não for um pedido claro)."""
    t = (user_text or "").strip()
    if not t:
        return None
    for rx, gesto in _COMPILADAS:
        if rx.search(t):
            return gesto if gesto in GESTOS_VALIDOS else None
    return None


def decide(user_text: str, *, self_model: object | None = None) -> Decision | None:
    """Decisão para o turno, ou None quando não há ação corporal evidente.

    Devolver None é o caso comum e é de propósito: só assumimos o controle do
    corpo quando o pedido é inequívoco. Ambiguidade fica com o LLM.
    """
    gesto = decide_gesture(user_text)
    if gesto is None:
        return None

    estilo = "neutral"
    if self_model is not None:
        try:
            st = self_model.style()
            estilo = "playful" if st.humor else ("short" if st.length == "curta" else "neutral")
        except Exception:  # noqa: BLE001 - estilo é decorativo aqui
            estilo = "neutral"

    return Decision(
        speech=Speech(text="", style=estilo),   # o texto continua sendo do LLM
        actions=[Action(type=gesto, target="body")],
        reason="user_request:body_action",
    )
