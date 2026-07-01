from __future__ import annotations

from smart_tts.models import SynthesisTask
from smart_tts.script.breaks import script_to_fish_text

# Fish Audio S2/S2.1: [bracket] tags, not parenthesis prose (which TTS may read aloud).
# See https://docs.fish.audio/developer-guide/models-pricing/models-overview
_EMOTION_MARKS: dict[str, str] = {
    "warm": "[warm]",
    "serious": "[serious]",
    "excited": "[excited]",
    "sad": "[sad]",
    "whisper": "[whisper]",
    "calm": "[calm]",
}


def prepare_text(task: SynthesisTask) -> str:
    text = task.text.strip()
    if task.enhance_text:
        text = script_to_fish_text(text)
        if task.emotion:
            mark = _EMOTION_MARKS.get(task.emotion.lower())
            if mark and mark not in text:
                text = f"{mark} {text}"
    return text.strip()
