from __future__ import annotations

import httpx
import pytest
import respx

from smart_tts.client.fish import FishClient
from smart_tts.exceptions import FishAPIError
from smart_tts.models import OutputFormat, TTSModel, VoiceSettings


@respx.mock
def test_fish_synthesize(config) -> None:
    route = respx.post("https://api.fish.audio/v1/tts").mock(
        return_value=httpx.Response(200, content=b"fish-mp3")
    )

    with FishClient(config) as client:
        audio, model_used = client.synthesize(
            "Привет",
            voice_id="voice-1",
            model=TTSModel.ELEVEN_V3,
            voice_settings=VoiceSettings(),
            output_format=OutputFormat.MP3_44100_128,
        )

    assert audio == b"fish-mp3"
    assert model_used == "s2.1-pro"
    assert route.called


@respx.mock
def test_fish_fallback_on_402(config) -> None:
    respx.post("https://api.fish.audio/v1/tts").mock(
        side_effect=[
            httpx.Response(402, text="no credits"),
            httpx.Response(200, content=b"free-mp3"),
        ]
    )

    with FishClient(config) as client:
        audio, model_used = client.synthesize(
            "Привет",
            voice_id="voice-1",
            model=TTSModel.ELEVEN_V3,
            voice_settings=VoiceSettings(),
            output_format=OutputFormat.MP3_44100_128,
        )

    assert audio == b"free-mp3"
    assert model_used == "s2.1-pro-free"


@respx.mock
def test_fish_error(config) -> None:
    respx.post("https://api.fish.audio/v1/tts").mock(
        return_value=httpx.Response(500, text="server error")
    )

    with FishClient(config) as client, pytest.raises(FishAPIError):
        client.synthesize(
            "Привет",
            voice_id="voice-1",
            model=TTSModel.ELEVEN_V3,
            voice_settings=VoiceSettings(),
            output_format=OutputFormat.MP3_44100_128,
        )
