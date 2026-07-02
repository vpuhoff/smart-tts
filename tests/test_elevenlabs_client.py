from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from smart_tts.client.elevenlabs import (
    AsyncElevenLabsBedsClient,
    ElevenLabsBedsClient,
    _aclose_elevenlabs_http_client,
    _close_elevenlabs_http_client,
)


def _make_elevenlabs_mock(*, httpx_client: object) -> MagicMock:
    client = MagicMock()
    client._client_wrapper.httpx_client.httpx_client = httpx_client
    return client


@pytest.mark.asyncio
async def test_async_elevenlabs_beds_client_aclose(config) -> None:
    async with AsyncElevenLabsBedsClient(config) as client:
        assert client._owns_client is True


@pytest.mark.asyncio
async def test_aclose_uses_async_client_aclose_when_available() -> None:
    httpx_client = MagicMock()
    httpx_client.aclose = AsyncMock()
    del httpx_client.close

    await _aclose_elevenlabs_http_client(_make_elevenlabs_mock(httpx_client=httpx_client))

    httpx_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_aclose_uses_sync_client_close_via_thread() -> None:
    httpx_client = MagicMock()
    httpx_client.close = MagicMock()
    del httpx_client.aclose

    await _aclose_elevenlabs_http_client(_make_elevenlabs_mock(httpx_client=httpx_client))

    httpx_client.close.assert_called_once()


def test_close_uses_sync_client_close() -> None:
    httpx_client = MagicMock()

    _close_elevenlabs_http_client(_make_elevenlabs_mock(httpx_client=httpx_client))

    httpx_client.close.assert_called_once()


def test_beds_client_does_not_close_shared_client(config) -> None:
    shared = _make_elevenlabs_mock(httpx_client=MagicMock())
    client = ElevenLabsBedsClient(config, client=shared)

    client.close()

    shared._client_wrapper.httpx_client.httpx_client.close.assert_not_called()
