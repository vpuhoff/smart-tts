from __future__ import annotations


class SmartTTSError(Exception):
    """Base exception for smart TTS library."""


class VoiceNotFoundError(SmartTTSError):
    """Voice could not be found in registry."""


class VoiceCacheEmptyError(SmartTTSError):
    """Voice registry is empty; sync_voices() required."""


class TextEnhancementError(SmartTTSError):
    """Text preparation failed or produced invalid output."""


class FishAPIError(SmartTTSError):
    """Fish Audio API returned an error."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Fish Audio API error {status_code}: {detail}")


class ElevenLabsAPIError(SmartTTSError):
    """ElevenLabs API returned an error."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"ElevenLabs API error {status_code}: {detail}")


class AudioMixError(SmartTTSError):
    """ffmpeg mixing failed."""
