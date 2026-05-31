from __future__ import annotations


class SmartTTSError(Exception):
    """Base exception for smart TTS library."""


class VoiceNotFoundError(SmartTTSError):
    """Voice could not be found in cache or via selection."""


class VoiceCacheEmptyError(SmartTTSError):
    """Voice cache is empty; sync_voices() required."""


class TextEnhancementError(SmartTTSError):
    """Text enhancement via OpenRouter failed or produced invalid output."""


class ElevenLabsAPIError(SmartTTSError):
    """ElevenLabs API returned an error."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"ElevenLabs API error {status_code}: {detail}")


class OpenRouterAPIError(SmartTTSError):
    """OpenRouter API returned an error."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"OpenRouter API error {status_code}: {detail}")


class ModelVoiceIncompatibleError(SmartTTSError):
    """Selected voice is incompatible with the requested TTS model."""
