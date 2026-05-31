from __future__ import annotations

from elevenlabs_smart_tts.enhancement.normalizer import TextNormalizer


def test_normalize_money() -> None:
    normalizer = TextNormalizer()
    result = normalizer.normalize("The total is $42.50 today.", "en")
    assert "forty-two dollars and fifty cents" in result


def test_normalize_phone() -> None:
    normalizer = TextNormalizer()
    result = normalizer.normalize("Call 555-555-5555 now.", "en")
    assert "five five five" in result


def test_normalize_date() -> None:
    normalizer = TextNormalizer()
    result = normalizer.normalize("Meeting on 3/14/2024.", "en")
    assert "March" in result
    assert "14th" in result


def test_non_english_passthrough() -> None:
    normalizer = TextNormalizer()
    text = "Стоимость $42.50"
    assert normalizer.normalize(text, "ru") == text
