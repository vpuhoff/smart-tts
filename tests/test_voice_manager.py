from __future__ import annotations

import httpx
import pytest
import respx

from elevenlabs_smart_tts.client.elevenlabs import ElevenLabsClient
from elevenlabs_smart_tts.models import TTSRequest, VoiceSettings
from elevenlabs_smart_tts.voices.cache import CacheStore
from elevenlabs_smart_tts.voices.manager import VoiceManager


@respx.mock
def test_sync_voices_populates_cache(config, sample_voice, default_voice) -> None:
    respx.get("https://api.elevenlabs.io/v1/voices").mock(
        return_value=httpx.Response(
            200,
            json={
                "voices": [
                    {
                        "voice_id": sample_voice.voice_id,
                        "name": sample_voice.name,
                        "description": sample_voice.description,
                        "labels": sample_voice.labels,
                        "category": sample_voice.category,
                    },
                    {
                        "voice_id": default_voice.voice_id,
                        "name": default_voice.name,
                        "description": default_voice.description,
                        "labels": default_voice.labels,
                        "category": default_voice.category,
                    },
                ]
            },
        )
    )

    cache = CacheStore(config.cache_dir)
    with ElevenLabsClient(config) as client:
        manager = VoiceManager(config, cache, client)
        count = manager.sync_voices()

    assert count == 2
    assert manager.get_voice(sample_voice.voice_id) is not None
    assert len(manager.list_voices()) == 2


@respx.mock
def test_sync_voices_skips_when_fresh(config, sample_voice) -> None:
    cache = CacheStore(config.cache_dir)
    cache.set_voice(sample_voice)
    cache.set_voice_ids([sample_voice.voice_id], ttl=3600)

    route = respx.get("https://api.elevenlabs.io/v1/voices").mock(
        return_value=httpx.Response(200, json={"voices": []})
    )

    with ElevenLabsClient(config) as client:
        manager = VoiceManager(config, cache, client)
        count = manager.sync_voices()

    assert count == 1
    assert route.called is False


def test_list_voices_filters(config, sample_voice, default_voice) -> None:
    cache = CacheStore(config.cache_dir)
    cache.set_voice(sample_voice)
    cache.set_voice(default_voice)
    cache.set_voice_ids([sample_voice.voice_id, default_voice.voice_id], ttl=3600)

    with ElevenLabsClient(config) as client:
        manager = VoiceManager(config, cache, client)
        ru_voices = manager.list_voices(language="ru")
        tagged = manager.list_voices(tags=["support"])

    assert [voice.voice_id for voice in ru_voices] == [sample_voice.voice_id]
    assert [voice.voice_id for voice in tagged] == [sample_voice.voice_id]


def test_search_and_tag_voice(config, sample_voice) -> None:
    cache = CacheStore(config.cache_dir)
    cache.set_voice(sample_voice)
    cache.set_voice_ids([sample_voice.voice_id], ttl=3600)

    with ElevenLabsClient(config) as client:
        manager = VoiceManager(config, cache, client)
        results = manager.search_voices("professional support")
        manager.tag_voice(sample_voice.voice_id, ["premium"])
        manager.set_task_profiles(sample_voice.voice_id, ["support"])

    assert results[0].voice_id == sample_voice.voice_id
    updated = manager.get_voice(sample_voice.voice_id)
    assert updated is not None
    assert "premium" in updated.tags
    assert "support" in updated.task_profiles
