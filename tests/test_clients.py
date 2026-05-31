from __future__ import annotations

import httpx
import pytest
import respx

from elevenlabs_smart_tts.client.elevenlabs import ElevenLabsClient
from elevenlabs_smart_tts.client.openrouter import OpenRouterClient
from elevenlabs_smart_tts.exceptions import ElevenLabsAPIError, OpenRouterAPIError
from elevenlabs_smart_tts.models import TTSRequest, VoiceSettings


@respx.mock
def test_elevenlabs_list_voices(config) -> None:
    route = respx.get("https://api.elevenlabs.io/v1/voices").mock(
        return_value=httpx.Response(
            200,
            json={
                "voices": [
                    {
                        "voice_id": "voice-1",
                        "name": "Anna",
                        "description": "Support voice",
                        "labels": {"language": "ru"},
                        "category": "premade",
                    }
                ]
            },
        )
    )

    with ElevenLabsClient(config) as client:
        voices = client.list_voices()

    assert route.called
    assert len(voices) == 1
    assert voices[0].voice_id == "voice-1"
    assert voices[0].language == "ru"


@respx.mock
def test_elevenlabs_synthesize(config) -> None:
    respx.post("https://api.elevenlabs.io/v1/text-to-speech/voice-1").mock(
        return_value=httpx.Response(200, content=b"audio-bytes")
    )

    request = TTSRequest(
        text="Hello",
        model_id="eleven_v3",
        voice_settings=VoiceSettings(),
    )
    with ElevenLabsClient(config) as client:
        audio = client.synthesize("voice-1", request)

    assert audio == b"audio-bytes"


@respx.mock
def test_elevenlabs_error_mapping(config) -> None:
    respx.get("https://api.elevenlabs.io/v1/voices/voice-x").mock(
        return_value=httpx.Response(404, text="not found")
    )

    with ElevenLabsClient(config) as client:
        with pytest.raises(ElevenLabsAPIError) as exc:
            client.get_voice("voice-x")

    assert exc.value.status_code == 404


@respx.mock
def test_openrouter_enhance_text(config) -> None:
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "[excited] Hello there!"}}
                ]
            },
        )
    )

    with OpenRouterClient(config) as client:
        result = client.enhance_text("Hello there!", "system prompt")

    assert result == "[excited] Hello there!"


@respx.mock
def test_openrouter_error_mapping(config) -> None:
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(500, text="server error")
    )

    with OpenRouterClient(config) as client:
        with pytest.raises(OpenRouterAPIError) as exc:
            client.enhance_text("Hello", "system")

    assert exc.value.status_code == 500


@respx.mock
def test_elevenlabs_retry_on_429(config) -> None:
    route = respx.post("https://api.elevenlabs.io/v1/text-to-speech/voice-1").mock(
        side_effect=[
            httpx.Response(429, text="rate limited"),
            httpx.Response(200, content=b"ok"),
        ]
    )

    request = TTSRequest(
        text="Hello",
        model_id="eleven_v3",
        voice_settings=VoiceSettings(),
    )
    with ElevenLabsClient(config) as client:
        audio = client.synthesize("voice-1", request)

    assert audio == b"ok"
    assert route.call_count == 2
