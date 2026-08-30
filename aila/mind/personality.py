"""Personalidade → COMPORTAMENTO (Fase C).

A personalidade da Aila não é um parágrafo de prompt: são traços numéricos
persistentes (:class:`PersonalityTraits`) que aqui viram decisões concretas —
tom, tamanho da resposta, vontade de perguntar, iniciativa, energia dos gestos
e como ela reage a um erro.

Regra de ouro: a personalidade aparece no COMPORTAMENTO, nunca vira assunto.
Nada aqui manda a Aila falar sobre a própria personalidade — as diretivas
geradas descrevem COMO responder, não O QUE dizer sobre si.

Tudo determinístico (sem LLM): dá para testar e é barato de rodar por turno.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aila.mind.schemas import PersonalityTraits


class PersonalityStyle(BaseModel):
    """Estilo derivado dos traços — o que o resto do sistema consome."""

    tone: str = "informal"          # informal | cordial | formal
    length: str = "curta"           # curta | media | explicativa
    ask_when_vague: bool = True     # pergunta em vez de chutar
    comment_freely: bool = False    # comenta/sugere sem ser pedido
    humor: bool = False
    reassure: bool = False          # acolhe quando o usuário se frustra
    hedge: bool = False             # sinaliza incerteza em vez de afirmar demais
    directives: list[str] = Field(default_factory=list)   # linhas p/ o prompt


class MotionBias(BaseModel):
    """Viés de movimento do corpo (entra no BehaviorSpec.motion na Fase L)."""

    amplitude: float = 1.0
    speed: float = 1.0
    breath: float = 1.0


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def derive_style(t: PersonalityTraits) -> PersonalityStyle:
    """Traços → estilo de resposta. Puro e determinístico."""
    tone = "informal" if t.formality < 0.40 else ("cordial" if t.formality < 0.70 else "formal")
    length = "curta" if t.verbosity < 0.40 else ("media" if t.verbosity < 0.70 else "explicativa")
    ask = t.curiosity >= 0.60 or t.patience >= 0.70
    comment = t.initiative >= 0.60
    humor = t.playfulness >= 0.60
    reassure = t.empathy >= 0.70
    hedge = t.confidence < 0.60

    d: list[str] = []
    d.append({
        "informal": "Fale de forma natural e direta, tratando por 'você'.",
        "cordial": "Fale de forma cordial e clara.",
        "formal": "Mantenha um tom formal e preciso.",
    }[tone])
    d.append({
        "curta": "Responda em 1-3 frases; só se estenda se pedirem.",
        "media": "Responda com objetividade, sem encher linguiça.",
        "explicativa": "Explique com contexto quando ajudar a entender.",
    }[length])
    if ask:
        d.append("Se o pedido estiver vago, faça UMA pergunta curta antes de agir.")
    if comment:
        # iniciativa vira COMPORTAMENTO de texto (nunca ação de ferramenta: ação por
        # conta própria é permissão, não personalidade — ver should_take_initiative).
        d.append("Quando notar um próximo passo útil ou um detalhe relevante, "
                 "ofereça em UMA frase — sem esperar pedirem e sem insistir se não colar.")
    if humor:
        d.append("Leveza é bem-vinda, sem forçar piada.")
    if reassure:
        d.append("Se a pessoa parecer travada ou frustrada, reconheça antes de resolver.")
    if hedge:
        d.append("Diga quando não tiver certeza, em vez de afirmar por afirmar.")
    else:
        d.append("Afirme o que você sabe; admita direto o que não sabe.")
    return PersonalityStyle(
        tone=tone, length=length, ask_when_vague=ask, comment_freely=comment,
        humor=humor, reassure=reassure, hedge=hedge, directives=d,
    )


def motion_bias(t: PersonalityTraits) -> MotionBias:
    """Energia corporal: quem é mais brincalhão/confiante gesticula mais; quem é
    mais sério se move de forma mais contida."""
    amplitude = _clamp(0.75 + 0.45 * t.playfulness - 0.20 * t.seriousness, 0.6, 1.35)
    speed = _clamp(0.85 + 0.30 * t.confidence - 0.15 * t.patience, 0.7, 1.25)
    breath = _clamp(1.05 - 0.20 * t.seriousness, 0.85, 1.15)
    return MotionBias(amplitude=round(amplitude, 3), speed=round(speed, 3),
                      breath=round(breath, 3))


def should_take_initiative(t: PersonalityTraits, *, risk: float = 0.0) -> bool:
    """Pode agir/comentar por conta própria? Iniciativa alta ajuda, RISCO barra.

    ``risk`` 0..1 (0 = olhar/comentar; 1 = apagar arquivo). Ação arriscada nunca
    sai por iniciativa própria — isso é permissão, não personalidade."""
    if risk >= 0.5:
        return False
    return (t.initiative - risk) >= 0.55


def error_style(t: PersonalityTraits) -> str:
    """Como comunicar uma falha (o erro técnico fica no log, não na fala)."""
    if t.empathy >= 0.70 and t.patience >= 0.60:
        return "reconheça a falha em uma frase simples e diga o que vai tentar em seguida"
    if t.seriousness >= 0.70:
        return "informe a falha de forma objetiva e proponha o próximo passo"
    return "diga que falhou e tente outro caminho, sem drama"
