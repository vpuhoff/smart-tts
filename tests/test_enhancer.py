from __future__ import annotations

import httpx
import pytest
import respx

from elevenlabs_smart_tts.client.openrouter import OpenRouterClient
from elevenlabs_smart_tts.enhancement.enhancer import TextEnhancer
from elevenlabs_smart_tts.enhancement.prompts import PromptBuilder
from elevenlabs_smart_tts.exceptions import TextEnhancementError
from elevenlabs_smart_tts.models import SynthesisTask, TTSModel
from elevenlabs_smart_tts.voices.cache import CacheStore


def test_prompt_builder_v3_contains_audio_tags(sample_voice) -> None:
    builder = PromptBuilder()
    task = SynthesisTask(text="Hello", style="dramatic", emotion="excited")
    prompt = builder.build(task, sample_voice, TTSModel.ELEVEN_V3)
    assert "[whispers]" in prompt
    assert "DO NOT use SSML break tags" in prompt


@respx.mock
def test_enhancer_success(config, sample_voice) -> None:
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "[excited] Hello world!"}}]},
        )
    )

    cache = CacheStore(config.cache_dir)
    with OpenRouterClient(config) as client:
        enhancer = TextEnhancer(config, client, cache)
        task = SynthesisTask(text="Hello world!", enhance_text=True, normalize_text=False)
        result = enhancer.enhance(task, sample_voice, TTSModel.ELEVEN_V3)

    assert result == "[excited] Hello world!"


@respx.mock
def test_enhancer_cache_hit(config, sample_voice) -> None:
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "[calm] Hello world!"}}]},
        )
    )

    cache = CacheStore(config.cache_dir)
    with OpenRouterClient(config) as client:
        enhancer = TextEnhancer(config, client, cache)
        task = SynthesisTask(text="Hello world!", enhance_text=True, normalize_text=False)
        first = enhancer.enhance(task, sample_voice, TTSModel.ELEVEN_V3)
        second = enhancer.enhance(task, sample_voice, TTSModel.ELEVEN_V3)

    assert first == second == "[calm] Hello world!"
    assert route.call_count == 1


@respx.mock
def test_enhancer_rejects_word_changes(config, sample_voice) -> None:
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "[excited] Hello totally different content now",
                        }
                    }
                ]
            },
        )
    )

    cache = CacheStore(config.cache_dir)
    with OpenRouterClient(config) as client:
        enhancer = TextEnhancer(config, client, cache)
        task = SynthesisTask(
            text="Hello world foo bar baz",
            enhance_text=True,
            normalize_text=False,
        )
        with pytest.raises(TextEnhancementError, match="preserved too few original words"):
            enhancer.enhance(task, sample_voice, TTSModel.ELEVEN_V3)


def test_enhancer_skips_llm_when_disabled(config, sample_voice) -> None:
    cache = CacheStore(config.cache_dir)
    with OpenRouterClient(config) as client:
        enhancer = TextEnhancer(config, client, cache)
        task = SynthesisTask(text="Hello world!", enhance_text=False)
        result = enhancer.enhance(task, sample_voice, TTSModel.ELEVEN_V3)

    assert result == "Hello world!"


@respx.mock
def test_enhancer_allows_number_and_html_normalization(config, sample_voice) -> None:
    original = (
        "<b>26 мая 2026</b> — уникальные теплицы в Беларуси. "
        "<i>Источник: agronews.com</i><br>"
        "Ожидается рост урожайности на 15%."
    )
    enhanced = (
        "[informative] Двадцать шестое мая две тысячи двадцать шестого года — "
        "уникальные теплицы в Беларуси. Источник: агроньюс точка ком. "
        "Ожидается рост урожайности на пятнадцать процентов."
    )
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": enhanced}}]},
        )
    )

    cache = CacheStore(config.cache_dir)
    with OpenRouterClient(config) as client:
        enhancer = TextEnhancer(config, client, cache)
        task = SynthesisTask(text=original, language="ru", enhance_text=True, normalize_text=False)
        result = enhancer.enhance(task, sample_voice, TTSModel.ELEVEN_V3)

    assert result == enhanced


def test_semantic_word_validation_helpers() -> None:
    enhancer = TextEnhancer.__new__(TextEnhancer)
    original = "<b>26 мая</b> agronews.com текст"
    enhanced = "двадцать шестое мая агроньюс точка ком текст"

    original_semantic = enhancer._semantic_words(original)
    enhanced_semantic = enhancer._semantic_words(enhanced)

    assert "май" in original_semantic or "мая" in original_semantic
    assert "agronews" not in original_semantic
    assert "com" not in original_semantic
    ratio = enhancer._preserved_word_ratio(original_semantic, enhanced_semantic)
    assert ratio >= 0.30

