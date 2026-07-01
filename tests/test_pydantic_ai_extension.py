from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import httpx

import pytest
import respx

from smart_tts.async_tts import AsyncSmartTTS
from smart_tts.extensions.pydantic_ai import (
    PreviewSpeechTextRequest,
    SmartTTSDeps,
    SynthesizeSpeechRequest,
    SynthesizeSpeechResult,
    create_smart_tts_toolset,
    require_openrouter_api_key,
    resolve_openrouter_model,
    run_synthesize_speech,
)
from smart_tts.templates import INVESTIGATION, GenerationTemplate, TemplateRegistryInfo
from smart_tts.voices.registry import VoiceRegistry


def test_resolve_openrouter_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYDANTIC_AI_MODEL", raising=False)
    monkeypatch.delenv("OPENROUTER_API_TTS_PROMPT_MODEL", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

    assert resolve_openrouter_model() == "openrouter:google/gemini-2.5-flash"
    assert resolve_openrouter_model("anthropic/claude-sonnet-4") == "openrouter:anthropic/claude-sonnet-4"
    assert resolve_openrouter_model("openrouter:openai/gpt-4o-mini") == "openrouter:openai/gpt-4o-mini"

    monkeypatch.setenv("OPENROUTER_API_TTS_PROMPT_MODEL", "google/gemini-3.5-flash")
    assert resolve_openrouter_model() == "openrouter:google/gemini-3.5-flash"


def test_require_openrouter_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        require_openrouter_api_key()

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    assert require_openrouter_api_key() == "sk-or-test"


def test_create_smart_tts_toolset_registers_tools() -> None:
    toolset = create_smart_tts_toolset()
    assert toolset.id == "smart_tts"
    assert set(toolset.tools) == {
        "synthesize_speech",
        "list_generation_templates",
        "preview_speech_text",
    }


def test_pydantic_schemas_have_field_descriptions() -> None:
    from smart_tts.extensions.pydantic_ai import SynthesisMetadata, TemplateInfo

    models = [
        SynthesizeSpeechRequest,
        SynthesizeSpeechResult,
        SynthesisMetadata,
        TemplateInfo,
        PreviewSpeechTextRequest,
    ]
    for model in models:
        schema = model.model_json_schema()
        for field_name, field_schema in schema["properties"].items():
            if "$ref" in field_schema:
                continue
            assert "description" in field_schema, f"{model.__name__}.{field_name} missing description"


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
    assert result.template_name == "investigation"
    assert result.metadata.fish_model
    assert result.metadata.char_count > 0
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
            PreviewSpeechTextRequest(
                text='Центр, <break time="1.2s" /> на связи.',
                template="investigation",
            ),
        )
    finally:
        await tts.aclose()

    assert "[serious]" in prepared.prepared_text
    assert "[long pause]" in prepared.prepared_text
    assert prepared.template == "investigation"
    assert prepared.enhance_text is True


@respx.mock
@pytest.mark.asyncio
async def test_run_synthesize_speech_with_prebuilt_template(config, sample_voice, tmp_path) -> None:
    respx.post("https://api.fish.audio/v1/tts").mock(
        return_value=httpx.Response(200, content=b"mp3-data")
    )

    voice_registry = VoiceRegistry(config)
    voice_registry.register_voice(sample_voice)
    tts = AsyncSmartTTS(config)
    tts._registry = voice_registry

    custom = INVESTIGATION.with_overrides(name="custom-slug")
    deps = SmartTTSDeps(tts=tts, output_dir=tmp_path)
    try:
        result = await run_synthesize_speech(
            deps,
            SynthesizeSpeechRequest(text="Тест.", template="ignored-slug", mix=False),
            template=custom,
        )
    finally:
        await tts.aclose()

    assert result.template_name == "custom-slug"


@respx.mock
@pytest.mark.asyncio
async def test_run_synthesize_speech_mix_default_from_template(config, sample_voice, tmp_path) -> None:
    respx.post("https://api.fish.audio/v1/tts").mock(
        return_value=httpx.Response(200, content=b"mp3-data")
    )

    voice_registry = VoiceRegistry(config)
    voice_registry.register_voice(sample_voice)
    tts = AsyncSmartTTS(config)
    tts._registry = voice_registry

    template = GenerationTemplate(
        name="speech-only",
        voice_id=sample_voice.voice_id,
        enhance_text=False,
        mix_default=False,
    )
    deps = SmartTTSDeps(tts=tts, output_dir=tmp_path)
    try:
        result = await run_synthesize_speech(
            deps,
            SynthesizeSpeechRequest(text="Тест.", template="speech-only"),
            template=template,
        )
    finally:
        await tts.aclose()

    assert result.mixed is False


@respx.mock
@pytest.mark.asyncio
async def test_on_synthesized_hook(config, sample_voice, tmp_path) -> None:
    respx.post("https://api.fish.audio/v1/tts").mock(
        return_value=httpx.Response(200, content=b"mp3-data")
    )

    voice_registry = VoiceRegistry(config)
    voice_registry.register_voice(sample_voice)
    tts = AsyncSmartTTS(config)
    tts._registry = voice_registry

    seen: list[SynthesizeSpeechResult] = []

    async def on_synthesized(result: SynthesizeSpeechResult) -> None:
        seen.append(result)

    deps = SmartTTSDeps(tts=tts, output_dir=tmp_path, on_synthesized=on_synthesized)
    try:
        await run_synthesize_speech(
            deps,
            SynthesizeSpeechRequest(
                text="Тест.",
                template="investigation",
                mix=False,
            ),
        )
    finally:
        await tts.aclose()

    assert len(seen) == 1
    assert seen[0].template_name == "investigation"


def test_custom_template_registry_in_toolset() -> None:
    class PodcastRegistry:
        def get(self, name: str) -> GenerationTemplate:
            if name == "podcast":
                return GenerationTemplate(name="podcast", language="ru", mix_default=False)
            raise KeyError(name)

        def list_info(self) -> list[TemplateRegistryInfo]:
            return [
                TemplateRegistryInfo(
                    name="podcast",
                    template=GenerationTemplate(name="podcast", language="ru"),
                    description="Podcast preset",
                )
            ]

    toolset = create_smart_tts_toolset(registry=PodcastRegistry())
    templates = toolset.tools["list_generation_templates"].function()
    assert {item.name for item in templates} == {"podcast"}
    assert templates[0].description == "Podcast preset"


@respx.mock
@pytest.mark.asyncio
async def test_has_smart_tts_protocol_deps(config, sample_voice, tmp_path) -> None:
    respx.post("https://api.fish.audio/v1/tts").mock(
        return_value=httpx.Response(200, content=b"mp3-data")
    )

    voice_registry = VoiceRegistry(config)
    voice_registry.register_voice(sample_voice)
    tts = AsyncSmartTTS(config)
    tts._registry = voice_registry

    class AgentDeps:
        def __init__(self, tts: AsyncSmartTTS, output: Path) -> None:
            self._tts = tts
            self._output = output

        @property
        def tts(self) -> AsyncSmartTTS:
            return self._tts

        @property
        def tts_output_dir(self) -> Path:
            return self._output

    deps = AgentDeps(tts, tmp_path)
    try:
        result = await run_synthesize_speech(
            deps,
            SynthesizeSpeechRequest(
                text="Тест.",
                template="investigation",
                mix=False,
            ),
        )
    finally:
        await tts.aclose()

    assert result.template_name == "investigation"
