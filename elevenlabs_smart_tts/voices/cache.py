from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import diskcache

from elevenlabs_smart_tts.models import CachedVoice


class CacheStore:
    ALL_VOICES_KEY = "all_voices"
    VOICE_LIST_SYNCED_AT_KEY = "voice_list_synced_at"

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir.expanduser()
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self.voices = diskcache.Cache(str(self._cache_dir / "voices"))
        self.voice_list = diskcache.Cache(str(self._cache_dir / "voice_list"))
        self.voice_index = diskcache.Cache(str(self._cache_dir / "voice_index"))
        self.enhanced_text = diskcache.Cache(str(self._cache_dir / "enhanced_text"))

    def set_voice(self, voice: CachedVoice) -> None:
        self.voices.set(voice.voice_id, json.dumps(voice.to_dict()))

    def get_voice(self, voice_id: str) -> CachedVoice | None:
        raw = self.voices.get(voice_id)
        if raw is None:
            return None
        return CachedVoice.from_dict(json.loads(raw))

    def delete_voice(self, voice_id: str) -> None:
        self.voices.delete(voice_id)

    def list_voice_ids(self) -> list[str]:
        raw = self.voice_list.get(self.ALL_VOICES_KEY)
        if raw is None:
            return []
        return json.loads(raw)

    def set_voice_ids(self, voice_ids: list[str], *, ttl: int) -> None:
        self.voice_list.set(self.ALL_VOICES_KEY, json.dumps(voice_ids), expire=ttl)
        self.voice_list.set(
            self.VOICE_LIST_SYNCED_AT_KEY,
            json.dumps({"count": len(voice_ids)}),
            expire=ttl,
        )

    def is_voice_list_fresh(self) -> bool:
        return self.voice_list.get(self.ALL_VOICES_KEY) is not None

    def set_search_result(self, query: str, voice_ids: list[str], *, ttl: int) -> None:
        key = self._normalize_query(query)
        self.voice_index.set(key, json.dumps(voice_ids), expire=ttl)

    def get_search_result(self, query: str) -> list[str] | None:
        key = self._normalize_query(query)
        raw = self.voice_index.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def get_enhanced_text(self, cache_key: str) -> str | None:
        return self.enhanced_text.get(cache_key)

    def set_enhanced_text(self, cache_key: str, text: str, *, ttl: int) -> None:
        self.enhanced_text.set(cache_key, text, expire=ttl)

    @staticmethod
    def make_enhancement_key(*parts: Any) -> str:
        payload = json.dumps(parts, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_query(query: str) -> str:
        return " ".join(query.lower().split())
