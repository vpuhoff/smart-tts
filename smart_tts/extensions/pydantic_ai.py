"""Pydantic AI tools for smart-tts synthesis.

Install the optional dependency::

    pip install smart-tts[pydantic-ai]

Example::

    from pathlib import Path

    from pydantic_ai import Agent

    from smart_tts.async_tts import AsyncSmartTTS
    from smart_tts.extensions.pydantic_ai import (
        SmartTTSDeps,
        create_smart_tts_toolset,
    )

    async def main() -> None:
        async with AsyncSmartTTS.from_env() as tts:
            deps = SmartTTSDeps(tts=tts, output_dir=Path("output"))
            agent = Agent(
                "openai:gpt-4o-mini",
                deps_type=SmartTTSDeps,
                toolsets=[create_smart_tts_toolset()],
            )
            result = await agent.run(
                "Озвучь: Срочное донесение. Обнаружена цель.",
                deps=deps,
            )
            print(result.output)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

try:
    from pydantic_ai import FunctionToolset, RunContext
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError(
        "smart-tts pydantic-ai extension requires pydantic-ai. "
        "Install with: pip install smart-tts[pydantic-ai]"
    ) from exc

from smart_tts.async_tts import AsyncSmartTTS
from smart_tts.audio.probe import audio_duration_seconds
from smart_tts.config import SmartTTSConfig
from smart_tts.templates import BUILTIN_TEMPLATES, GenerationTemplate, get_template
from smart_tts.text import prepare_text

__all__ = [
    "SmartTTSDeps",
    "SynthesizeSpeechRequest",
    "SynthesizeSpeechResult",
    "TemplateInfo",
    "create_smart_tts_toolset",
    "run_synthesize_speech",
]


@dataclass
class SmartTTSDeps:
    """Agent dependencies for smart-tts tools."""

    tts: AsyncSmartTTS
    output_dir: Path = field(default_factory=lambda: Path("output"))

    @classmethod
    def from_env(
        cls,
        *,
        output_dir: str | Path = "output",
        config: SmartTTSConfig | None = None,
    ) -> SmartTTSDeps:
        tts = AsyncSmartTTS(config or SmartTTSConfig.from_env())
        return cls(tts=tts, output_dir=Path(output_dir))


class SynthesizeSpeechRequest(BaseModel):
    """Input for speech synthesis."""

    text: str = Field(
        description=(
            "Script to synthesize. SSML breaks like "
            '<break time="1.0s"/> are converted to Fish pause tags when enhance_text is enabled.'
        ),
    )
    template: str = Field(
        default="investigation",
        description="Built-in template name (investigation, default) or path to a JSON template file.",
    )
    mix: bool = Field(
        default=True,
        description="Whether to mix speech with music/ambient beds from the template.",
    )
    emotion: str | None = Field(
        default=None,
        description="Optional emotion override (warm, serious, excited, sad, whisper, calm).",
    )
    output_filename: str | None = Field(
        default=None,
        description="Optional output file name. Defaults to <template>_<timestamp>.mp3.",
    )


class SynthesizeSpeechResult(BaseModel):
    """Synthesis result returned to the agent."""

    path: str
    duration_seconds: float
    enhanced_text: str
    model: str
    voice_id: str
    mixed: bool
    metadata: dict[str, Any]


class TemplateInfo(BaseModel):
    """Summary of a built-in generation template."""

    name: str
    language: str | None = None
    emotion: str | None = None
    has_music: bool
    has_ambient: bool


def _resolve_template(name_or_path: str) -> GenerationTemplate:
    path = Path(name_or_path)
    if path.suffix == ".json" and path.exists():
        return GenerationTemplate.from_json_file(path)
    return get_template(name_or_path)


def _output_path(deps: SmartTTSDeps, template_name: str, filename: str | None) -> Path:
    deps.output_dir.mkdir(parents=True, exist_ok=True)
    if filename:
        name = filename if filename.endswith(".mp3") else f"{filename}.mp3"
        return deps.output_dir / name
    slug = re.sub(r"[^\w\-]+", "_", template_name).strip("_") or "speech"
    return deps.output_dir / f"{slug}_{int(time.time())}.mp3"


async def run_synthesize_speech(
    deps: SmartTTSDeps,
    request: SynthesizeSpeechRequest,
) -> SynthesizeSpeechResult:
    template = _resolve_template(request.template)
    overrides: dict[str, Any] = {}
    if request.emotion is not None:
        overrides["emotion"] = request.emotion

    output_path = _output_path(deps, template.name, request.output_filename)
    result = await deps.tts.synthesize_text_to_file(
        request.text,
        template,
        output_path,
        mix=request.mix,
        **overrides,
    )
    duration_ms = result.metadata.get("duration_ms")
    if isinstance(duration_ms, (int, float)):
        duration = max(duration_ms / 1000.0, 0.0)
    else:
        duration = audio_duration_seconds(output_path)

    return SynthesizeSpeechResult(
        path=str(output_path.resolve()),
        duration_seconds=duration,
        enhanced_text=result.enhanced_text,
        model=result.model.value,
        voice_id=result.voice.voice_id,
        mixed=bool(result.metadata.get("mixed")),
        metadata=result.metadata,
    )


def create_smart_tts_toolset() -> FunctionToolset[SmartTTSDeps]:
    """Build a FunctionToolset with smart-tts synthesis tools."""
    toolset: FunctionToolset[SmartTTSDeps] = FunctionToolset(
        id="smart_tts",
        instructions=(
            "Use these tools to synthesize Russian speech with Fish Audio. "
            "Prefer template 'investigation' for noir detective narration. "
            "Set mix=false for speech-only output."
        ),
    )

    @toolset.tool
    async def synthesize_speech(
        ctx: RunContext[SmartTTSDeps],
        request: SynthesizeSpeechRequest,
    ) -> SynthesizeSpeechResult:
        """Synthesize speech from text using a generation template."""
        return await run_synthesize_speech(ctx.deps, request)

    @toolset.tool_plain
    def list_generation_templates() -> list[TemplateInfo]:
        """List built-in generation templates and their capabilities."""
        items: list[TemplateInfo] = []
        for name, template in sorted(BUILTIN_TEMPLATES.items()):
            items.append(
                TemplateInfo(
                    name=name,
                    language=template.language,
                    emotion=template.emotion,
                    has_music=bool(template.music_prompt or template.music_path),
                    has_ambient=bool(template.ambient_prompt or template.ambient_path),
                )
            )
        return items

    @toolset.tool
    async def preview_speech_text(
        ctx: RunContext[SmartTTSDeps],
        text: str,
        template: str = "investigation",
        emotion: str | None = None,
    ) -> str:
        """Preview prepared Fish Audio text without calling TTS."""
        tpl = _resolve_template(template)
        overrides: dict[str, Any] = {}
        if emotion is not None:
            overrides["emotion"] = emotion
        task = tpl.to_task(text, mix=False, **overrides)
        return prepare_text(task) if task.enhance_text else task.text.strip()

    return toolset
