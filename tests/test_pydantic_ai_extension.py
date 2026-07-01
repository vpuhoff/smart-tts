from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from smart_tts.async_tts import AsyncSmartTTS
from smart_tts.extensions.pydantic_ai import (
    SmartTTSDeps,
    SynthesizeSpeechRequest,
    create_smart_tts_toolset,
    run_synthesize_speech,
)
from smart_tts.templates import INVESTIGATION
from smart_tts.voices.registry import VoiceRegistry


def test_create_smart_tts_toolset_registers_tools() -> None:
    toolset = create_smart_tts_toolset()
    assert toolset.id == "smart_tts"
    assert set(toolset.tools) == {
        "synthesize_speech",
        "list_generation_templates",
        "preview_speech_text",
    }


def test_list_generation_templates_tool() -> None:
    toolset = create_smart_tts_toolset()
    templates = toolset.tools["list_generation_templates"].function()
    names = {item.name for item in templates}
    assert "investigation" in names
    assert "default" in names


@respx.mock
@pytest.mark.asyncio
async def test_run_synthesize_speech(config, sample_voice, tmp_path) -> None:
    respx.post("https://api.fish.audio/v1/tts").mock(
        return_value=httpx.Response(200, content=b"mp3-data")
    )

    registry = VoiceRegistry(config)
    registry.register_voice(sample_voice)
    tts = AsyncSmartTTS(config)
    tts._registry = registry

    deps = SmartTTSDeps(tts=tts, output_dir=tmp_path)
    try:
        result = await run_synthesize_speech(
            deps,
            SynthesizeSpeechRequest(
                text='Центр, <break time="1.2s" /> на связи.',
                template="investigation",
                mix=False,
                output_filename="agent_speech.mp3",
            ),
        )
    finally:
        await tts.aclose()

    assert result.path.endswith("agent_speech.mp3")
    assert "[serious]" in result.enhanced_text
    assert result.voice_id == INVESTIGATION.voice_id
    assert result.model == INVESTIGATION.model.value
    assert result.mixed is False
    assert Path(result.path).read_bytes() == b"mp3-data"


@pytest.mark.asyncio
async def test_preview_speech_text_tool(config, sample_voice, tmp_path) -> None:
    registry = VoiceRegistry(config)
    registry.register_voice(sample_voice)
    tts = AsyncSmartTTS(config)
    tts._registry = registry

    deps = SmartTTSDeps(tts=tts, output_dir=tmp_path)
    toolset = create_smart_tts_toolset()
    preview = toolset.tools["preview_speech_text"].function

    from pydantic_ai import RunContext

    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps

    try:
        prepared = await preview(
            ctx,
            'Центр, <break time="1.2s" /> на связи.',
            template="investigation",
        )
    finally:
        await tts.aclose()

    assert "[serious]" in prepared
    assert "[long pause]" in prepared
