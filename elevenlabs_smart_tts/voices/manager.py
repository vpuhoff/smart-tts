from __future__ import annotations

import logging
from datetime import datetime, timezone

from elevenlabs_smart_tts.client.elevenlabs import ElevenLabsClient
from elevenlabs_smart_tts.config import SmartTTSConfig
from elevenlabs_smart_tts.models import CachedVoice
from elevenlabs_smart_tts.voices.cache import CacheStore

logger = logging.getLogger(__name__)


class VoiceManager:
    def __init__(
        self,
        config: SmartTTSConfig,
        cache: CacheStore,
        client: ElevenLabsClient | None = None,
    ) -> None:
        self._config = config
        self._cache = cache
        self._client = client

    def sync_voices(self, *, force: bool = False) -> int:
        if self._client is None:
            raise RuntimeError("VoiceManager.sync_voices() requires an ElevenLabsClient")
        if not force and self._cache.is_voice_list_fresh():
            voice_ids = self._cache.list_voice_ids()
            logger.info("voice_sync_skipped", extra={"cached_count": len(voice_ids)})
            return len(voice_ids)

        voices = self._client.list_voices()
        return self.store_voices(voices)

    def store_voices(self, voices: list[CachedVoice]) -> int:
        now = datetime.now(timezone.utc)
        voice_ids: list[str] = []
        for voice in voices:
            existing = self._cache.get_voice(voice.voice_id)
            if existing is not None:
                voice.tags = existing.tags
                voice.task_profiles = existing.task_profiles
            voice.cached_at = now
            self._cache.set_voice(voice)
            voice_ids.append(voice.voice_id)

        self._cache.set_voice_ids(voice_ids, ttl=self._config.cache_ttl_voices)
        logger.info("voice_sync_complete", extra={"count": len(voice_ids)})
        return len(voice_ids)

    def get_voice(self, voice_id: str) -> CachedVoice | None:
        return self._cache.get_voice(voice_id)

    def list_voices(
        self,
        *,
        category: str | None = None,
        language: str | None = None,
        tags: list[str] | None = None,
    ) -> list[CachedVoice]:
        voices = [self._cache.get_voice(vid) for vid in self._cache.list_voice_ids()]
        result = [voice for voice in voices if voice is not None]

        if category is not None:
            result = [voice for voice in result if voice.category == category]
        if language is not None:
            lang = language.lower()
            result = [
                voice
                for voice in result
                if (voice.language and voice.language.lower() == lang)
                or voice.labels.get("language", "").lower() == lang
                or voice.labels.get("accent", "").lower() == lang
            ]
        if tags:
            tag_set = {tag.lower() for tag in tags}
            result = [
                voice
                for voice in result
                if tag_set.intersection({t.lower() for t in voice.tags})
            ]
        return result

    def search_voices(self, query: str, limit: int = 10) -> list[CachedVoice]:
        cached_ids = self._cache.get_search_result(query)
        if cached_ids is not None:
            voices = [self._cache.get_voice(voice_id) for voice_id in cached_ids]
            return [voice for voice in voices if voice is not None][:limit]

        tokens = self._tokenize(query)
        scored: list[tuple[int, CachedVoice]] = []
        for voice in self.list_voices():
            score = self._match_score(tokens, voice)
            if score > 0:
                scored.append((score, voice))

        scored.sort(key=lambda item: item[0], reverse=True)
        results = [voice for _, voice in scored[:limit]]
        self._cache.set_search_result(
            query,
            [voice.voice_id for voice in results],
            ttl=self._config.cache_ttl_voices,
        )
        return results

    def tag_voice(self, voice_id: str, tags: list[str]) -> None:
        voice = self._require_voice(voice_id)
        merged = list(dict.fromkeys([*voice.tags, *tags]))
        voice.tags = merged
        self._cache.set_voice(voice)

    def set_task_profiles(self, voice_id: str, profiles: list[str]) -> None:
        voice = self._require_voice(voice_id)
        merged = list(dict.fromkeys([*voice.task_profiles, *profiles]))
        voice.task_profiles = merged
        self._cache.set_voice(voice)

    def _require_voice(self, voice_id: str) -> CachedVoice:
        voice = self.get_voice(voice_id)
        if voice is None:
            from elevenlabs_smart_tts.exceptions import VoiceNotFoundError

            raise VoiceNotFoundError(f"Voice not found in cache: {voice_id}")
        return voice

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [token for token in text.lower().split() if token]

    @staticmethod
    def _match_score(tokens: list[str], voice: CachedVoice) -> int:
        haystack = " ".join(
            [
                voice.name,
                voice.description or "",
                " ".join(f"{k}:{v}" for k, v in voice.labels.items()),
                " ".join(voice.tags),
                " ".join(voice.task_profiles),
            ]
        ).lower()
        return sum(1 for token in tokens if token in haystack)
