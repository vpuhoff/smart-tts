from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from smart_tts.config import SmartTTSConfig
from smart_tts.models import CachedVoice


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    return tmp_path / "cache"


@pytest.fixture
def config(tmp_cache_dir: Path) -> SmartTTSConfig:
    return SmartTTSConfig(
        fish_api_key="test-fish-key",
        elevenlabs_api_key="test-eleven-key",
        cache_dir=tmp_cache_dir,
        default_voice_id="voice-default",
    )


@pytest.fixture
def sample_voice() -> CachedVoice:
    return CachedVoice(
        voice_id="voice-1",
        name="Kanevsky",
        description="Detective narrator",
        labels={"language": "ru"},
        category="fish",
        preview_url=None,
        language="ru",
        cached_at=datetime.now(timezone.utc),
        tags=["narration"],
        task_profiles=["investigation"],
    )
