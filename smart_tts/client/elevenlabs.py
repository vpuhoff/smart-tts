from __future__ import annotations

import logging
from pathlib import Path

from elevenlabs import ElevenLabs
from elevenlabs.core.api_error import ApiError

from smart_tts.audio.mixer import collect_chunks
from smart_tts.config import SmartTTSConfig
from smart_tts.exceptions import ElevenLabsAPIError
from smart_tts.telemetry import span

logger = logging.getLogger(__name__)

MUSIC_FALLBACK_PROMPT = (
    "Suspenseful noir strings, mystery investigation, slow dramatic instrumental, no vocals"
)


def is_permission_error(exc: ApiError) -> bool:
    body = exc.body if isinstance(exc.body, dict) else {}
    detail = body.get("detail", body)
    if isinstance(detail, dict):
        return detail.get("status") == "missing_permissions" or detail.get("code") == "subscription_required"
    return exc.status_code in {401, 403}


def _raise_api_error(exc: ApiError) -> None:
    body = exc.body if isinstance(exc.body, str) else str(exc.body)
    raise ElevenLabsAPIError(exc.status_code or 0, body) from exc


class ElevenLabsBedsClient:
    """ElevenLabs music and ambient generation (not speech TTS)."""

    def __init__(
        self,
        config: SmartTTSConfig,
        *,
        client: ElevenLabs | None = None,
    ) -> None:
        if not config.elevenlabs_api_key:
            raise ElevenLabsAPIError(0, "ELEVENLABS_API_KEY is required for music/ambient generation")
        self._config = config
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = ElevenLabs(api_key=config.elevenlabs_api_key, timeout=120.0)
            self._owns_client = True

    def close(self) -> None:
        if self._owns_client:
            self._client._client_wrapper.httpx_client.httpx_client.close()

    def __enter__(self) -> ElevenLabsBedsClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def generate_music(self, path: Path, *, prompt: str, duration_ms: int) -> bool:
        with span(
            "smart_tts.elevenlabs.generate_music",
            duration_ms=duration_ms,
            output_path=str(path),
        ):
            music_length_ms = max(10_000, min(300_000, duration_ms + 12_000))
            try:
                audio = collect_chunks(
                    self._client.music.compose(
                        prompt=prompt,
                        music_length_ms=music_length_ms,
                        force_instrumental=True,
                        output_format="mp3_44100_128",
                    )
                )
            except ApiError as exc:
                if is_permission_error(exc):
                    return False
                body = exc.body if isinstance(exc.body, dict) else {}
                detail = body.get("detail", body)
                if isinstance(detail, dict) and detail.get("code") == "bad_prompt":
                    logger.warning("music_bad_prompt", extra={"prompt": prompt[:80]})
                    try:
                        audio = collect_chunks(
                            self._client.music.compose(
                                prompt=MUSIC_FALLBACK_PROMPT,
                                music_length_ms=music_length_ms,
                                force_instrumental=True,
                                output_format="mp3_44100_128",
                            )
                        )
                    except ApiError:
                        return False
                else:
                    _raise_api_error(exc)
            path.write_bytes(audio)
            return True

    def generate_ambient(self, path: Path, *, prompt: str, duration_seconds: float) -> bool:
        with span(
            "smart_tts.elevenlabs.generate_ambient",
            duration_seconds=duration_seconds,
            output_path=str(path),
        ):
            try:
                audio = collect_chunks(
                    self._client.text_to_sound_effects.convert(
                        text=prompt,
                        duration_seconds=max(0.5, min(30.0, duration_seconds)),
                        loop=True,
                        prompt_influence=0.5,
                    )
                )
            except ApiError as exc:
                if is_permission_error(exc):
                    return False
                _raise_api_error(exc)
            path.write_bytes(audio)
            return True


class AsyncElevenLabsBedsClient:
    def __init__(
        self,
        config: SmartTTSConfig,
        *,
        client: ElevenLabs | None = None,
    ) -> None:
        if not config.elevenlabs_api_key:
            raise ElevenLabsAPIError(0, "ELEVENLABS_API_KEY is required for music/ambient generation")
        self._config = config
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = ElevenLabs(api_key=config.elevenlabs_api_key, timeout=120.0)
            self._owns_client = True

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client._client_wrapper.httpx_client.httpx_client.aclose()

    async def __aenter__(self) -> AsyncElevenLabsBedsClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def generate_music(self, path: Path, *, prompt: str, duration_ms: int) -> bool:
        import asyncio

        return await asyncio.to_thread(
            ElevenLabsBedsClient(self._config, client=self._client).generate_music,
            path,
            prompt=prompt,
            duration_ms=duration_ms,
        )

    async def generate_ambient(self, path: Path, *, prompt: str, duration_seconds: float) -> bool:
        import asyncio

        return await asyncio.to_thread(
            ElevenLabsBedsClient(self._config, client=self._client).generate_ambient,
            path,
            prompt=prompt,
            duration_seconds=duration_seconds,
        )
