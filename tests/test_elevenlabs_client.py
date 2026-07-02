from __future__ import annotations

import pytest

from smart_tts.client.elevenlabs import AsyncElevenLabsBedsClient


@pytest.mark.asyncio
async def test_async_elevenlabs_beds_client_aclose(config) -> None:
    async with AsyncElevenLabsBedsClient(config) as client:
        assert client._owns_client is True
