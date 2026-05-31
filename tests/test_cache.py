from __future__ import annotations

from datetime import datetime, timezone

from elevenlabs_smart_tts.models import CachedVoice
from elevenlabs_smart_tts.voices.cache import CacheStore


def test_cached_voice_roundtrip() -> None:
    voice = CachedVoice(
        voice_id="v1",
        name="Test",
        description="desc",
        labels={"gender": "female"},
        category="premade",
        preview_url="http://example.com",
        language="en",
        cached_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        tags=["narration"],
        task_profiles=["audiobook"],
    )
    restored = CachedVoice.from_dict(voice.to_dict())
    assert restored == voice


def test_cache_store_voice_list_ttl(config, tmp_cache_dir) -> None:
    cache = CacheStore(tmp_cache_dir)
    assert cache.is_voice_list_fresh() is False

    cache.set_voice_ids(["v1", "v2"], ttl=3600)
    assert cache.is_voice_list_fresh() is True
    assert cache.list_voice_ids() == ["v1", "v2"]


def test_cache_store_enhanced_text(config, tmp_cache_dir) -> None:
    cache = CacheStore(tmp_cache_dir)
    key = CacheStore.make_enhancement_key("model", "prompt", "text")
    cache.set_enhanced_text(key, "enhanced", ttl=60)
    assert cache.get_enhanced_text(key) == "enhanced"
