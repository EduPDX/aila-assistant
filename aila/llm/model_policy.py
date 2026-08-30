"""Política de escolha do modelo LOCAL — consciente de recurso.

Resource Intelligence R5. O router decide o PROVEDOR (local/nuvem); esta função
decide, DENTRO do local, entre o modelo grande (padrão) e o pequeno/rápido
(`fast_model`). Antes essa escolha só olhava se o turno era "leve"; agora também
olha a PRESSÃO de recurso (R2) e o tamanho do contexto — para degradar com
elegância quando a VRAM aperta, em vez de arriscar um OOM ou perder o contexto
WebGL do avatar.

Fronteira de segurança (privacidade > recurso): esta função SÓ escolhe entre
modelos LOCAIS. Ela nunca troca de provedor, nunca sobe de tamanho por causa de
recurso e JAMAIS empurra a tarefa para a nuvem. O pior que faz é preferir o
modelo pequeno — que já está instalado e roda no mesmo PC.

Retorna o NOME do modelo rápido (usar o pequeno) ou ``None`` (usar o grande/padrão).
"""

from __future__ import annotations

from aila.core.resources import Pressure

# Complexidade a partir da qual o turno é "pesado" (mesmo limiar do turn.py p/
# kind='reasoning'): tarefa densa não degrada por pressão — o usuário quer a
# resposta boa, e evitar OOM aí é papel do pré-voo/lifecycle (R6/R9), não aqui.
_HEAVY_COMPLEXITY = 0.6


def select_local_model(
    *,
    fast_model: str,
    is_light: bool,
    complexity: float = 0.0,
    pressure: Pressure = Pressure.NORMAL,
    est_context: int = 0,
    ctx_limit: int = 0,
) -> str | None:
    """Escolhe o sub-modelo local. `fast_model` vazio → sempre o grande (None).

    Ordem de decisão:
      1. Sem modelo rápido configurado → grande.
      2. Contexto já no limite da janela → grande (turno longo/denso; não degrada).
      3. Turno leve/trivial → rápido (comportamento de sempre).
      4. Pressão de GPU alta + turno não-pesado → rápido (degradação graciosa).
      5. Caso contrário → grande.
    """
    if not fast_model:
        return None
    # Contexto perto de estourar a janela = turno pesado por si só: mantém o modelo
    # capaz mesmo sob pressão (degradar a qualidade num prompt cheio é o pior caso).
    if ctx_limit and est_context >= ctx_limit:
        return None
    if is_light:
        return fast_model
    if pressure >= Pressure.HIGH and complexity < _HEAVY_COMPLEXITY:
        return fast_model
    return None
