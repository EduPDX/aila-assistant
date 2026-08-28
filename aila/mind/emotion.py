"""Emoção → TOM da fala (Fase F).

NÃO é um sistema de emoções: o EmotionEngine (aila/avatar/emotion_engine.py)
continua sendo o único dono de derivar a emoção. Aqui só traduzimos a emoção
atual em uma diretiva CURTA de tom, para que ela influencie o TEXTO da resposta
(item 12) — hoje a emoção já mexe em postura/gesto/movimento, mas não na escolha
de palavras. Determinístico e barato.
"""

from __future__ import annotations

#: emoção (valores do enum Emotion) → como isso soa na FALA (1ª pessoa, pt-BR)
_TOM: dict[str, str] = {
    "neutral": "",
    "happy": "Tom leve e positivo.",
    "confident": "Tom seguro e direto.",
    "focused": "Tom objetivo, foco no essencial.",
    "confused": "Reconheça a dúvida com naturalidade; sem fingir certeza.",
    "surprised": "Pode demonstrar um pequeno entusiasmo.",
    "sad": "Tom mais contido e gentil.",
    "thinking": "Pode pensar em voz alta, breve.",
}


def tone_hint(emotion: str) -> str:
    """Diretiva de tom para a emoção atual ('' quando neutra: nada a acrescentar)."""
    return _TOM.get((emotion or "neutral").strip().lower(), "")
