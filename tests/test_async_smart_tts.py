from __future__ import annotations

import httpx
import pytest
import respx

from elevenlabs_smart_tts.async_tts import AsyncSmartTTS
from elevenlabs_smart_tts.models import SynthesisTask, TTSModel


@pytest.mark.asyncio
@respx.mock
async def test_async_smart_tts_end_to_end(config, sample_voice, default_voice, tmp_path) -> None:
    respx.get("https://api.elevenlabs.io/v1/voices").mock(
        return_value=httpx.Response(
            200,
            json={
                "voices": [
                    {
                        "voice_id": sample_voice.voice_id,
                        "name": sample_voice.name,
                        "description": sample_voice.description,
                        "labels": sample_voice.labels,
                        "category": sample_voice.category,
                    },
                    {
                        "voice_id": default_voice.voice_id,
                        "name": default_voice.name,
                        "description": default_voice.description,
                        "labels": default_voice.labels,
                        "category": default_voice.category,
                    },
                ]
            },
        )
    )
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "[warm] Welcome to our support service."
                        }
                    }
                ]
            },
        )
    )
    respx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{sample_voice.voice_id}"
    ).mock(return_value=httpx.Response(200, content=b"mp3-data"))

    async with AsyncSmartTTS(config) as tts:
        await tts.sync_voices(force=True)
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
                voice_id=sample_voice.voice_id,
            )
        )

    assert result.audio == b"mp3-data"
    assert result.model == TTSModel.ELEVEN_V3
    assert file_result.audio == b"mp3-data"
    assert output_path.read_bytes() == b"mp3-data"
    assert enhanced.startswith("[warm]")
