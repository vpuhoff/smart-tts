from __future__ import annotations

import os

import pytest

from elevenlabs_smart_tts.config import SmartTTSConfig
from elevenlabs_smart_tts.exceptions import SmartTTSError
from elevenlabs_smart_tts.models import OutputFormat, TTSModel


def test_from_env_success(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("OPENROUTER_API_TTS_PROMPT_MODEL", "anthropic/claude-3.5-sonnet")
    monkeypatch.setenv("ELEVENLABS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("ELEVENLABS_DEFAULT_MODEL", "eleven_v3")
    monkeypatch.setenv("ELEVENLABS_DEFAULT_OUTPUT_FORMAT", "mp3_44100_128")
    monkeypatch.setenv("ELEVENLABS_DEFAULT_VOICE_ID", "voice-default")

    config = SmartTTSConfig.from_env()

    assert config.elevenlabs_api_key == "el-key"
    assert config.openrouter_api_key == "or-key"
    assert config.default_model == TTSModel.ELEVEN_V3
    assert config.default_output_format == OutputFormat.MP3_44100_128
    assert config.default_voice_id == "voice-default"
    assert config.cache_dir == tmp_path / "cache"


def test_from_env_missing_required(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "ELEVENLABS_API_KEY",
        "OPENROUTER_API_KEY",
        "OPENROUTER_API_TTS_PROMPT_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(SmartTTSError, match="Missing required environment variables"):
        SmartTTSConfig.from_env()

    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.delenv("OPENROUTER_API_TTS_PROMPT_MODEL", raising=False)

    with pytest.raises(SmartTTSError):
        SmartTTSConfig.from_env()
