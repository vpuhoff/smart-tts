from __future__ import annotations

import pytest

from elevenlabs_smart_tts.config import SmartTTSConfig
from elevenlabs_smart_tts.exceptions import ModelVoiceIncompatibleError, VoiceNotFoundError
from elevenlabs_smart_tts.models import SynthesisTask, TTSModel
from elevenlabs_smart_tts.voices.selector import VoiceSelector


def test_select_explicit_voice(config, sample_voice, default_voice) -> None:
    selector = VoiceSelector(config)
    task = SynthesisTask(text="Hello", voice_id=sample_voice.voice_id)
    voice = selector.select(task, [sample_voice, default_voice])
    assert voice.voice_id == sample_voice.voice_id


def test_select_by_description(config, sample_voice, default_voice) -> None:
    selector = VoiceSelector(config)
    task = SynthesisTask(
        text="Hello",
        voice_description="professional support",
        language="ru",
        use_case="customer_support",
    )
    voice = selector.select(task, [default_voice, sample_voice])
    assert voice.voice_id == sample_voice.voice_id


def test_select_fallback_default_voice(config, sample_voice, default_voice) -> None:
    selector = VoiceSelector(config)
    task = SynthesisTask(text="Hello")
    voice = selector.select(task, [sample_voice, default_voice])
    assert voice.voice_id == default_voice.voice_id


def test_select_pvc_with_v3_raises(config, sample_voice_pvc) -> None:
    selector = VoiceSelector(config)
    task = SynthesisTask(
        text="Hello",
        voice_id=sample_voice_pvc.voice_id,
        model=TTSModel.ELEVEN_V3,
    )
    with pytest.raises(ModelVoiceIncompatibleError):
        selector.select(task, [sample_voice_pvc])


def test_select_explicit_voice_outside_library(config, sample_voice) -> None:
    selector = VoiceSelector(config)
    task = SynthesisTask(text="Hello", voice_id="tnSpp4vdxKPjI9w0GnoV")
    voice = selector.select(task, [sample_voice])
    assert voice.voice_id == "tnSpp4vdxKPjI9w0GnoV"
    assert voice.category == "shared"


def test_select_random_fallback_when_no_match(config, sample_voice) -> None:
    config_no_default = SmartTTSConfig(
        elevenlabs_api_key=config.elevenlabs_api_key,
        openrouter_api_key=config.openrouter_api_key,
        openrouter_tts_prompt_model=config.openrouter_tts_prompt_model,
        cache_dir=config.cache_dir,
        default_voice_id=None,
    )
    selector = VoiceSelector(config_no_default)
    task = SynthesisTask(text="Hello", style="unknown-style")
    voice = selector.select(task, [sample_voice])
    assert voice.voice_id == sample_voice.voice_id


def test_select_default_voice_outside_library(config, sample_voice) -> None:
    selector = VoiceSelector(config)
    task = SynthesisTask(text="Hello", style="unknown-style")
    voice = selector.select(task, [sample_voice])
    assert voice.voice_id == "voice-default"
    assert voice.category == "shared"
