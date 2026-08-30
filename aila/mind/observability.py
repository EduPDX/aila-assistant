"""Observabilidade do Cognitive Core (Fase N).

Log ESTRUTURADO das decisões internas do turno — para depurar por que a Aila
respondeu/agiu de tal jeito. Formato do item 32:

    [COGNITIVE] intent=chat tools=false model=local
    [SELF] identity=Aila emotion=focused activity=analyzing
    [DECISION] action=raise_right reason=user_request:body_action
    [BODY] right_hand=raised gaze=o gráfico
    [SPEECH] "Assim?"

É interno: vai só para o log (nível DEBUG), NUNCA para o frontend/usuário. Barato
e à prova de erro — nunca derruba o turno por um valor estranho.
"""

from __future__ import annotations

from typing import Any

from aila.core.logging import get_logger

log = get_logger("cognitive")


def _fmt(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return f"{v:.2f}"
    s = str(v).replace("\n", " ").strip()
    return s if len(s) <= 60 else s[:57] + "…"


def trace(section: str, **fields: Any) -> None:
    """Emite uma linha ``[SECTION] k=v k=v`` no log (campos vazios são omitidos)."""
    try:
        pares = " ".join(f"{k}={_fmt(v)}" for k, v in fields.items()
                         if v is not None and v != "")
        if pares:
            log.debug(f"[{section.upper()}] {pares}")
    except Exception:  # noqa: BLE001 - observabilidade jamais quebra o fluxo
        pass


def trace_speech(text: str) -> None:
    """Registra a fala final (curta, entre aspas)."""
    try:
        t = (text or "").replace("\n", " ").strip()
        if t:
            log.debug(f'[SPEECH] "{t[:80]}"' + ("…" if len(t) > 80 else ""))
    except Exception:  # noqa: BLE001
        pass
