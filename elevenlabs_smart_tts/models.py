from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TTSModel(str, Enum):
    ELEVEN_V3 = "eleven_v3"
    ELEVEN_MULTILINGUAL_V2 = "eleven_multilingual_v2"
    ELEVEN_FLASH_V2_5 = "eleven_flash_v2_5"


class OutputFormat(str, Enum):
    MP3_44100_128 = "mp3_44100_128"
    MP3_44100_192 = "mp3_44100_192"
    PCM_16000 = "pcm_16000"
    PCM_22050 = "pcm_22050"
    PCM_24000 = "pcm_24000"
    PCM_44100 = "pcm_44100"


@dataclass
class VoiceSettings:
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    speed: float = 1.0
    use_speaker_boost: bool = True

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "stability": self.stability,
            "similarity_boost": self.similarity_boost,
            "style": self.style,
            "speed": self.speed,
            "use_speaker_boost": self.use_speaker_boost,
        }


@dataclass
class CachedVoice:
    voice_id: str
    name: str
    description: str | None
    labels: dict[str, str]
    category: str
    preview_url: str | None
    language: str | None
    cached_at: datetime
    tags: list[str] = field(default_factory=list)
    task_profiles: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["cached_at"] = self.cached_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CachedVoice:
        cached_at = data["cached_at"]
        if isinstance(cached_at, str):
            cached_at = datetime.fromisoformat(cached_at)
        return cls(
            voice_id=data["voice_id"],
            name=data["name"],
            description=data.get("description"),
            labels=data.get("labels") or {},
            category=data.get("category", "premade"),
            preview_url=data.get("preview_url"),
            language=data.get("language"),
            cached_at=cached_at,
            tags=data.get("tags") or [],
            task_profiles=data.get("task_profiles") or [],
        )


@dataclass
class SynthesisTask:
    text: str
    language: str | None = None
    model: TTSModel | None = None
    voice_id: str | None = None
    voice_description: str | None = None
    style: str | None = None
    emotion: str | None = None
    use_case: str | None = None
    enhance_text: bool = True
    normalize_text: bool = True
    voice_settings: VoiceSettings | None = None
    output_format: OutputFormat | None = None
    language_override: bool = False


@dataclass
class SynthesisResult:
    audio: bytes
    content_type: str
    enhanced_text: str
    original_text: str
    voice: CachedVoice
    model: TTSModel
    voice_settings: VoiceSettings
    metadata: dict[str, Any]


@dataclass
class TTSRequest:
    text: str
    model_id: str
    voice_settings: VoiceSettings
    language_code: str | None = None
    output_format: str = "mp3_44100_128"
    optimize_streaming_latency: int | None = None

    def to_api_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "text": self.text,
            "model_id": self.model_id,
            "voice_settings": self.voice_settings.to_api_dict(),
        }
        if self.language_code is not None:
            payload["language_code"] = self.language_code
        if self.optimize_streaming_latency is not None:
            payload["optimize_streaming_latency"] = self.optimize_streaming_latency
        return payload


CONTENT_TYPE_BY_FORMAT: dict[str, str] = {
    OutputFormat.MP3_44100_128.value: "audio/mpeg",
    OutputFormat.MP3_44100_192.value: "audio/mpeg",
    OutputFormat.PCM_16000.value: "audio/pcm",
    OutputFormat.PCM_22050.value: "audio/pcm",
    OutputFormat.PCM_24000.value: "audio/pcm",
    OutputFormat.PCM_44100.value: "audio/pcm",
}
