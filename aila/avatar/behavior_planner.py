"""Behavior Planner — decide o COMPORTAMENTO do avatar pelo SIGNIFICADO da
resposta (não pelo áudio), ANTES do TTS começar.

Fica entre o LLM e o Animation Controller:

    LLM → Behavior Planner → (BehaviorSpec) → Animation Controller → TTS → VRM

Totalmente desacoplado do render: só produz um ``BehaviorSpec`` (JSON). A
detecção de intenção usa sinais baratos e sem latência:
    1. Ferramentas usadas no turno (sinal forte: web.search→search, code.*→coding…).
    2. Heurística léxica sobre o texto (saudação, erro, explicação…).
Reaproveita o ``EmotionEngine`` para a emoção/gesto de base.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from aila.avatar.behavior_spec import BehaviorSpec, GestureCue, Motion
from aila.avatar.emotion_engine import EmotionEngine

# prefixo da ferramenta -> intenção (ordem = prioridade)
_TOOL_INTENT: list[tuple[str, str]] = [
    ("web.", "search"),
    ("code.", "coding"),
    ("vision.", "analysis"),
    ("binary.", "analysis"),
    ("computer.", "tool_execution"),
    ("file.", "reading"),
    ("memory.", "thinking"),
]

# intenção -> (postura, olhar, amplitude, velocidade, respiração)
_STYLE: dict[str, tuple[str, str, float, float, float]] = {
    "greeting":       ("open",     "user",   1.20, 1.15, 1.10),
    "farewell":       ("open",     "user",   1.10, 1.05, 1.00),
    "explanation":    ("open",     "user",   1.15, 1.05, 1.05),
    "conversation":   ("neutral",  "user",   1.00, 1.00, 1.00),
    "coding":         ("neutral",  "screen", 0.80, 0.95, 0.95),
    "analysis":       ("thinking", "screen", 0.85, 0.95, 0.95),
    "search":         ("thinking", "wander", 0.90, 0.95, 0.95),
    "reading":        ("neutral",  "screen", 0.85, 0.95, 0.95),
    "tool_execution": ("neutral",  "wander", 0.90, 1.00, 1.00),
    "thinking":       ("thinking", "wander", 0.85, 0.90, 0.90),
    "error":          ("closed",   "down",   0.70, 0.90, 0.90),
}

# gesto por trecho — F5: vários gestos numa TIMELINE, cada um no tempo em que
# a palavra-gatilho é falada (estimado pela posição no texto).
_GESTURE_CUES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^\s*(ol[áa]|oi+|e a[íi]|bom dia|boa tarde|boa noite)\b", re.I), "wave"),
    (re.compile(r"\b(tchau|at[ée] (mais|logo|breve)|falou|abra[çc]o)\b", re.I), "wave"),
    (re.compile(r"\b(recomendo|proponho|sugiro|a melhor|veja|observe|repara|note)\b", re.I), "hand_explain"),
    (re.compile(r"\b(perfeito|excelente|consegui|funcionou|resolvido|show)\b", re.I), "thumbs_up"),
    (re.compile(r"\b(aqui|isto|isso aqui|este|esse ponto|olha (isso|aqui))\b", re.I), "point"),
    (re.compile(r"\b(sim|claro|com certeza|certo|exatamente|isso mesmo)\b", re.I), "nod"),
    (re.compile(r"\b(n[ãa]o|jamais|nunca|de jeito nenhum|de forma alguma)\b", re.I), "shake"),
    (re.compile(r"\b(deixa eu pensar|hmm+|talvez|n[ãa]o sei ao certo)\b", re.I), "think"),
]

_GREETING = re.compile(r"^\s*(ol[áa]|oi+|e a[íi]|bom dia|boa tarde|boa noite)\b", re.I)
_FAREWELL = re.compile(r"\b(tchau|at[ée] (mais|logo|breve)|falou)\b", re.I)
_ERROR = re.compile(r"\b(erro|falha|desculp|n[ãa]o consegui|infelizmente|deu problema)\b", re.I)
_THINKING = re.compile(r"\b(deixa eu pensar|hmm+|analisando|talvez|depende)\b", re.I)
_EXPLAIN = re.compile(r"\b(porque|portanto|primeiro|segundo|al[ée]m disso|ou seja|por exemplo|basicamente)\b", re.I)


class BehaviorPlanner:
    def __init__(self, emotions: EmotionEngine | None = None) -> None:
        self.emotions = emotions or EmotionEngine()

    def plan(self, text: str, *, tools_used: Iterable[str] = (), speaking: bool = True) -> BehaviorSpec:
        text = (text or "").strip()
        emo = self.emotions.from_text(text, speaking=speaking)
        emotion = str(emo.emotion)
        intent = self._intent(text, list(tools_used))
        posture, gaze, amp, speed, breath = _STYLE.get(intent, _STYLE["conversation"])
        intensity = 0.85 if emotion in ("happy", "confident", "surprised") else 0.6
        est = round(max(1.0, len(text) / 15.0), 1)   # ~15 chars/s pt-BR
        return BehaviorSpec(
            state="SPEAKING" if speaking else "IDLE",
            emotion=emotion,
            intensity=intensity,
            intent=intent,
            posture=posture,
            gaze=gaze,
            motion=Motion(amplitude=amp, speed=speed, breath=breath),
            gestures=self._gestures(text, str(emo.gesture), est),
            est_speech_seconds=est,
            text=text[:200],
        )

    # ------------------------------------------------------------------ #
    def _intent(self, text: str, tools_used: list[str]) -> str:
        for prefix, intent in _TOOL_INTENT:
            if any(t.startswith(prefix) for t in tools_used):
                return intent
        if _GREETING.search(text):
            return "greeting"
        if _FAREWELL.search(text):
            return "farewell"
        if _ERROR.search(text):
            return "error"
        if _THINKING.search(text):
            return "thinking"
        if len(text) > 220 or _EXPLAIN.search(text):
            return "explanation"
        return "conversation"

    def _gestures(self, text: str, emo_gesture: str, est_seconds: float) -> list[GestureCue]:
        """Timeline de gestos: cada cue no tempo em que a palavra é falada
        (estimado pela posição do texto × duração da fala)."""
        n = max(1, len(text))
        found: dict[str, tuple[float, str]] = {}
        for pat, g in _GESTURE_CUES:
            m = pat.search(text)
            if m and g not in found:
                at = round(m.start() / n * est_seconds, 2)
                found[g] = (at, m.group(0).strip()[:24])
        cues = [
            GestureCue(type=g, at_time=at, at_word=word)
            for g, (at, word) in sorted(found.items(), key=lambda kv: kv[1][0])
        ]
        if not cues and emo_gesture and emo_gesture != "none":
            cues = [GestureCue(type=emo_gesture, at_time=0.0)]
        return cues[:4]
