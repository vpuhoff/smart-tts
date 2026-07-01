from __future__ import annotations

import httpx
import pytest
import respx

from smart_tts.async_tts import AsyncSmartTTS
from smart_tts.models import SynthesisTask, TTSModel
from smart_tts.voices.registry import VoiceRegistry


@pytest.mark.asyncio
@respx.mock
async def test_async_smart_tts_end_to_end(config, sample_voice, tmp_path) -> None:
    respx.post("https://api.fish.audio/v1/tts").mock(
        return_value=httpx.Response(200, content=b"mp3-data")
    )

    registry = VoiceRegistry(config)
    registry.register_voice(sample_voice)

    async with AsyncSmartTTS(config) as tts:
        tts._registry = registry
        result = await tts.synthesize(
            SynthesisTask(
                text="Welcome to our support service.",
                language="en",
                voice_id=sample_voice.voice_id,
            )
        )
        output_path = tmp_path / "async-out.mp3"
        file_result = await tts.synthesize_to_file(
            SynthesisTask(
                text="Welcome to our support service.",
                language="en",
                voice_id=sample_voice.voice_id,
                enhance_text=False,
            ),
            output_path,
        )
        enhanced = await tts.enhance_text_only(
            SynthesisTask(
                text="Welcome to our support service.",
                language="en",
                emotion="warm",
                voice_id=sample_voice.voice_id,
            )
        )

    assert result.audio == b"mp3-data"
    assert result.model == TTSModel.ELEVEN_V3
    assert file_result.audio == b"mp3-data"
    assert output_path.read_bytes() == b"mp3-data"
    assert "[warm]" in enhanced
