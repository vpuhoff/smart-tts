"""ElevenLabs Smart TTS library."""

from elevenlabs_smart_tts.async_tts import AsyncSmartTTS, asynthesize
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
    "AsyncSmartTTS",
    "CachedVoice",
    "OutputFormat",
    "SmartTTS",
    "SmartTTSConfig",
    "SynthesisResult",
    "SynthesisTask",
    "TTSModel",
    "VoiceSettings",
    "asynthesize",
    "synthesize",
]

try:
    from elevenlabs_smart_tts._version import __version__
except ImportError:
    __version__ = "0.0.0+unknown"
