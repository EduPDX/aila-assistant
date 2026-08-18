"""BehaviorSpec — o CONTRATO entre o Behavior Planner e o Animation Controller.

Descrição declarativa e **render-agnóstica** do que o avatar deve fazer ao
responder: qual emoção transmitir, postura, olhar, ritmo corporal e quais
gestos executar. O planner (backend) decide "o quê"; o controller (frontend)
decide "como". Trocar o motor de render não muda esta camada.

Evolui o ``AvatarState`` (que era plano) acrescentando intenção, ritmo e uma
timeline de gestos.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GestureCue(BaseModel):
    """Um gesto a executar, opcionalmente sincronizado com a fala."""

    type: str                       # ex.: "wave", "hand_explain", "thumbs_up"
    at_time: float = 0.0            # seg desde o início da fala (F5: via WordBoundary)
    at_word: str | None = None     # palavra-gatilho (referência/legenda)


class Motion(BaseModel):
    """Ritmo corporal (multiplicadores aplicados às camadas procedurais)."""

    amplitude: float = 1.0          # energia dos movimentos
    speed: float = 1.0              # velocidade dos micro-movimentos
    breath: float = 1.0             # ritmo respiratório


class CognitiveUI(BaseModel):
    """Estado da Cognitive Scene (o "ambiente" holográfico). Opcional: quando
    presente, o backend DIRIGE a interface (modo/intensidade) em vez de o
    frontend inferir pelo intent. Render-agnóstico."""

    enabled: bool = True            # a cena reage (False = fica calma/idle)
    type: str = "conversation"      # search|analysis|thinking|coding|reading|...
    intensity: float = 0.6          # ênfase visual (0..1)


class Interaction(BaseModel):
    """Alvo de interação: a Aila aponta/olha para um elemento da cena. `target`
    é SEMÂNTICO (analysis|memory|data|search…); o frontend resolve p/ a âncora 3D."""

    type: str = "point"             # point|inspect|select|touch
    target: str = ""                # ex.: "analysis", "memory"


class BehaviorSpec(BaseModel):
    """Comportamento planejado para UMA resposta da IA."""

    state: str = "SPEAKING"                     # estado alvo durante a fala
    emotion: str = "neutral"                    # emoção a transmitir
    intensity: float = Field(default=0.6, ge=0.0, le=1.0)
    intent: str = "conversation"                # natureza da resposta (ver planner)
    posture: str = "neutral"                    # open|neutral|closed|thinking|attentive
    gaze: str = "user"                          # user|screen|wander|down|soft|lock
    motion: Motion = Field(default_factory=Motion)
    gestures: list[GestureCue] = Field(default_factory=list)
    est_speech_seconds: float = 0.0             # duração estimada da fala
    text: str = ""                              # trecho (debug/legenda)
    cognitive_ui: CognitiveUI | None = None     # Fase 6: estado da Cognitive Scene (opcional)
    interaction: Interaction | None = None       # Fase 6: alvo de interação (opcional)

    def to_event_payload(self) -> dict:
        return self.model_dump(mode="json")
