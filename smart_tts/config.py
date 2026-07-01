from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from smart_tts.exceptions import SmartTTSError
from smart_tts.models import OutputFormat, TTSModel, VoiceSettings

DEFAULT_VOICE_ID = "67d37d81cb7340b391e9461d6671de03"


@dataclass
class SmartTTSConfig:
    fish_api_key: str
    elevenlabs_api_key: str | None = None
    cache_dir: Path = field(default_factory=lambda: Path("~/.cache/smart-tts"))
    default_model: TTSModel = TTSModel.ELEVEN_V3
    default_output_format: OutputFormat = OutputFormat.MP3_44100_128
    default_voice_settings: VoiceSettings = field(default_factory=VoiceSettings)
    default_voice_id: str | None = DEFAULT_VOICE_ID
    fish_api_url: str = "https://api.fish.audio/v1/tts"
    cache_ttl_voices: int = 86400

    def __post_init__(self) -> None:
        self.cache_dir = Path(self.cache_dir).expanduser()

    @classmethod
    def from_env(cls, *, dotenv_path: str | Path | None = None) -> SmartTTSConfig:
        if dotenv_path is not None:
            load_dotenv(dotenv_path)
        else:
            load_dotenv()

        fish_api_key = os.getenv("FISH_API_KEY", "").strip()
        if not fish_api_key:
            raise SmartTTSError("Missing required environment variable: FISH_API_KEY")

        elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "").strip() or None
        cache_dir = os.getenv("ELEVENLABS_CACHE_DIR", str(Path("~/.cache/smart-tts")))
        default_model = os.getenv("FISH_DEFAULT_MODEL", TTSModel.ELEVEN_V3.value)
        default_output_format = os.getenv(
            "ELEVENLABS_DEFAULT_OUTPUT_FORMAT",
            OutputFormat.MP3_44100_128.value,
        )
        default_voice_id = (
            os.getenv("FISH_DEFAULT_VOICE_ID", os.getenv("ELEVENLABS_DEFAULT_VOICE_ID", DEFAULT_VOICE_ID))
            .strip()
            or DEFAULT_VOICE_ID
        )
        fish_api_url = os.getenv("FISH_API_URL", "https://api.fish.audio/v1/tts")

        return cls(
            fish_api_key=fish_api_key,
            elevenlabs_api_key=elevenlabs_api_key,
            cache_dir=Path(cache_dir),
            default_model=TTSModel(default_model),
            default_output_format=OutputFormat(default_output_format),
            default_voice_id=default_voice_id,
            fish_api_url=fish_api_url,
        )
