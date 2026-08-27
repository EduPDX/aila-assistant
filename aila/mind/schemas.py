"""Esquemas do Cognitive Core (Fase B) — a representação que a Aila tem de SI.

São só DADOS (Pydantic), sem comportamento de IA: identidade e personalidade
persistentes, estado do corpo, experiência atual e capacidades. O contrato com
o frontend é o :class:`AilaState`.

Nota conceitual: isto é um *self model* (modelo computacional de identidade e
estado) — não uma alegação de consciência. Serve para a Aila falar e agir em
PRIMEIRA PESSOA de forma coerente, independentemente de qual LLM respondeu.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------- identidade #


class Identity(BaseModel):
    """Quem a Aila é. Estável: muda por configuração, não por conversa."""

    name: str = "Aila"
    self_reference: str = "eu"
    role: str = "assistente pessoal"
    form: str = "avatar virtual"
    pronouns: str = "ela/dela"
    # 1–2 frases; entra no contexto do modelo (curto de propósito: cabe em 8k)
    summary: str = (
        "Sou a Aila, assistente pessoal do Eduardo. Rodo no computador dele e "
        "tenho um corpo virtual (um avatar) que uso para olhar, apontar e gesticular."
    )

    def prompt_block(self) -> str:
        """Bloco mínimo de identidade para o prompt (1ª pessoa)."""
        return (
            f"Você é {self.name}. Fale sempre em primeira pessoa "
            f"('{self.self_reference}', 'meu', 'minha', 'estou').\n{self.summary}"
        )


# ------------------------------------------------------------- personalidade #


class PersonalityTraits(BaseModel):
    """Traços persistentes (0..1). Influenciam ESTILO e iniciativa — nunca viram
    assunto: a Aila não fala sobre a própria personalidade, ela a demonstra."""

    curiosity: float = Field(0.85, ge=0.0, le=1.0)
    playfulness: float = Field(0.55, ge=0.0, le=1.0)
    confidence: float = Field(0.70, ge=0.0, le=1.0)
    patience: float = Field(0.75, ge=0.0, le=1.0)
    seriousness: float = Field(0.60, ge=0.0, le=1.0)
    empathy: float = Field(0.82, ge=0.0, le=1.0)
    formality: float = Field(0.35, ge=0.0, le=1.0)
    initiative: float = Field(0.50, ge=0.0, le=1.0)   # quanto age/comenta sem pedir
    verbosity: float = Field(0.40, ge=0.0, le=1.0)    # quão longa é a resposta

    def summary(self) -> str:
        """Descrição CURTA do estilo (o que vai ao modelo — não os números)."""
        bits: list[str] = []
        bits.append("informal e direta" if self.formality < 0.45 else "cordial e um pouco formal")
        bits.append("respostas curtas" if self.verbosity < 0.5 else "respostas explicativas")
        if self.curiosity >= 0.7:
            bits.append("curiosa (pergunta quando algo está vago)")
        if self.playfulness >= 0.6:
            bits.append("bem-humorada")
        if self.empathy >= 0.7:
            bits.append("atenciosa")
        if self.seriousness >= 0.7:
            bits.append("objetiva no trabalho")
        return "; ".join(bits)


# ---------------------------------------------------------------- corpo/estado #


class BodyState(BaseModel):
    """O corpo AGORA. Preenchido pelo frontend (Fase D) — aqui só o formato."""

    posture: str = "standing"
    gaze_target: str = ""                 # "" = usuário; ex.: "panel_analysis"
    hands: dict[str, str] = Field(default_factory=lambda: {"left": "rest", "right": "rest"})
    gesture: str = "rest"
    interaction_target: str = ""
    interaction_action: str = ""
    updated_at: float = 0.0               # epoch (frescor do dado)

    def describe(self) -> str:
        """Frase em 1ª PESSOA do estado do corpo — é isto que o modelo lê, e é o
        que evita 'o avatar está com a mão levantada'."""
        partes: list[str] = []
        erguida = [lado for lado, e in self.hands.items() if e in ("raised", "up", "point", "pointing")]
        if erguida:
            nome = {"left": "esquerda", "right": "direita"}
            quais = " e ".join(nome.get(x, x) for x in erguida)
            partes.append(f"estou com a mão {quais} levantada" if len(erguida) == 1
                          else f"estou com as mãos ({quais}) levantadas")
        if self.gaze_target:
            partes.append(f"estou olhando para {self.gaze_target}")
        if self.interaction_target:
            acao = self.interaction_action or "interagindo com"
            partes.append(f"estou {acao} {self.interaction_target}")
        if self.gesture and self.gesture != "rest" and not erguida:
            partes.append(f"estou fazendo o gesto '{self.gesture}'")
        return "; ".join(partes)


class Experience(BaseModel):
    """O que está acontecendo comigo agora (temporário, muda a cada turno)."""

    activity: str = "idle"       # idle|talking|thinking|searching|coding|analyzing|...
    attention: str = ""          # foco atual (objeto/assunto)
    emotion: str = "neutral"     # espelha o EmotionEngine (não duplica a lógica)
    confidence: float = Field(0.7, ge=0.0, le=1.0)


class Capabilities(BaseModel):
    """O que eu consigo fazer — derivado das ferramentas REAIS registradas, para
    a Aila não prometer o que não tem nem negar o que tem."""

    items: dict[str, bool] = Field(default_factory=dict)

    def can(self, name: str) -> bool:
        return bool(self.items.get(name, False))

    def summary(self) -> str:
        sim = [k for k, v in self.items.items() if v]
        return ", ".join(sorted(sim)) or "(nenhuma)"


# ------------------------------------------------- fala/ação (fases I–J) #


class Action(BaseModel):
    """Ação corporal decidida (separada da fala)."""

    type: str                                  # ex.: "raise_hands", "point", "look"
    target: str = ""
    params: dict[str, Any] = Field(default_factory=dict)


class Speech(BaseModel):
    text: str = ""
    style: str = "neutral"


class Decision(BaseModel):
    """Saída do DecisionEngine: falar, agir, ou ambos (ou nenhum)."""

    speech: Speech = Field(default_factory=Speech)
    actions: list[Action] = Field(default_factory=list)
    reason: str = ""


# ------------------------------------------------- contrato com o frontend #


class AilaState(BaseModel):
    """O que o frontend recebe. NÃO expõe qual LLM respondeu (detalhe interno)."""

    identity: Identity = Field(default_factory=Identity)
    personality: str = ""            # resumo legível, não os números
    emotion: str = "neutral"
    experience: Experience = Field(default_factory=Experience)
    body: BodyState = Field(default_factory=BodyState)
    capabilities: list[str] = Field(default_factory=list)

    def to_event_payload(self) -> dict[str, Any]:
        return self.model_dump()
