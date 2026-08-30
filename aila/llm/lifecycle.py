"""keep_alive adaptativo — quanto o modelo fica residente depois do uso.

Resource Intelligence R9. O `keep_alive` do Ollama era fixo (``"10m"``): todo
modelo usado ficava 10 min na VRAM esperando um próximo turno. Ótimo quando há
folga (resposta repetida sem recarregar), ruim quando a VRAM aperta — o modelo
frio segura espaço que o próximo (visão, coder) precisaria.

Aqui o keep_alive vira função da PRESSÃO (R2): sob folga, mantém o padrão (rápido
p/ turnos seguidos); conforme aperta, encolhe a permanência para o Ollama liberar
o modelo mais cedo depois de responder. É orquestração de ciclo de vida — não
mexe na inferência; só diz por quanto tempo o peso fica quente. Auto-corrige: ao
baixar a pressão, o keep_alive volta ao padrão no próximo turno.

Nunca descarrega o modelo ATIVO no meio do uso — só ajusta quanto ele espera
DEPOIS. E vale só p/ backends locais (a nuvem ignora o parâmetro).
"""

from __future__ import annotations

from aila.core.resources import Pressure

#: escada de permanência por pressão. NORMAL cai no default do backend (config).
#: Quanto mais apertada a VRAM, mais cedo o Ollama libera o modelo frio.
_LADDER = {
    Pressure.ELEVATED: "5m",
    Pressure.HIGH: "2m",
    Pressure.CRITICAL: "30s",
}


def keep_alive_for(pressure: Pressure, default: str = "10m") -> str:
    """keep_alive p/ esta pressão. NORMAL → o default configurado; do ELEVATED p/
    cima, encolhe a permanência para liberar VRAM mais cedo."""
    return _LADDER.get(pressure, default)
