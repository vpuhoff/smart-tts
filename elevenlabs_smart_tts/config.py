from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from elevenlabs_smart_tts.exceptions import SmartTTSError
from elevenlabs_smart_tts.models import OutputFormat, TTSModel, VoiceSettings


@dataclass
class SmartTTSConfig:
    elevenlabs_api_key: str
    openrouter_api_key: str
    openrouter_tts_prompt_model: str
    cache_dir: Path = field(default_factory=lambda: Path("~/.cache/elevenlabs-smart-tts"))
    default_model: TTSModel = TTSModel.ELEVEN_V3
    default_output_format: OutputFormat = OutputFormat.MP3_44100_128
    default_voice_settings: VoiceSettings = field(default_factory=VoiceSettings)
    default_voice_id: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    cache_ttl_voices: int = 86400
    cache_ttl_enhanced_text: int = 3600

    def __post_init__(self) -> None:
        self.cache_dir = Path(self.cache_dir).expanduser()

    @classmethod
    def from_env(cls, *, dotenv_path: str | Path | None = None) -> SmartTTSConfig:
        if dotenv_path is not None:
            load_dotenv(dotenv_path)
        else:
            load_dotenv()

        elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        openrouter_tts_prompt_model = os.getenv("OPENROUTER_API_TTS_PROMPT_MODEL", "").strip()

        missing = [
            name
            for name, value in (
                ("ELEVENLABS_API_KEY", elevenlabs_api_key),
                ("OPENROUTER_API_KEY", openrouter_api_key),
                ("OPENROUTER_API_TTS_PROMPT_MODEL", openrouter_tts_prompt_model),
            )
            if not value
        ]
        if missing:
            raise SmartTTSError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        cache_dir = os.getenv(
            "ELEVENLABS_CACHE_DIR",
            str(Path("~/.cache/elevenlabs-smart-tts")),
        )
        default_model = os.getenv("ELEVENLABS_DEFAULT_MODEL", TTSModel.ELEVEN_V3.value)
        default_output_format = os.getenv(
            "ELEVENLABS_DEFAULT_OUTPUT_FORMAT",
            OutputFormat.MP3_44100_128.value,
        )
        default_voice_id = os.getenv("ELEVENLABS_DEFAULT_VOICE_ID", "").strip() or None
        openrouter_base_url = os.getenv(
            "OPENROUTER_BASE_URL",
            "https://openrouter.ai/api/v1",
        )

        return cls(
            elevenlabs_api_key=elevenlabs_api_key,
            openrouter_api_key=openrouter_api_key,
            openrouter_tts_prompt_model=openrouter_tts_prompt_model,
            cache_dir=Path(cache_dir),
            default_model=TTSModel(default_model),
            default_output_format=OutputFormat(default_output_format),
            default_voice_id=default_voice_id,
            openrouter_base_url=openrouter_base_url,
        )
