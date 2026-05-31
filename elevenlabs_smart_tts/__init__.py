"""ElevenLabs Smart TTS library."""

from elevenlabs_smart_tts.config import SmartTTSConfig
from elevenlabs_smart_tts.models import (
    CachedVoice,
    OutputFormat,
    SynthesisResult,
    SynthesisTask,
    TTSModel,
    VoiceSettings,
)
from elevenlabs_smart_tts.tts import SmartTTS, synthesize

__all__ = [
    "CachedVoice",
    "OutputFormat",
    "SmartTTS",
    "SmartTTSConfig",
    "SynthesisResult",
    "SynthesisTask",
    "TTSModel",
    "VoiceSettings",
    "synthesize",
]

__version__ = "0.1.0"
