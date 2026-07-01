from __future__ import annotations

import json

import httpx
import pytest
import respx

from smart_tts import INVESTIGATION, GenerationTemplate, get_template
from smart_tts.models import TTSModel, VoiceSettings
from smart_tts.tts import SmartTTS, synthesize_with_template
from smart_tts.voices.registry import VoiceRegistry


def test_to_task_includes_template_fields() -> None:
    template = INVESTIGATION.with_overrides(voice_id="voice-1")
    task = template.to_task('Привет. <break time="1.0s" /> Мир.')

    assert task.text.startswith("Привет.")
    assert task.voice_id == "voice-1"
    assert task.model == TTSModel.ELEVEN_V3
    assert task.emotion == "serious"
    assert task.music_prompt == INVESTIGATION.music_prompt
    assert task.music_volume == pytest.approx(0.32)
    assert task.speech_volume == pytest.approx(1.0)


def test_to_task_mix_false_strips_background() -> None:
    task = INVESTIGATION.to_task("Текст", mix=False)

    assert task.music_prompt is None
    assert task.ambient_prompt is None
    assert task.music_path is None
    assert task.ambient_path is None


def test_to_task_overrides() -> None:
    task = INVESTIGATION.to_task(
        "Текст",
        voice_settings=VoiceSettings(temperature=0.9),
        speech_volume=1.5,
    )

    assert task.voice_settings is not None
    assert task.voice_settings.temperature == pytest.approx(0.9)
    assert task.speech_volume == pytest.approx(1.5)


def test_from_dict_roundtrip(tmp_path) -> None:
    template = INVESTIGATION.with_overrides(
        voice_id="voice-abc",
        voice_settings=VoiceSettings(temperature=0.8, speed=1.1),
        mix_default=True,
    )
    path = tmp_path / "template.json"
    template.save_json(path)

    loaded = GenerationTemplate.from_json_file(path)
    assert loaded.name == "investigation"
    assert loaded.voice_id == "voice-abc"
    assert loaded.model == TTSModel.ELEVEN_V3
    assert loaded.mix_default is True
    assert loaded.voice_settings is not None
    assert loaded.voice_settings.temperature == pytest.approx(0.8)
    assert loaded.to_dict() == json.loads(path.read_text(encoding="utf-8"))


def test_get_template_builtin() -> None:
    assert get_template("investigation") is INVESTIGATION

    with pytest.raises(KeyError, match="Unknown template"):
        get_template("missing")


@respx.mock
def test_synthesize_text_with_template(config, sample_voice, tmp_path) -> None:
    respx.post("https://api.fish.audio/v1/tts").mock(
        return_value=httpx.Response(200, content=b"mp3-data")
    )

    registry = VoiceRegistry(config)
    registry.register_voice(sample_voice)
    template = INVESTIGATION.with_overrides(voice_id=sample_voice.voice_id)

    with SmartTTS(config) as tts:
        tts._registry = registry
        result = tts.synthesize_text(
            'Центр, <break time="1.2s" /> на связи.',
            template,
            mix=False,
        )
        out = tmp_path / "speech.mp3"
        file_result = tts.synthesize_text_to_file(
            "Добро пожаловать.",
            template,
            out,
            mix=False,
            enhance_text=False,
        )

    assert result.audio == b"mp3-data"
    assert "[serious]" in result.enhanced_text
    assert file_result.audio == b"mp3-data"
    assert out.read_bytes() == b"mp3-data"


@respx.mock
def test_synthesize_with_template_helper(config, sample_voice) -> None:
    respx.post("https://api.fish.audio/v1/tts").mock(
        return_value=httpx.Response(200, content=b"mp3-data")
    )

    registry = VoiceRegistry(config)
    registry.register_voice(sample_voice)
    template = GenerationTemplate(voice_id=sample_voice.voice_id, enhance_text=False)

    with SmartTTS(config) as tts:
        tts._registry = registry

    result = synthesize_with_template(
        "Привет!",
        template,
        config=config,
        mix=False,
    )

    assert result.audio == b"mp3-data"
    assert result.enhanced_text == "Привет!"
