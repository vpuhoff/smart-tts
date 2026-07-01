from __future__ import annotations

import pytest

from smart_tts.config import SmartTTSConfig
from smart_tts.exceptions import SmartTTSError
from smart_tts.models import OutputFormat, TTSModel


def test_from_env_success(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("FISH_API_KEY", "fish-key")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setenv("ELEVENLABS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FISH_DEFAULT_MODEL", "s2.1-pro")
    monkeypatch.setenv("ELEVENLABS_DEFAULT_OUTPUT_FORMAT", "mp3_44100_128")
    monkeypatch.setenv("FISH_DEFAULT_VOICE_ID", "voice-default")

    config = SmartTTSConfig.from_env()

    assert config.fish_api_key == "fish-key"
    assert config.elevenlabs_api_key == "el-key"
    assert config.default_model == TTSModel.ELEVEN_V3
    assert config.default_output_format == OutputFormat.MP3_44100_128
    assert config.default_voice_id == "voice-default"
    assert config.cache_dir == tmp_path / "cache"


def test_from_env_missing_required(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.delenv("FISH_API_KEY", raising=False)

    missing_env = tmp_path / "missing.env"
    with pytest.raises(SmartTTSError, match="FISH_API_KEY"):
        SmartTTSConfig.from_env(dotenv_path=missing_env)
