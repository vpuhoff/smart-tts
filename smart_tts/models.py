from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class TTSModel(str, Enum):
    """Fish Audio model identifiers (legacy enum names kept for API compatibility)."""

    ELEVEN_V3 = "s2.1-pro"
    S2_1_PRO_FREE = "s2.1-pro-free"
    ELEVEN_MULTILINGUAL_V2 = "s2-pro"
    ELEVEN_FLASH_V2_5 = "s1"

    @property
    def fish_model(self) -> str:
        return self.value

    @property
    def fallback_model(self) -> str | None:
        if self == TTSModel.ELEVEN_V3:
            return TTSModel.S2_1_PRO_FREE.value
        return None


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
    temperature: float = 0.7
    top_p: float = 0.7
    repetition_penalty: float = 1.2


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
    music_prompt: str | None = None
    ambient_prompt: str | None = None
    music_path: Path | str | None = None
    ambient_path: Path | str | None = None
    music_volume: float = 0.32
    ambient_volume: float = 0.18
    speech_volume: float = 1.0
    bed_weight: float = 0.68


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


CONTENT_TYPE_BY_FORMAT: dict[str, str] = {
    OutputFormat.MP3_44100_128.value: "audio/mpeg",
    OutputFormat.MP3_44100_192.value: "audio/mpeg",
    OutputFormat.PCM_16000.value: "audio/pcm",
    OutputFormat.PCM_22050.value: "audio/pcm",
    OutputFormat.PCM_24000.value: "audio/pcm",
    OutputFormat.PCM_44100.value: "audio/pcm",
}

FISH_MP3_BITRATE_BY_FORMAT: dict[str, int] = {
    OutputFormat.MP3_44100_128.value: 128,
    OutputFormat.MP3_44100_192.value: 192,
}
