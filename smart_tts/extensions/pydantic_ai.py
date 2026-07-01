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

import asyncio
import inspect
import os
import re
import time
import warnings
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, Literal, Protocol, TypeVar, cast

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
from smart_tts.exceptions import SynthesisTimeoutError
from smart_tts.templates import (
    GenerationTemplate,
    TemplateRegistry,
    TemplateRegistryInfo,
    default_template_registry,
    resolve_request_template,
    resolve_template,
)
from smart_tts.telemetry import async_span
from smart_tts.text import prepare_text

__all__ = [
    "BuiltinTemplateName",
    "EmotionTag",
    "HasSmartTTS",
    "LegacyOnSynthesizedCallback",
    "OnSynthesizedCallback",
    "PreviewSpeechTextRequest",
    "PreviewSpeechTextResult",
    "SmartTTSDeps",
    "SynthesisMetadata",
    "SynthesizeSpeechRequest",
    "SynthesizeSpeechResult",
    "TemplateInfo",
    "create_smart_tts_toolset",
    "list_generation_templates",
    "make_run_context",
    "require_openrouter_api_key",
    "resolve_openrouter_model",
    "run_preview_speech_text",
    "run_synthesize_speech",
]

DEFAULT_OPENROUTER_MODEL = "google/gemini-2.5-flash"
DEFAULT_TOOLSET_INSTRUCTIONS = (
    "Use these tools to synthesize Russian speech with Fish Audio. "
    "Prefer template 'investigation' for noir detective narration. "
    "Omit mix to use each template's default; set mix=false for speech-only output."
)
SYNTHESIS_TIMEOUT_ENV = "SMART_TTS_SYNTHESIS_TIMEOUT_SEC"
_LEGACY_ON_SYNTHESIZED_WARNED = False

BuiltinTemplateName = Literal["investigation", "default"]
EmotionTag = Literal["warm", "serious", "excited", "sad", "whisper", "calm"]

DepsT = TypeVar("DepsT")


class HasSmartTTS(Protocol):
    """Structural protocol for agent deps with smart-tts runtime."""

    @property
    def tts(self) -> AsyncSmartTTS: ...

    @property
    def tts_output_dir(self) -> Path: ...


OnSynthesizedCallback = Callable[
    [RunContext[HasSmartTTS], "SynthesizeSpeechResult"],
    Awaitable[Any],
]
LegacyOnSynthesizedCallback = Callable[
    ["SynthesizeSpeechResult"],
    Awaitable[Any],
]


@dataclass
class _MinimalRunContext(Generic[DepsT]):
    """Minimal RunContext stand-in for run_synthesize_speech outside Agent.iter."""

    deps: DepsT


def make_run_context(deps: HasSmartTTS) -> RunContext[HasSmartTTS]:
    """Build a minimal RunContext for run_synthesize_speech outside Agent.iter."""
    return cast(RunContext[HasSmartTTS], _MinimalRunContext(deps=deps))


@dataclass
class SmartTTSDeps:
    """Agent dependencies for smart-tts tools."""

    tts: AsyncSmartTTS
    output_dir: Path = field(default_factory=lambda: Path("output"))
    on_synthesized: OnSynthesizedCallback | LegacyOnSynthesizedCallback | None = None

    @property
    def tts_output_dir(self) -> Path:
        return self.output_dir

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
    template: str | None = Field(
        default=None,
        description=(
            "Template slug. Omit to use registry default, then 'investigation' fallback."
        ),
    )
    mix: bool | None = Field(
        default=None,
        description=(
            "Whether to mix speech with music/ambient beds. "
            "When omitted, uses the template mix_default."
        ),
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
    template_name: str = Field(
        description="Resolved generation template name used for synthesis.",
        min_length=1,
    )
    metadata: SynthesisMetadata = Field(
        description="Technical synthesis metadata from the smart-tts pipeline.",
    )


class TemplateInfo(BaseModel):
    """Summary of a generation template."""

    name: str = Field(
        description="Template identifier passed to synthesize_speech.",
        min_length=1,
    )
    slug: str | None = Field(
        default=None,
        description="Template slug alias; defaults to name when omitted.",
    )
    description: str | None = Field(
        default=None,
        description="Human-readable template description for admins and LLM selection.",
    )
    mix_default: bool = Field(
        default=False,
        description="Default mix flag when synthesize_speech omits mix.",
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
    is_default: bool = Field(
        default=False,
        description="Whether this template is the registry default when template is omitted.",
    )


class PreviewSpeechTextRequest(BaseModel):
    """Input for previewing prepared Fish Audio text without calling TTS."""

    text: str = Field(
        description=(
            "Source script. SSML breaks are converted to Fish pause tags when enhance_text is enabled."
        ),
        min_length=1,
    )
    template: str | None = Field(
        default=None,
        description=(
            "Template slug. Omit to use registry default, then builtin fallback."
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


def _template_info_from_registry(entry: TemplateRegistryInfo) -> TemplateInfo:
    template = entry.template
    return TemplateInfo(
        name=entry.name,
        slug=entry.name,
        description=entry.description,
        mix_default=template.mix_default,
        language=template.language,
        emotion=template.emotion,
        has_music=bool(template.music_prompt or template.music_path),
        has_ambient=bool(template.ambient_prompt or template.ambient_path),
        is_default=entry.is_default,
    )


def _resolve_mix(
    request_mix: bool | None,
    template: GenerationTemplate,
    factory_default_mix: bool | None,
) -> bool:
    if request_mix is not None:
        return request_mix
    if factory_default_mix is not None:
        return factory_default_mix
    return template.mix_default


def _output_path(deps: HasSmartTTS, template_name: str, filename: str | None) -> Path:
    deps.tts_output_dir.mkdir(parents=True, exist_ok=True)
    if filename:
        name = filename if filename.endswith(".mp3") else f"{filename}.mp3"
        return deps.tts_output_dir / name
    slug = re.sub(r"[^\w\-]+", "_", template_name).strip("_") or "speech"
    return deps.tts_output_dir / f"{slug}_{int(time.time())}.mp3"


def _accepts_run_context(callback: Callable[..., Awaitable[Any]]) -> bool:
    try:
        signature = inspect.signature(callback)
    except (TypeError, ValueError):
        return False
    params = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind
        not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    ]
    if params and params[0].name == "self":
        params = params[1:]
    return len(params) >= 2


def _warn_legacy_on_synthesized() -> None:
    global _LEGACY_ON_SYNTHESIZED_WARNED
    if _LEGACY_ON_SYNTHESIZED_WARNED:
        return
    _LEGACY_ON_SYNTHESIZED_WARNED = True
    warnings.warn(
        "on_synthesized(result) is deprecated; use on_synthesized(ctx, result) instead.",
        DeprecationWarning,
        stacklevel=3,
    )


async def _call_on_synthesized(
    ctx: RunContext[HasSmartTTS] | None,
    deps: HasSmartTTS,
    result: SynthesizeSpeechResult,
) -> None:
    callback = getattr(deps, "on_synthesized", None)
    if callback is None:
        return

    async with async_span("smart_tts.on_synthesized", template=result.template_name):
        if ctx is not None and _accepts_run_context(callback):
            await callback(ctx, result)
        elif _accepts_run_context(callback):
            return
        else:
            _warn_legacy_on_synthesized()
            await callback(result)


def _resolve_timeout_sec(explicit: float | None) -> float | None:
    if explicit is not None:
        if explicit <= 0:
            raise ValueError("timeout_sec must be positive")
        return explicit

    env_value = os.getenv(SYNTHESIS_TIMEOUT_ENV, "").strip()
    if not env_value:
        return None
    parsed = float(env_value)
    if parsed <= 0:
        raise ValueError(f"{SYNTHESIS_TIMEOUT_ENV} must be positive")
    return parsed


def list_generation_templates_from_registry(
    registry: TemplateRegistry | None = None,
) -> list[TemplateInfo]:
    """List generation templates from *registry* (built-in chain by default)."""
    active = registry or default_template_registry()
    return [_template_info_from_registry(entry) for entry in active.list_info()]


def list_generation_templates(
    registry: TemplateRegistry | None = None,
) -> list[TemplateInfo]:
    """Alias for :func:`list_generation_templates_from_registry`."""
    return list_generation_templates_from_registry(registry)


async def _core_synthesize_speech(
    deps: HasSmartTTS,
    request: SynthesizeSpeechRequest,
    *,
    resolved: GenerationTemplate,
    mix: bool,
) -> SynthesizeSpeechResult:
    overrides: dict[str, Any] = {}
    if request.emotion is not None:
        overrides["emotion"] = request.emotion

    output_path = _output_path(deps, resolved.name, request.output_filename)
    result = await deps.tts.synthesize_text_to_file(
        request.text,
        resolved,
        output_path,
        mix=mix,
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
        template_name=resolved.name,
        metadata=SynthesisMetadata.model_validate(result.metadata),
    )


async def run_synthesize_speech(
    deps: HasSmartTTS,
    request: SynthesizeSpeechRequest,
    *,
    template: GenerationTemplate | None = None,
    registry: TemplateRegistry | None = None,
    default_mix: bool | None = None,
    ctx: RunContext[HasSmartTTS] | None = None,
    timeout_sec: float | None = None,
) -> SynthesizeSpeechResult:
    if template is not None:
        resolved = template
    else:
        _, resolved = resolve_request_template(request.template, registry)
    mix = _resolve_mix(request.mix, resolved, default_mix)
    timeout = _resolve_timeout_sec(timeout_sec)

    async with async_span(
        "smart_tts.tool.synthesize_speech",
        template=resolved.name,
        mix=mix,
        char_count=len(request.text),
    ) as span:
        try:
            if timeout is not None:
                speech_result = await asyncio.wait_for(
                    _core_synthesize_speech(
                        deps,
                        request,
                        resolved=resolved,
                        mix=mix,
                    ),
                    timeout=timeout,
                )
            else:
                speech_result = await _core_synthesize_speech(
                    deps,
                    request,
                    resolved=resolved,
                    mix=mix,
                )
        except asyncio.TimeoutError as exc:
            span.set_attribute("smart_tts.timeout_sec", timeout)
            span.record_exception(exc)
            raise SynthesisTimeoutError(timeout, stage="synthesis") from exc

        await _call_on_synthesized(ctx, deps, speech_result)
        return speech_result


async def run_preview_speech_text(
    request: PreviewSpeechTextRequest,
    *,
    template: GenerationTemplate | None = None,
    registry: TemplateRegistry | None = None,
) -> PreviewSpeechTextResult:
    if template is not None:
        resolved = template
    else:
        _, resolved = resolve_request_template(request.template, registry)
    overrides: dict[str, Any] = {}
    if request.emotion is not None:
        overrides["emotion"] = request.emotion
    task = resolved.to_task(request.text, mix=False, **overrides)
    prepared = prepare_text(task) if task.enhance_text else task.text.strip()
    return PreviewSpeechTextResult(
        prepared_text=prepared,
        template=resolved.name,
        enhance_text=task.enhance_text,
    )


def create_smart_tts_toolset(
    *,
    registry: TemplateRegistry | None = None,
    default_mix: bool | None = None,
    instructions: str | None = None,
    include_preview: bool = True,
    include_list: bool = True,
) -> FunctionToolset[HasSmartTTS]:
    """Build a FunctionToolset with smart-tts synthesis tools."""
    active_registry = registry or default_template_registry()
    toolset: FunctionToolset[HasSmartTTS] = FunctionToolset(
        id="smart_tts",
        instructions=instructions or DEFAULT_TOOLSET_INSTRUCTIONS,
    )

    @toolset.tool
    async def synthesize_speech(
        ctx: RunContext[HasSmartTTS],
        request: SynthesizeSpeechRequest,
    ) -> SynthesizeSpeechResult:
        """Synthesize speech from text using a generation template."""
        return await run_synthesize_speech(
            ctx.deps,
            request,
            registry=active_registry,
            default_mix=default_mix,
            ctx=ctx,
        )

    if include_list:

        @toolset.tool_plain
        def list_generation_templates() -> list[TemplateInfo]:
            """List generation templates and their capabilities."""
            return list_generation_templates_from_registry(active_registry)

    if include_preview:

        @toolset.tool
        async def preview_speech_text(
            ctx: RunContext[HasSmartTTS],
            request: PreviewSpeechTextRequest,
        ) -> PreviewSpeechTextResult:
            """Preview prepared Fish Audio text without calling TTS."""
            return await run_preview_speech_text(request, registry=active_registry)

    return toolset
