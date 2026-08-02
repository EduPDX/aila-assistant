"""Sistema de voz: STT (Whisper) e TTS (SAPI/Piper)."""

from aila.voice.stt import SpeechToText
from aila.voice.system import VoiceSystem
from aila.voice.tts import TextToSpeech

__all__ = ["SpeechToText", "TextToSpeech", "VoiceSystem"]
