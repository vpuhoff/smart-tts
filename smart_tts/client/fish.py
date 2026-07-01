from __future__ import annotations

import logging
from typing import Any

import httpx

from smart_tts.config import SmartTTSConfig
from smart_tts.exceptions import FishAPIError
from smart_tts.models import FISH_MP3_BITRATE_BY_FORMAT, OutputFormat, TTSModel, VoiceSettings
from smart_tts.telemetry import async_span, set_span_attributes, span

logger = logging.getLogger(__name__)


def _models_to_try(model: TTSModel) -> list[str]:
    models = [model.fish_model]
    fallback = model.fallback_model
    if fallback and fallback not in models:
        models.append(fallback)
    return models


class FishClient:
    def __init__(
        self,
        config: SmartTTSConfig,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._config = config
        self._client = client or httpx.Client(timeout=300.0)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> FishClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str,
        model: TTSModel,
        voice_settings: VoiceSettings,
        output_format: OutputFormat,
    ) -> tuple[bytes, str]:
        with span(
            "smart_tts.fish.synthesize",
            voice_id=voice_id,
            model=model.value,
            char_count=len(text),
        ) as fish_span:
            payload = self._build_payload(text, voice_id, model, voice_settings, output_format)
            models_to_try = _models_to_try(model)

            last_error: FishAPIError | None = None
            for index, attempt_model in enumerate(models_to_try):
                try:
                    with span("smart_tts.fish.request", fish_model=attempt_model):
                        audio = self._post(payload, attempt_model)
                except FishAPIError as exc:
                    last_error = exc
                    if exc.status_code == 402 and index + 1 < len(models_to_try):
                        fallback = models_to_try[index + 1]
                        logger.warning(
                            "На Fish Audio модели %s нет кредитов (402), пробую %s",
                            attempt_model,
                            fallback,
                        )
                        continue
                    raise
                else:
                    if index > 0:
                        logger.info("Fish TTS: озвучка через %s", attempt_model)
                    set_span_attributes(
                        fish_span,
                        {
                            "smart_tts.fish_model": attempt_model,
                            "smart_tts.audio_bytes": len(audio),
                        },
                    )
                    return audio, attempt_model

            assert last_error is not None
            raise last_error

    def _post(self, payload: dict[str, Any], model: str) -> bytes:
        response = self._client.post(
            self._config.fish_api_url,
            headers={
                "Authorization": f"Bearer {self._config.fish_api_key}",
                "Content-Type": "application/json",
                "model": model,
            },
            json=payload,
        )
        if response.status_code >= 400:
            raise FishAPIError(response.status_code, response.text[:500])
        return response.content

    @staticmethod
    def _build_payload(
        text: str,
        voice_id: str,
        model: TTSModel,
        voice_settings: VoiceSettings,
        output_format: OutputFormat,
    ) -> dict[str, Any]:
        return {
            "text": text,
            "reference_id": voice_id,
            "format": "mp3",
            "mp3_bitrate": FISH_MP3_BITRATE_BY_FORMAT.get(output_format.value, 128),
            "sample_rate": 44100,
            "normalize": True,
            "latency": "normal",
            "temperature": voice_settings.temperature,
            "top_p": voice_settings.top_p,
            "repetition_penalty": voice_settings.repetition_penalty,
            "condition_on_previous_chunks": True,
            "prosody": {"speed": voice_settings.speed, "volume": 0},
        }


class AsyncFishClient:
    def __init__(
        self,
        config: SmartTTSConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._client = client or httpx.AsyncClient(timeout=300.0)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> AsyncFishClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def synthesize(
        self,
        text: str,
        *,
        voice_id: str,
        model: TTSModel,
        voice_settings: VoiceSettings,
        output_format: OutputFormat,
    ) -> tuple[bytes, str]:
        async with async_span(
            "smart_tts.fish.synthesize",
            voice_id=voice_id,
            model=model.value,
            char_count=len(text),
        ) as fish_span:
            payload = FishClient._build_payload(text, voice_id, model, voice_settings, output_format)
            models_to_try = _models_to_try(model)

            last_error: FishAPIError | None = None
            for index, attempt_model in enumerate(models_to_try):
                try:
                    async with async_span("smart_tts.fish.request", fish_model=attempt_model):
                        audio = await self._post(payload, attempt_model)
                except FishAPIError as exc:
                    last_error = exc
                    if exc.status_code == 402 and index + 1 < len(models_to_try):
                        fallback = models_to_try[index + 1]
                        logger.warning(
                            "На Fish Audio модели %s нет кредитов (402), пробую %s",
                            attempt_model,
                            fallback,
                        )
                        continue
                    raise
                else:
                    if index > 0:
                        logger.info("Fish TTS: озвучка через %s", attempt_model)
                    set_span_attributes(
                        fish_span,
                        {
                            "smart_tts.fish_model": attempt_model,
                            "smart_tts.audio_bytes": len(audio),
                        },
                    )
                    return audio, attempt_model

            assert last_error is not None
            raise last_error

    async def _post(self, payload: dict[str, Any], model: str) -> bytes:
        response = await self._client.post(
            self._config.fish_api_url,
            headers={
                "Authorization": f"Bearer {self._config.fish_api_key}",
                "Content-Type": "application/json",
                "model": model,
            },
            json=payload,
        )
        if response.status_code >= 400:
            raise FishAPIError(response.status_code, response.text[:500])
        return response.content
