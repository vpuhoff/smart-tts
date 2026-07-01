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
        resolve_openrouter_model,
    )

    async def main() -> None:
        async with AsyncSmartTTS.from_env() as tts:
            deps = SmartTTSDeps(tts=tts, output_dir=Path("output"))
            agent = Agent(
                resolve_openrouter_model(),
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

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

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
from smart_tts.telemetry import async_span
from smart_tts.text import prepare_text

__all__ = [
    "BuiltinTemplateName",
    "EmotionTag",
    "PreviewSpeechTextRequest",
    "PreviewSpeechTextResult",
    "SmartTTSDeps",
    "SynthesisMetadata",
    "SynthesizeSpeechRequest",
    "SynthesizeSpeechResult",
    "TemplateInfo",
    "create_smart_tts_toolset",
    "require_openrouter_api_key",
    "resolve_openrouter_model",
    "run_synthesize_speech",
]

DEFAULT_OPENROUTER_MODEL = "google/gemini-2.5-flash"

BuiltinTemplateName = Literal["investigation", "default"]
EmotionTag = Literal["warm", "serious", "excited", "sad", "whisper", "calm"]


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


def resolve_openrouter_model(model: str | None = None) -> str:
    """Build a Pydantic AI model id for OpenRouter.

    Reads, in order: explicit ``model``, ``PYDANTIC_AI_MODEL``,
    ``OPENROUTER_API_TTS_PROMPT_MODEL``, ``OPENROUTER_MODEL``.
    Adds the ``openrouter:`` prefix when missing.
  """
    chosen = (
        model
        or os.getenv("PYDANTIC_AI_MODEL")
        or os.getenv("OPENROUTER_API_TTS_PROMPT_MODEL")
        or os.getenv("OPENROUTER_MODEL")
        or DEFAULT_OPENROUTER_MODEL
    ).strip()
    if ":" in chosen:
        return chosen
    return f"openrouter:{chosen}"


def require_openrouter_api_key() -> str:
    """Return ``OPENROUTER_API_KEY`` or raise if it is missing."""
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Missing OPENROUTER_API_KEY environment variable.")
    return api_key


class SynthesizeSpeechRequest(BaseModel):
    """Input for speech synthesis via a generation template."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "text": 'Срочное донесение. <break time="1.2s" /> Обнаружена цель.',
                    "template": "investigation",
                    "mix": True,
                    "emotion": "serious",
                }
            ]
        }
    )

    text: str = Field(
        description=(
            "Script to synthesize. SSML breaks like "
            '<break time="1.0s"/> are converted to Fish pause tags when enhance_text is enabled.'
        ),
        min_length=1,
    )
    template: str = Field(
        default="investigation",
        description=(
            "Generation template: built-in name (investigation, default) "
            "or path to a JSON template file."
        ),
    )
    mix: bool = Field(
        default=True,
        description="Whether to mix speech with music/ambient beds from the template.",
    )
    emotion: EmotionTag | None = Field(
        default=None,
        description="Optional emotion delivery tag override for Fish Audio.",
    )
    output_filename: str | None = Field(
        default=None,
        description="Optional output file name. Defaults to <template>_<timestamp>.mp3.",
    )


class SynthesisMetadata(BaseModel):
    """Technical metadata from the synthesis pipeline."""

    duration_ms: int = Field(
        description="Total synthesis time in milliseconds, including mixing when enabled.",
        ge=0,
    )
    char_count: int = Field(
        description="Length of the prepared text sent to Fish Audio.",
        ge=0,
    )
    voice_id: str = Field(
        description="Fish Audio reference_id used for synthesis.",
        min_length=1,
    )
    model: str = Field(
        description="Requested TTS model identifier.",
        min_length=1,
    )
    fish_model: str = Field(
        description="Actual Fish Audio model used (may differ after credit fallback).",
        min_length=1,
    )
    mixed: bool = Field(
        description="Whether music or ambient beds were mixed into the output.",
    )
    music: bool = Field(
        description="Whether a music bed was included in the final mix.",
    )
    ambient: bool = Field(
        description="Whether an ambient bed was included in the final mix.",
    )


class SynthesizeSpeechResult(BaseModel):
    """Synthesis result returned to the agent after audio is saved to disk."""

    path: str = Field(
        description="Absolute path to the generated MP3 file.",
        min_length=1,
    )
    duration_seconds: float = Field(
        description="Audio duration in seconds.",
        ge=0,
    )
    enhanced_text: str = Field(
        description="Prepared Fish Audio script after break conversion and emotion tags.",
    )
    model: str = Field(
        description="Requested TTS model identifier.",
        min_length=1,
    )
    voice_id: str = Field(
        description="Fish Audio reference_id used for synthesis.",
        min_length=1,
    )
    mixed: bool = Field(
        description="Whether the output includes mixed music/ambient beds.",
    )
    metadata: SynthesisMetadata = Field(
        description="Technical synthesis metadata from the smart-tts pipeline.",
    )


class TemplateInfo(BaseModel):
    """Summary of a built-in generation template."""

    name: str = Field(
        description="Template identifier passed to synthesize_speech.",
        min_length=1,
    )
    language: str | None = Field(
        default=None,
        description="Default language hint for the template, if configured.",
    )
    emotion: str | None = Field(
        default=None,
        description="Default Fish Audio emotion tag for the template, if configured.",
    )
    has_music: bool = Field(
        description="Whether the template defines a music prompt or music file path.",
    )
    has_ambient: bool = Field(
        description="Whether the template defines an ambient prompt or ambient file path.",
    )


class PreviewSpeechTextRequest(BaseModel):
    """Input for previewing prepared Fish Audio text without calling TTS."""

    text: str = Field(
        description=(
            "Source script. SSML breaks are converted to Fish pause tags when enhance_text is enabled."
        ),
        min_length=1,
    )
    template: str = Field(
        default="investigation",
        description=(
            "Generation template: built-in name (investigation, default) "
            "or path to a JSON template file."
        ),
    )
    emotion: EmotionTag | None = Field(
        default=None,
        description="Optional emotion delivery tag override for the preview.",
    )


class PreviewSpeechTextResult(BaseModel):
    """Prepared Fish Audio script returned by preview_speech_text."""

    prepared_text: str = Field(
        description="Text after SSML break conversion and optional emotion prefix.",
    )
    template: str = Field(
        description="Template name or path used for preparation.",
        min_length=1,
    )
    enhance_text: bool = Field(
        description="Whether text enhancement was applied for this template.",
    )


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
    async with async_span(
        "smart_tts.tool.synthesize_speech",
        template=request.template,
        mix=request.mix,
        char_count=len(request.text),
    ):
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
            metadata=SynthesisMetadata.model_validate(result.metadata),
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
        request: PreviewSpeechTextRequest,
    ) -> PreviewSpeechTextResult:
        """Preview prepared Fish Audio text without calling TTS."""
        tpl = _resolve_template(request.template)
        overrides: dict[str, Any] = {}
        if request.emotion is not None:
            overrides["emotion"] = request.emotion
        task = tpl.to_task(request.text, mix=False, **overrides)
        prepared = prepare_text(task) if task.enhance_text else task.text.strip()
        return PreviewSpeechTextResult(
            prepared_text=prepared,
            template=request.template,
            enhance_text=task.enhance_text,
        )

    return toolset
