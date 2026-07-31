"""Sistema de voz: STT (Whisper) e TTS (Piper/XTTS)."""

from aila.voice.stt import SpeechToText
from aila.voice.tts import TextToSpeech

__all__ = ["SpeechToText", "TextToSpeech"]
