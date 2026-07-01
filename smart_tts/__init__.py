"""Smart TTS library: Fish Audio speech + ElevenLabs music/ambient + ffmpeg mixing."""

from smart_tts.async_tts import AsyncSmartTTS, asynthesize, asynthesize_with_template
from smart_tts.config import SmartTTSConfig
from smart_tts.models import (
    CachedVoice,
    OutputFormat,
    SynthesisResult,
    SynthesisTask,
    TTSModel,
    VoiceSettings,
)
from smart_tts.templates import (
    BUILTIN_TEMPLATES,
    INVESTIGATION,
    GenerationTemplate,
    get_template,
)
from smart_tts.tts import SmartTTS, synthesize, synthesize_with_template

__all__ = [
    "AsyncSmartTTS",
    "BUILTIN_TEMPLATES",
    "CachedVoice",
    "GenerationTemplate",
    "INVESTIGATION",
    "OutputFormat",
    "SmartTTS",
    "SmartTTSConfig",
    "SynthesisResult",
    "SynthesisTask",
    "TTSModel",
    "VoiceSettings",
    "asynthesize",
    "asynthesize_with_template",
    "get_template",
    "synthesize",
    "synthesize_with_template",
]

try:
    from smart_tts._version import __version__
except ImportError:
    __version__ = "0.0.0+unknown"
