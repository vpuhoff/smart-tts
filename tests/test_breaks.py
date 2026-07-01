from __future__ import annotations

from smart_tts.script.breaks import parse_break_script, script_to_fish_text


def test_parse_break_script() -> None:
    chunks = parse_break_script('Привет, <break time="1.2s" /> мир.')
    assert chunks == [("Привет,", 1.2), ("мир.", 0.0)]


def test_script_to_fish_text() -> None:
    text = script_to_fish_text('Центр, <break time="1.2s" /> на связи.')
    assert "[long pause]" in text
    assert "Центр," in text
