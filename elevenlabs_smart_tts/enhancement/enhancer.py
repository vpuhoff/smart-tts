from __future__ import annotations

import logging
import re

from elevenlabs_smart_tts.client.openrouter import AsyncOpenRouterClient, OpenRouterClient
from elevenlabs_smart_tts.config import SmartTTSConfig
from elevenlabs_smart_tts.enhancement.normalizer import TextNormalizer
from elevenlabs_smart_tts.enhancement.prompts import PromptBuilder
from elevenlabs_smart_tts.exceptions import OpenRouterAPIError, TextEnhancementError
from elevenlabs_smart_tts.models import CachedVoice, SynthesisTask, TTSModel
from elevenlabs_smart_tts.voices.cache import CacheStore

logger = logging.getLogger(__name__)

_AUDIO_TAG_PATTERN = re.compile(r"\[[^\]]+\]")
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_URL_PATTERN = re.compile(r"https?://\S+|(?:[\w-]+\.)+[\w-]+", re.UNICODE)
_PUNCTUATION_PATTERN = re.compile(r"[^\w\s']+", re.UNICODE)
_NUMERIC_TOKEN_PATTERN = re.compile(r"^\d+([.,]\d+)?%?$")
MIN_PRESERVED_WORD_RATIO = 0.30


def validate_word_preservation(original: str, enhanced: str) -> None:
    original_semantic = semantic_words(original)
    enhanced_semantic = semantic_words(enhanced)
    ratio = preserved_word_ratio(original_semantic, enhanced_semantic)
    if ratio < MIN_PRESERVED_WORD_RATIO:
        raise TextEnhancementError(
            "Enhanced text preserved too few original words: "
            f"{ratio:.0%} (minimum {MIN_PRESERVED_WORD_RATIO:.0%}). "
            f"Original semantic words: {original_semantic}, "
            f"enhanced semantic words: {enhanced_semantic}."
        )


def preserved_word_ratio(original_words: list[str], enhanced_words: list[str]) -> float:
    if not original_words:
        return 1.0
    enhanced_set = set(enhanced_words)
    preserved = sum(1 for word in original_words if word in enhanced_set)
    return preserved / len(original_words)


def semantic_words(text: str) -> list[str]:
    return [word for word in extract_words(text) if not is_skippable_token(word)]


def extract_words(text: str) -> list[str]:
    cleaned = _AUDIO_TAG_PATTERN.sub(" ", text)
    cleaned = _HTML_TAG_PATTERN.sub(" ", cleaned)
    cleaned = _URL_PATTERN.sub(" ", cleaned)
    cleaned = _PUNCTUATION_PATTERN.sub(" ", cleaned)
    return [word.lower() for word in cleaned.split() if word]


def is_skippable_token(word: str) -> bool:
    if _NUMERIC_TOKEN_PATTERN.match(word):
        return True
    if word in {"http", "https", "www"}:
        return True
    return False


class TextEnhancer:
    def __init__(
        self,
        config: SmartTTSConfig,
        client: OpenRouterClient,
        cache: CacheStore,
        *,
        normalizer: TextNormalizer | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._cache = cache
        self._normalizer = normalizer or TextNormalizer()
        self._prompt_builder = prompt_builder or PromptBuilder()

    def enhance(
        self,
        task: SynthesisTask,
        voice: CachedVoice,
        model: TTSModel,
    ) -> str:
        text = task.text
        if task.normalize_text:
            text = self._normalizer.normalize(text, task.language)

        if not task.enhance_text:
            return text

        system_prompt = self._prompt_builder.build(task, voice, model)
        cache_key = CacheStore.make_enhancement_key(
            model.value,
            system_prompt,
            text,
            task.style,
            task.emotion,
            task.use_case,
            task.language,
        )
        cached = self._cache.get_enhanced_text(cache_key)
        if cached is not None:
            logger.info(
                "text_enhanced",
                extra={
                    "original_len": len(task.text),
                    "enhanced_len": len(cached),
                    "model": model.value,
                    "cached": True,
                },
            )
            return cached

        try:
            enhanced = self._client.enhance_text(
                text,
                system_prompt,
                model=self._config.openrouter_tts_prompt_model,
            )
        except OpenRouterAPIError as exc:
            raise TextEnhancementError(str(exc)) from exc

        validate_word_preservation(text, enhanced)
        self._cache.set_enhanced_text(
            cache_key,
            enhanced,
            ttl=self._config.cache_ttl_enhanced_text,
        )
        logger.info(
            "text_enhanced",
            extra={
                "original_len": len(task.text),
                "enhanced_len": len(enhanced),
                "model": model.value,
                "cached": False,
            },
        )
        logger.debug("enhanced_text", extra={"text": enhanced})
        return enhanced


class AsyncTextEnhancer:
    def __init__(
        self,
        config: SmartTTSConfig,
        client: AsyncOpenRouterClient,
        cache: CacheStore,
        *,
        normalizer: TextNormalizer | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._cache = cache
        self._normalizer = normalizer or TextNormalizer()
        self._prompt_builder = prompt_builder or PromptBuilder()

    async def enhance(
        self,
        task: SynthesisTask,
        voice: CachedVoice,
        model: TTSModel,
    ) -> str:
        text = task.text
        if task.normalize_text:
            text = self._normalizer.normalize(text, task.language)

        if not task.enhance_text:
            return text

        system_prompt = self._prompt_builder.build(task, voice, model)
        cache_key = CacheStore.make_enhancement_key(
            model.value,
            system_prompt,
            text,
            task.style,
            task.emotion,
            task.use_case,
            task.language,
        )
        cached = self._cache.get_enhanced_text(cache_key)
        if cached is not None:
            logger.info(
                "text_enhanced",
                extra={
                    "original_len": len(task.text),
                    "enhanced_len": len(cached),
                    "model": model.value,
                    "cached": True,
                },
            )
            return cached

        try:
            enhanced = await self._client.enhance_text(
                text,
                system_prompt,
                model=self._config.openrouter_tts_prompt_model,
            )
        except OpenRouterAPIError as exc:
            raise TextEnhancementError(str(exc)) from exc

        validate_word_preservation(text, enhanced)
        self._cache.set_enhanced_text(
            cache_key,
            enhanced,
            ttl=self._config.cache_ttl_enhanced_text,
        )
        logger.info(
            "text_enhanced",
            extra={
                "original_len": len(task.text),
                "enhanced_len": len(enhanced),
                "model": model.value,
                "cached": False,
            },
        )
        logger.debug("enhanced_text", extra={"text": enhanced})
        return enhanced
