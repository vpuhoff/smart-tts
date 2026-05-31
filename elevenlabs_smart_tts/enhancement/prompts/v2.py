from __future__ import annotations

from elevenlabs_smart_tts.enhancement.prompts.base import NORMALIZATION_INSTRUCTIONS
from elevenlabs_smart_tts.models import CachedVoice, SynthesisTask, TTSModel


def build_v2_system_prompt(task: SynthesisTask, voice: CachedVoice, model: TTSModel) -> str:
    labels = ", ".join(f"{key}={value}" for key, value in voice.labels.items())
    return f"""
You enhance text for ElevenLabs text-to-speech model {model.value}.

Core directives:
- Add narrative context and natural pacing.
- You may use SSML pause tags such as <break time="0.5s" /> where helpful.
- You may use alias-style pronunciation hints when needed.
- DO NOT change, remove, or reorder the original words.

Task context:
- Language: {task.language or "auto"}
- Style: {task.style or "neutral"}
- Emotion: {task.emotion or "neutral"}
- Use case: {task.use_case or "general"}
- Voice character: {voice.name}, {labels}
- Model: {model.value}

{NORMALIZATION_INSTRUCTIONS}

Return only the enhanced text.
""".strip()
