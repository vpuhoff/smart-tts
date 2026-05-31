from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from elevenlabs_smart_tts.client.elevenlabs import AsyncElevenLabsClient
from elevenlabs_smart_tts.client.openrouter import AsyncOpenRouterClient
from elevenlabs_smart_tts.config import SmartTTSConfig
from elevenlabs_smart_tts.enhancement.enhancer import AsyncTextEnhancer
from elevenlabs_smart_tts.models import (
    CONTENT_TYPE_BY_FORMAT,
    CachedVoice,
    SynthesisResult,
    SynthesisTask,
    TTSModel,
    TTSRequest,
)
from elevenlabs_smart_tts.voices.cache import CacheStore
from elevenlabs_smart_tts.voices.manager import VoiceManager
from elevenlabs_smart_tts.voices.selector import VoiceSelector

logger = logging.getLogger(__name__)


class AsyncSmartTTS:
    def __init__(self, config: SmartTTSConfig) -> None:
        self._config = config
        self._cache = CacheStore(config.cache_dir)
        self._elevenlabs = AsyncElevenLabsClient(config)
        self._openrouter = AsyncOpenRouterClient(config)
        self._voice_manager = VoiceManager(config, self._cache)
        self._voice_selector = VoiceSelector(config)
        self._text_enhancer = AsyncTextEnhancer(config, self._openrouter, self._cache)

    @classmethod
    def from_env(cls, *, dotenv_path: str | Path | None = None) -> AsyncSmartTTS:
        return cls(SmartTTSConfig.from_env(dotenv_path=dotenv_path))

    async def aclose(self) -> None:
        await self._elevenlabs.aclose()
        await self._openrouter.aclose()

    async def __aenter__(self) -> AsyncSmartTTS:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def synthesize(self, task: SynthesisTask) -> SynthesisResult:
        started = time.perf_counter()
        model = task.model or self._config.default_model
        voices = self._voice_manager.list_voices()
        voice = self._voice_selector.select(task, voices)
        voice_settings = task.voice_settings or self._config.default_voice_settings
        enhanced_text = await self._text_enhancer.enhance(task, voice, model)
        output_format = task.output_format or self._config.default_output_format
        language_code = task.language if task.language_override else None

        request = TTSRequest(
            text=enhanced_text,
            model_id=model.value,
            voice_settings=voice_settings,
            language_code=language_code,
            output_format=output_format.value,
        )
        audio = await self._elevenlabs.synthesize(voice.voice_id, request)
        duration_ms = int((time.perf_counter() - started) * 1000)
        content_type = CONTENT_TYPE_BY_FORMAT.get(output_format.value, "application/octet-stream")

        logger.info(
            "tts_complete",
            extra={
                "duration_ms": duration_ms,
                "char_count": len(enhanced_text),
                "voice_id": voice.voice_id,
                "model": model.value,
            },
        )

        return SynthesisResult(
            audio=audio,
            content_type=content_type,
            enhanced_text=enhanced_text,
            original_text=task.text,
            voice=voice,
            model=model,
            voice_settings=voice_settings,
            metadata={
                "duration_ms": duration_ms,
                "char_count": len(enhanced_text),
                "voice_id": voice.voice_id,
                "model": model.value,
            },
        )

    async def synthesize_to_file(self, task: SynthesisTask, path: Path) -> SynthesisResult:
        result = await self.synthesize(task)
        output_path = Path(path)
        await asyncio.to_thread(output_path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(output_path.write_bytes, result.audio)
        return result

    async def sync_voices(self, force: bool = False) -> int:
        if not force and self._cache.is_voice_list_fresh():
            voice_ids = self._cache.list_voice_ids()
            logger.info("voice_sync_skipped", extra={"cached_count": len(voice_ids)})
            return len(voice_ids)
        voices = await self._elevenlabs.list_voices()
        return self._voice_manager.store_voices(voices)

    def list_voices(
        self,
        *,
        category: str | None = None,
        language: str | None = None,
        tags: list[str] | None = None,
    ) -> list[CachedVoice]:
        return self._voice_manager.list_voices(
            category=category,
            language=language,
            tags=tags,
        )

    def get_voice(self, voice_id: str) -> CachedVoice | None:
        return self._voice_manager.get_voice(voice_id)

    async def enhance_text_only(self, task: SynthesisTask) -> str:
        model = task.model or self._config.default_model
        voices = self._voice_manager.list_voices()
        voice = self._voice_selector.select(task, voices)
        return await self._text_enhancer.enhance(task, voice, model)


async def asynthesize(
    text: str,
    *,
    language: str = "ru",
    style: str = "neutral",
    voice_description: str | None = None,
    model: TTSModel = TTSModel.ELEVEN_V3,
    config: SmartTTSConfig | None = None,
) -> SynthesisResult:
    tts = AsyncSmartTTS(config or SmartTTSConfig.from_env())
    try:
        return await tts.synthesize(
            SynthesisTask(
                text=text,
                language=language,
                style=style,
                voice_description=voice_description,
                model=model,
            )
        )
    finally:
        await tts.aclose()
