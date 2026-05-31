from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from elevenlabs_smart_tts.client.retry import async_request_with_retry, request_with_retry
from elevenlabs_smart_tts.config import SmartTTSConfig
from elevenlabs_smart_tts.exceptions import ElevenLabsAPIError
from elevenlabs_smart_tts.models import CachedVoice, TTSRequest


class ElevenLabsClient:
    BASE_URL = "https://api.elevenlabs.io/v1"

    def __init__(self, config: SmartTTSConfig, *, client: httpx.Client | None = None) -> None:
        self._config = config
        self._client = client or httpx.Client(
            base_url=self.BASE_URL,
            headers={"xi-api-key": config.elevenlabs_api_key},
            timeout=60.0,
        )
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> ElevenLabsClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def list_voices(self) -> list[CachedVoice]:
        response = request_with_retry(
            lambda: self._client.get("/voices"),
            max_retries=3,
        )
        if response.status_code >= 400:
            raise ElevenLabsAPIError(response.status_code, response.text)
        payload = response.json()
        voices = payload.get("voices", payload if isinstance(payload, list) else [])
        return [map_voice_response(voice) for voice in voices]

    def get_voice(self, voice_id: str) -> CachedVoice:
        response = request_with_retry(
            lambda: self._client.get(f"/voices/{voice_id}"),
            max_retries=3,
        )
        if response.status_code >= 400:
            raise ElevenLabsAPIError(response.status_code, response.text)
        return map_voice_response(response.json())

    def synthesize(self, voice_id: str, request: TTSRequest) -> bytes:
        params = {"output_format": request.output_format}
        response = request_with_retry(
            lambda: self._client.post(
                f"/text-to-speech/{voice_id}",
                params=params,
                json=request.to_api_dict(),
            ),
            max_retries=3,
        )
        if response.status_code >= 400:
            raise ElevenLabsAPIError(response.status_code, response.text)
        return response.content

    def _map_voice(self, data: dict[str, Any]) -> CachedVoice:
        return map_voice_response(data)


def map_voice_response(data: dict[str, Any]) -> CachedVoice:
    labels = data.get("labels") or {}
    language = labels.get("language") or labels.get("accent")
    return CachedVoice(
        voice_id=data["voice_id"],
        name=data.get("name", ""),
        description=data.get("description"),
        labels=labels,
        category=data.get("category", "premade"),
        preview_url=data.get("preview_url"),
        language=language,
        cached_at=datetime.now(timezone.utc),
    )


class AsyncElevenLabsClient:
    BASE_URL = "https://api.elevenlabs.io/v1"

    def __init__(
        self,
        config: SmartTTSConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._client = client or httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"xi-api-key": config.elevenlabs_api_key},
            timeout=60.0,
        )
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> AsyncElevenLabsClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def list_voices(self) -> list[CachedVoice]:
        response = await async_request_with_retry(
            lambda: self._client.get("/voices"),
            max_retries=3,
        )
        if response.status_code >= 400:
            raise ElevenLabsAPIError(response.status_code, response.text)
        payload = response.json()
        voices = payload.get("voices", payload if isinstance(payload, list) else [])
        return [map_voice_response(voice) for voice in voices]

    async def get_voice(self, voice_id: str) -> CachedVoice:
        response = await async_request_with_retry(
            lambda: self._client.get(f"/voices/{voice_id}"),
            max_retries=3,
        )
        if response.status_code >= 400:
            raise ElevenLabsAPIError(response.status_code, response.text)
        return map_voice_response(response.json())

    async def synthesize(self, voice_id: str, request: TTSRequest) -> bytes:
        params = {"output_format": request.output_format}
        response = await async_request_with_retry(
            lambda: self._client.post(
                f"/text-to-speech/{voice_id}",
                params=params,
                json=request.to_api_dict(),
            ),
            max_retries=3,
        )
        if response.status_code >= 400:
            raise ElevenLabsAPIError(response.status_code, response.text)
        return response.content
