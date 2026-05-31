from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from elevenlabs_smart_tts.config import SmartTTSConfig
from elevenlabs_smart_tts.models import CachedVoice, TTSModel, VoiceSettings


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    return tmp_path / "cache"


@pytest.fixture
def config(tmp_cache_dir: Path) -> SmartTTSConfig:
    return SmartTTSConfig(
        elevenlabs_api_key="test-eleven-key",
        openrouter_api_key="test-openrouter-key",
        openrouter_tts_prompt_model="anthropic/claude-3.5-sonnet",
        cache_dir=tmp_cache_dir,
        default_voice_id="voice-default",
    )


@pytest.fixture
def sample_voice() -> CachedVoice:
    return CachedVoice(
        voice_id="voice-1",
        name="Anna Professional",
        description="Warm professional support voice",
        labels={"gender": "female", "use_case": "customer_support", "language": "ru"},
        category="premade",
        preview_url=None,
        language="ru",
        cached_at=datetime.now(timezone.utc),
        tags=["support"],
        task_profiles=["customer_support"],
    )


@pytest.fixture
def sample_voice_pvc() -> CachedVoice:
    return CachedVoice(
        voice_id="voice-pvc",
        name="PVC Clone",
        description="Professional cloned voice",
        labels={"category": "pvc"},
        category="cloned",
        preview_url=None,
        language="en",
        cached_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def default_voice() -> CachedVoice:
    return CachedVoice(
        voice_id="voice-default",
        name="Default Voice",
        description="Fallback voice",
        labels={"use_case": "general"},
        category="premade",
        preview_url=None,
        language="en",
        cached_at=datetime.now(timezone.utc),
    )
