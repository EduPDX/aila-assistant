"""Emotion Engine — deriva emoção, gesto e animação a partir do estado da
conversa e do texto da IA.

Estratégia em camadas (barata primeiro):
    1. Sinais de estado (a IA está pensando? falando? chamando ferramenta?).
    2. Heurística léxica sobre o texto da resposta (palavras-chave).
    3. (Fase futura) classificação por LLM leve para nuance emocional.

Exemplos do enunciado:
    erro encontrado   -> confused + thinking
    boa solução       -> happy + confident
"""

from __future__ import annotations

import re

from aila.avatar.protocol import (
    Animation,
    AvatarState,
    Emotion,
    Gesture,
    SpeechState,
)

# Palavra-chave -> (emoção, gesto). Ordem = prioridade.
_LEXICON: list[tuple[re.Pattern, Emotion, Gesture]] = [
    (re.compile(r"\b(erro|falha|exception|traceback|bug|não funcion)", re.I),
     Emotion.CONFUSED, Gesture.SHRUG),
    (re.compile(r"\b(pronto|resolvido|sucesso|funcionou|consegui|perfeito)", re.I),
     Emotion.HAPPY, Gesture.THUMBS_UP),
    (re.compile(r"\b(recomendo|melhor abordagem|solução|vamos|proponho)", re.I),
     Emotion.CONFIDENT, Gesture.HAND_EXPLAIN),
    (re.compile(r"\b(deixa eu pensar|analisando|hmm|talvez|depende)", re.I),
     Emotion.THINKING, Gesture.NONE),
    (re.compile(r"\?\s*$"),
     Emotion.FOCUSED, Gesture.NONE),
]


class EmotionEngine:
    def thinking(self) -> AvatarState:
        """Estado enquanto a IA processa (antes de responder)."""
        return AvatarState(
            emotion=Emotion.FOCUSED,
            animation=Animation.THINKING,
            speech_state=SpeechState.SILENT,
            intensity=0.6,
        )

    def listening(self) -> AvatarState:
        return AvatarState(
            emotion=Emotion.NEUTRAL,
            animation=Animation.IDLE,
            speech_state=SpeechState.LISTENING,
        )

    def from_text(self, text: str, speaking: bool = True) -> AvatarState:
        """Deriva o estado a partir do texto final da resposta."""
        emotion, gesture = Emotion.NEUTRAL, Gesture.NONE
        for pattern, emo, ges in _LEXICON:
            if pattern.search(text):
                emotion, gesture = emo, ges
                break

        animation = Animation.TALKING if speaking else Animation.IDLE
        speech = SpeechState.TALKING if speaking else SpeechState.SILENT
        intensity = 0.8 if emotion in (Emotion.HAPPY, Emotion.CONFIDENT) else 0.5

        return AvatarState(
            emotion=emotion,
            gesture=gesture,
            animation=animation,
            speech_state=speech,
            intensity=intensity,
            text=text[:200],
        )

    def idle(self) -> AvatarState:
        return AvatarState()
