from __future__ import annotations

import re

BREAK_RE = re.compile(r'<break\s+time="([0-9.]+)s"\s*/>', re.IGNORECASE)


def parse_break_script(text: str) -> list[tuple[str, float]]:
    chunks: list[tuple[str, float]] = []
    pos = 0
    for match in BREAK_RE.finditer(text):
        phrase = text[pos : match.start()].strip()
        pause = float(match.group(1))
        if phrase:
            chunks.append((phrase, pause))
        pos = match.end()
    tail = text[pos:].strip()
    if tail:
        chunks.append((tail, 0.0))
    return chunks


def pause_markup(seconds: float) -> str:
    """Fish Audio S2/S2.1 inline tags in [square brackets]."""
    if seconds >= 1.2:
        return "[long pause]"
    if seconds >= 0.75:
        return "[pause]"
    if seconds >= 0.4:
        return "..."
    return ""


def script_to_fish_text(raw: str) -> str:
    """SSML breaks → Fish Audio S2 bracket tags."""
    if not BREAK_RE.search(raw):
        return raw.strip()
    parts: list[str] = []
    for phrase, pause in parse_break_script(raw):
        parts.append(phrase)
        mark = pause_markup(pause)
        if mark:
            parts.append(mark)
    return " ".join(parts)
