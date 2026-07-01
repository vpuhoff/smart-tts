from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import diskcache

from smart_tts.config import SmartTTSConfig
from smart_tts.exceptions import VoiceNotFoundError
from smart_tts.models import CachedVoice, SynthesisTask

logger = logging.getLogger(__name__)


class VoiceRegistry:
    ALL_VOICES_KEY = "all_voices"

    def __init__(self, config: SmartTTSConfig) -> None:
        self._config = config
        cache_dir = config.cache_dir.expanduser()
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache = diskcache.Cache(str(cache_dir / "voices"))

    def sync_voices(self, *, force: bool = False) -> int:
        if not force and self._cache.get(self.ALL_VOICES_KEY) is not None:
            voice_ids = self.list_voice_ids()
            logger.info("voice_sync_skipped", extra={"cached_count": len(voice_ids)})
            return len(voice_ids)

        voice_id = self._config.default_voice_id
        if not voice_id:
            self._cache.set(self.ALL_VOICES_KEY, json.dumps([]), expire=self._config.cache_ttl_voices)
            return 0

        voice = CachedVoice(
            voice_id=voice_id,
            name=voice_id,
            description="Default Fish Audio reference voice",
            labels={},
            category="fish",
            preview_url=None,
            language=None,
            cached_at=datetime.now(timezone.utc),
        )
        self.set_voice(voice)
        self._cache.set(
            self.ALL_VOICES_KEY,
            json.dumps([voice_id]),
            expire=self._config.cache_ttl_voices,
        )
        logger.info("voice_sync_complete", extra={"count": 1})
        return 1

    def set_voice(self, voice: CachedVoice) -> None:
        self._cache.set(voice.voice_id, json.dumps(voice.to_dict()))

    def register_voice(self, voice: CachedVoice) -> None:
        self.set_voice(voice)
        voice_ids = self.list_voice_ids()
        if voice.voice_id not in voice_ids:
            voice_ids.append(voice.voice_id)
            self._cache.set(
                self.ALL_VOICES_KEY,
                json.dumps(voice_ids),
                expire=self._config.cache_ttl_voices,
            )

    def get_voice(self, voice_id: str) -> CachedVoice | None:
        raw = self._cache.get(voice_id)
        if raw is None:
            return None
        return CachedVoice.from_dict(json.loads(raw))

    def list_voice_ids(self) -> list[str]:
        raw = self._cache.get(self.ALL_VOICES_KEY)
        if raw is None:
            return []
        return json.loads(raw)

    def list_voices(
        self,
        *,
        category: str | None = None,
        language: str | None = None,
        tags: list[str] | None = None,
    ) -> list[CachedVoice]:
        voices = [self.get_voice(voice_id) for voice_id in self.list_voice_ids()]
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
            ]
        if tags:
            tag_set = {tag.lower() for tag in tags}
            result = [
                voice
                for voice in result
                if tag_set.intersection({tag.lower() for tag in voice.tags})
            ]
        return result

    def resolve_voice(self, task: SynthesisTask) -> CachedVoice:
        voice_id = task.voice_id or self._config.default_voice_id
        if not voice_id:
            raise VoiceNotFoundError("No voice_id in task and no default_voice_id in config")

        voice = self.get_voice(voice_id)
        if voice is not None:
            return voice

        return CachedVoice(
            voice_id=voice_id,
            name=voice_id,
            description=task.voice_description,
            labels={},
            category="fish",
            preview_url=None,
            language=task.language,
            cached_at=datetime.now(timezone.utc),
        )

    def tag_voice(self, voice_id: str, tags: list[str]) -> None:
        voice = self._require_voice(voice_id)
        voice.tags = list(dict.fromkeys([*voice.tags, *tags]))
        self.set_voice(voice)

    def set_task_profiles(self, voice_id: str, profiles: list[str]) -> None:
        voice = self._require_voice(voice_id)
        voice.task_profiles = list(dict.fromkeys([*voice.task_profiles, *profiles]))
        self.set_voice(voice)

    def _require_voice(self, voice_id: str) -> CachedVoice:
        voice = self.get_voice(voice_id)
        if voice is None:
            raise VoiceNotFoundError(f"Voice not found in registry: {voice_id}")
        return voice
