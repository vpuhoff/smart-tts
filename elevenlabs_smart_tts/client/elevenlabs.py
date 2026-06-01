from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from datetime import datetime, timezone
from typing import Any, TypeVar

import httpx
from elevenlabs.client import AsyncElevenLabs, ElevenLabs
from elevenlabs.core.api_error import ApiError
from elevenlabs.types import Voice, VoiceSettings as SdkVoiceSettings

from elevenlabs_smart_tts.config import SmartTTSConfig
from elevenlabs_smart_tts.exceptions import ElevenLabsAPIError, VoiceNotFoundError
from elevenlabs_smart_tts.models import CachedVoice, TTSRequest, VoiceSettings

T = TypeVar("T")

logger = logging.getLogger(__name__)


def map_voice_response(data: dict[str, Any] | Voice) -> CachedVoice:
    if isinstance(data, Voice):
        voice_id = data.voice_id
        name = data.name or ""
        description = data.description
        labels = dict(data.labels or {})
        category = data.category or "premade"
        preview_url = data.preview_url
    else:
        labels = data.get("labels") or {}
        voice_id = data["voice_id"]
        name = data.get("name", "")
        description = data.get("description")
        category = data.get("category", "premade")
        preview_url = data.get("preview_url")

    language = labels.get("language") or labels.get("accent")
    return CachedVoice(
        voice_id=voice_id,
        name=name,
        description=description,
        labels=labels,
        category=category,
        preview_url=preview_url,
        language=language,
        cached_at=datetime.now(timezone.utc),
    )


def _to_sdk_voice_settings(settings: VoiceSettings) -> SdkVoiceSettings:
    return SdkVoiceSettings(
        stability=settings.stability,
        similarity_boost=settings.similarity_boost,
        style=settings.style,
        speed=settings.speed,
        use_speaker_boost=settings.use_speaker_boost,
    )


def _api_error_detail(exc: ApiError) -> str:
    body = exc.body
    if isinstance(body, str):
        return body
    return str(body)


def _raise_api_error(exc: ApiError) -> None:
    raise ElevenLabsAPIError(exc.status_code or 0, _api_error_detail(exc)) from exc


def _is_voice_not_found(exc: ApiError) -> bool:
    if exc.status_code not in {400, 404}:
        return False
    body = exc.body
    if not isinstance(body, dict):
        return exc.status_code == 404
    detail = body.get("detail", body)
    if not isinstance(detail, dict):
        return exc.status_code == 404
    return detail.get("code") == "voice_not_found" or detail.get("status") == "voice_not_found"


def _raise_voice_not_found(exc: ApiError, *, voice_id: str | None = None) -> None:
    suffix = f": {voice_id}" if voice_id else ""
    raise VoiceNotFoundError(
        f"Voice not found via ElevenLabs API{suffix} ({_api_error_detail(exc)})"
    ) from exc


def _is_retryable(exc: ApiError) -> bool:
    status_code = exc.status_code or 0
    return status_code == 429 or status_code >= 500


def _call_with_retry(fn: Callable[[], T], *, max_retries: int = 3) -> T:
    last_error: ApiError | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except ApiError as exc:
            last_error = exc
            if _is_voice_not_found(exc):
                _raise_voice_not_found(exc)
            if not _is_retryable(exc) or attempt >= max_retries:
                _raise_api_error(exc)
            time.sleep(2**attempt)
    assert last_error is not None
    _raise_api_error(last_error)
    raise AssertionError("unreachable")


async def _await_with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    max_retries: int = 3,
) -> T:
    last_error: ApiError | None = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except ApiError as exc:
            last_error = exc
            if _is_voice_not_found(exc):
                _raise_voice_not_found(exc)
            if not _is_retryable(exc) or attempt >= max_retries:
                _raise_api_error(exc)
            await asyncio.sleep(2**attempt)
    assert last_error is not None
    _raise_api_error(last_error)
    raise AssertionError("unreachable")


def _collect_audio(chunks: Iterator[bytes]) -> bytes:
    return b"".join(chunk for chunk in chunks if isinstance(chunk, bytes))


async def _collect_audio_async(chunks: AsyncIterator[bytes]) -> bytes:
    parts: list[bytes] = []
    async for chunk in chunks:
        if isinstance(chunk, bytes):
            parts.append(chunk)
    return b"".join(parts)


class ElevenLabsClient:
    def __init__(
        self,
        config: SmartTTSConfig,
        *,
        client: ElevenLabs | None = None,
        httpx_client: httpx.Client | None = None,
    ) -> None:
        self._config = config
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = ElevenLabs(
                api_key=config.elevenlabs_api_key,
                httpx_client=httpx_client,
                timeout=60.0,
            )
            self._owns_client = httpx_client is None

    def close(self) -> None:
        if self._owns_client:
            self._client._client_wrapper.httpx_client.httpx_client.close()

    def __enter__(self) -> ElevenLabsClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def list_voices(self) -> list[CachedVoice]:
        def _fetch() -> list[CachedVoice]:
            response = self._client.voices.get_all()
            return [map_voice_response(voice) for voice in response.voices]

        return _call_with_retry(_fetch)

    def get_voice(self, voice_id: str) -> CachedVoice:
        def _fetch() -> CachedVoice:
            return map_voice_response(self._client.voices.get(voice_id))

        try:
            return _call_with_retry(_fetch)
        except VoiceNotFoundError:
            return self._voice_outside_library(voice_id)

    def synthesize(self, voice_id: str, request: TTSRequest) -> bytes:
        def _fetch() -> bytes:
            chunks = self._client.text_to_speech.convert(
                voice_id=voice_id,
                text=request.text,
                model_id=request.model_id,
                output_format=request.output_format,  # type: ignore[arg-type]
                voice_settings=_to_sdk_voice_settings(request.voice_settings),
                language_code=request.language_code,
                optimize_streaming_latency=request.optimize_streaming_latency,
            )
            return _collect_audio(chunks)

        return _call_with_retry(_fetch)

    def _map_voice(self, data: dict[str, Any]) -> CachedVoice:
        return map_voice_response(data)

    @staticmethod
    def _voice_outside_library(voice_id: str) -> CachedVoice:
        logger.warning(
            "voice metadata unavailable from voices.get; voice may still work for text-to-speech",
            extra={"voice_id": voice_id},
        )
        return CachedVoice(
            voice_id=voice_id,
            name=voice_id,
            description=None,
            labels={},
            category="shared",
            preview_url=None,
            language=None,
            cached_at=datetime.now(timezone.utc),
        )


class AsyncElevenLabsClient:
    def __init__(
        self,
        config: SmartTTSConfig,
        *,
        client: AsyncElevenLabs | None = None,
        httpx_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = AsyncElevenLabs(
                api_key=config.elevenlabs_api_key,
                httpx_client=httpx_client,
                timeout=60.0,
            )
            self._owns_client = httpx_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client._client_wrapper.httpx_client.httpx_client.aclose()

    async def __aenter__(self) -> AsyncElevenLabsClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def list_voices(self) -> list[CachedVoice]:
        async def _fetch() -> list[CachedVoice]:
            response = await self._client.voices.get_all()
            return [map_voice_response(voice) for voice in response.voices]

        return await _await_with_retry(_fetch)

    async def get_voice(self, voice_id: str) -> CachedVoice:
        async def _fetch() -> CachedVoice:
            voice = await self._client.voices.get(voice_id)
            return map_voice_response(voice)

        try:
            return await _await_with_retry(_fetch)
        except VoiceNotFoundError:
            return ElevenLabsClient._voice_outside_library(voice_id)

    async def synthesize(self, voice_id: str, request: TTSRequest) -> bytes:
        async def _fetch() -> bytes:
            chunks = self._client.text_to_speech.convert(
                voice_id=voice_id,
                text=request.text,
                model_id=request.model_id,
                output_format=request.output_format,  # type: ignore[arg-type]
                voice_settings=_to_sdk_voice_settings(request.voice_settings),
                language_code=request.language_code,
                optimize_streaming_latency=request.optimize_streaming_latency,
            )
            return await _collect_audio_async(chunks)

        return await _await_with_retry(_fetch)
