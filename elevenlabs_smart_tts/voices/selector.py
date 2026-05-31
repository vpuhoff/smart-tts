from __future__ import annotations

import logging

from elevenlabs_smart_tts.config import SmartTTSConfig
from elevenlabs_smart_tts.exceptions import ModelVoiceIncompatibleError, VoiceCacheEmptyError, VoiceNotFoundError
from elevenlabs_smart_tts.models import CachedVoice, SynthesisTask, TTSModel

logger = logging.getLogger(__name__)


class VoiceSelector:
    def __init__(self, config: SmartTTSConfig) -> None:
        self._config = config

    def select(self, task: SynthesisTask, voices: list[CachedVoice]) -> CachedVoice:
        if not voices:
            raise VoiceCacheEmptyError("Voice cache is empty. Call sync_voices() first.")

        model = task.model or self._config.default_model

        if task.voice_id:
            voice = self._find_by_id(task.voice_id, voices)
            self._validate_model_compatibility(voice, model)
            logger.info(
                "voice_selected",
                extra={"voice_id": voice.voice_id, "score": None, "reason": "explicit"},
            )
            return voice

        if task.voice_description:
            matches = self._score_voices(task, voices, description=task.voice_description)
            if matches:
                voice, score = matches[0]
                self._validate_model_compatibility(voice, model)
                logger.info(
                    "voice_selected",
                    extra={"voice_id": voice.voice_id, "score": score, "reason": "description"},
                )
                return voice

        matches = self._score_voices(task, voices)
        if matches:
            voice, score = matches[0]
            self._validate_model_compatibility(voice, model)
            logger.info(
                "voice_selected",
                extra={"voice_id": voice.voice_id, "score": score, "reason": "scoring"},
            )
            return voice

        if self._config.default_voice_id:
            voice = self._find_by_id(self._config.default_voice_id, voices)
            self._validate_model_compatibility(voice, model)
            logger.info(
                "voice_selected",
                extra={
                    "voice_id": voice.voice_id,
                    "score": None,
                    "reason": "default_voice_id",
                },
            )
            return voice

        raise VoiceNotFoundError("Unable to select a voice for the given task.")

    def _find_by_id(self, voice_id: str, voices: list[CachedVoice]) -> CachedVoice:
        for voice in voices:
            if voice.voice_id == voice_id:
                return voice
        raise VoiceNotFoundError(f"Voice not found: {voice_id}")

    def _score_voices(
        self,
        task: SynthesisTask,
        voices: list[CachedVoice],
        *,
        description: str | None = None,
    ) -> list[tuple[CachedVoice, int]]:
        description_tokens = self._tokenize(description or task.voice_description or "")
        scored: list[tuple[CachedVoice, int]] = []

        for voice in voices:
            score = 0
            if description_tokens:
                score += self._keyword_score(description_tokens, voice)

            if task.use_case:
                use_case = task.use_case.lower()
                if voice.labels.get("use_case", "").lower() == use_case:
                    score += 5
                if use_case in {p.lower() for p in voice.task_profiles}:
                    score += 4
                if use_case in {t.lower() for t in voice.tags}:
                    score += 3

            if task.style:
                style = task.style.lower()
                if style in voice.name.lower() or style in (voice.description or "").lower():
                    score += 2
                if style in {t.lower() for t in voice.tags}:
                    score += 2

            if task.language:
                lang = task.language.lower()
                if voice.language and voice.language.lower() == lang:
                    score += 4
                if voice.labels.get("language", "").lower() == lang:
                    score += 3
                if voice.labels.get("accent", "").lower() == lang:
                    score += 2

            model = task.model or self._config.default_model
            if model == TTSModel.ELEVEN_V3 and self._is_pvc(voice):
                score -= 10

            if score > 0:
                scored.append((voice, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [token for token in text.lower().split() if token]

    @staticmethod
    def _keyword_score(tokens: list[str], voice: CachedVoice) -> int:
        haystack = " ".join(
            [
                voice.name,
                voice.description or "",
                " ".join(f"{k}:{v}" for k, v in voice.labels.items()),
                " ".join(voice.tags),
                " ".join(voice.task_profiles),
            ]
        ).lower()
        return sum(2 for token in tokens if token in haystack)

    @staticmethod
    def _is_pvc(voice: CachedVoice) -> bool:
        category = voice.category.lower()
        return category in {"cloned", "professional"} or voice.labels.get("category", "").lower() == "pvc"

    def _validate_model_compatibility(self, voice: CachedVoice, model: TTSModel) -> None:
        if model == TTSModel.ELEVEN_V3 and self._is_pvc(voice):
            raise ModelVoiceIncompatibleError(
                f"Voice {voice.voice_id} ({voice.category}) is not recommended for eleven_v3."
            )
