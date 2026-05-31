from __future__ import annotations

from elevenlabs_smart_tts.enhancement.prompts.base import NORMALIZATION_INSTRUCTIONS
from elevenlabs_smart_tts.enhancement.prompts.v2 import build_v2_system_prompt
from elevenlabs_smart_tts.enhancement.prompts.v3 import build_v3_system_prompt
from elevenlabs_smart_tts.models import CachedVoice, SynthesisTask, TTSModel


class PromptBuilder:
    def build(self, task: SynthesisTask, voice: CachedVoice, model: TTSModel) -> str:
        if model == TTSModel.ELEVEN_V3:
            return build_v3_system_prompt(task, voice, model)
        if model in {TTSModel.ELEVEN_MULTILINGUAL_V2, TTSModel.ELEVEN_FLASH_V2_5}:
            if model == TTSModel.ELEVEN_FLASH_V2_5:
                return self._build_flash_prompt(task, voice, model)
            return build_v2_system_prompt(task, voice, model)
        return build_v3_system_prompt(task, voice, model)

    @staticmethod
    def _build_flash_prompt(task: SynthesisTask, voice: CachedVoice, model: TTSModel) -> str:
        labels = ", ".join(f"{key}={value}" for key, value in voice.labels.items())
        return f"""
You enhance text for low-latency ElevenLabs model {model.value}.

Core directives:
- Keep markup minimal.
- Aggressively normalize numbers, dates, times, currency, phone numbers, and URLs into spoken form.
- DO NOT change, remove, or reorder the original words.

Task context:
- Language: {task.language or "auto"}
- Style: {task.style or "neutral"}
- Emotion: {task.emotion or "neutral"}
- Use case: {task.use_case or "general"}
- Voice character: {voice.name}, {labels}

{NORMALIZATION_INSTRUCTIONS}

Return only the enhanced text.
""".strip()
