from __future__ import annotations

from elevenlabs_smart_tts.enhancement.prompts.base import NORMALIZATION_INSTRUCTIONS
from elevenlabs_smart_tts.models import CachedVoice, SynthesisTask, TTSModel


def build_v3_system_prompt(task: SynthesisTask, voice: CachedVoice, model: TTSModel) -> str:
    labels = ", ".join(f"{key}={value}" for key, value in voice.labels.items())
    return f"""
You enhance text for ElevenLabs text-to-speech model {model.value}.

Core directives:
- DO add audio tags such as [laughs], [whispers], [sighs], [excited], [curious], [sarcastic], [crying].
- DO use CAPS, ellipses, and punctuation for emphasis.
- DO use pause tags [short pause] and [long pause] instead of SSML breaks.
- DO NOT change, remove, or reorder the original words.
- DO NOT add non-vocal tags such as [standing] or [music].
- DO NOT use SSML break tags.

Task context:
- Language: {task.language or "auto"}
- Style: {task.style or "neutral"}
- Emotion: {task.emotion or "neutral"}
- Use case: {task.use_case or "general"}
- Voice character: {voice.name}, {labels}
- Model: {model.value}

Audio tags reference:
- Voice-related: [laughs], [whispers], [sighs], [sarcastic], [curious], [excited], [crying]
- Pauses: [short pause], [long pause]
- Sound effects: [applause], [clapping]
- Accents: [strong French accent]

{NORMALIZATION_INSTRUCTIONS}

Return only the enhanced text.
""".strip()
