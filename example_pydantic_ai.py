#!/usr/bin/env python3
"""
Пример работы smart-tts через Pydantic AI tools (расширенный API).

Демонстрирует:
  - TemplateRegistry (кастомный slug + builtin fallback)
  - create_smart_tts_toolset(registry=...)
  - mix=None → mix_default из шаблона
  - run_synthesize_speech(..., template=) с уже resolved шаблоном
  - on_synthesized hook (post-synthesis delivery)
  - HasSmartTTS protocol (AgentDeps без SmartTTSDeps)

Требуется:
  pip install smart-tts[pydantic-ai]
  FISH_API_KEY в .env

Запуск:
  uv run python example_pydantic_ai.py
  uv run python example_pydantic_ai.py --agent
  uv run python example_pydantic_ai.py --agent --live  # агент + OpenRouter LLM
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext

from smart_tts.async_tts import AsyncSmartTTS
from smart_tts.extensions.pydantic_ai import (
    HasSmartTTS,
    PreviewSpeechTextRequest,
    SmartTTSDeps,
    SynthesizeSpeechRequest,
    SynthesizeSpeechResult,
    create_smart_tts_toolset,
    list_generation_templates,
    require_openrouter_api_key,
    resolve_openrouter_model,
    run_preview_speech_text,
    run_synthesize_speech,
)
from smart_tts.templates import (
    GenerationTemplate,
    INVESTIGATION,
    TemplateRegistry,
    TemplateRegistryInfo,
    default_template_registry,
    resolve_template,
)

OUTPUT_DIR = Path("output")

SCRIPT = """
Центр, <break time="0.6s" /> на связи резидентура. <break time="1.2s" />
Срочное донесение. <break time="1.0s" />
Обнаружена цель. <break time="0.8s" />
Конец связи.
""".strip()

AGENT_INSTRUCTIONS = """
Ты ассистент озвучивания. Для запросов пользователя:
1. Вызови list_generation_templates, если нужно выбрать шаблон.
2. Вызови preview_speech_text, чтобы проверить подготовленный текст.
3. Вызови synthesize_speech. mix можно не указывать — возьмётся mix_default шаблона.
   brief и investigation с mix=false — только речь; investigation по умолчанию с фоном.
Всегда сообщай путь к созданному MP3 и template_name из результата.
""".strip()


class ExampleTemplateRegistry:
    """Демо registry: кастомный slug + builtin/JSON chain."""

    def __init__(self) -> None:
        self._fallback = default_template_registry()

    def get(self, name: str) -> GenerationTemplate:
        if name == "brief":
            return GenerationTemplate(
                name="brief",
                language="ru",
                emotion="serious",
                enhance_text=True,
                mix_default=False,
            )
        return self._fallback.get(name)

    def list_info(self) -> list[TemplateRegistryInfo]:
        brief = self.get("brief")
        return [
            TemplateRegistryInfo(
                name="brief",
                template=brief,
                description="Короткие донесения без фона (speech-only).",
            ),
            *self._fallback.list_info(),
        ]


def make_toolset(registry: TemplateRegistry | None = None):
    return create_smart_tts_toolset(
        registry=registry or ExampleTemplateRegistry(),
        default_mix=None,
        instructions=(
            "Synthesize Russian speech with Fish Audio. "
            "Templates: investigation (noir, mix by default), brief (speech-only), default. "
            "Omit mix to use template mix_default."
        ),
    )


@dataclass
class AgentDeps:
    """Пример deps с HasSmartTTS — без наследования от SmartTTSDeps."""

    _tts: AsyncSmartTTS
    _output: Path

    @property
    def tts(self) -> AsyncSmartTTS:
        return self._tts

    @property
    def tts_output_dir(self) -> Path:
        return self._output


def _make_ctx(deps: HasSmartTTS) -> RunContext[HasSmartTTS]:
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


async def _on_synthesized(result: SynthesizeSpeechResult) -> None:
    """Post-synthesis hook: в продукте здесь S3 / Telegram / webhook."""
    print(f"  [on_synthesized] delivered: {result.path} (template={result.template_name})")


async def demo_tools(deps: SmartTTSDeps, registry: ExampleTemplateRegistry) -> Path:
    """Прямой вызов tools из toolset с кастомным registry."""
    toolset = make_toolset(registry)
    ctx = _make_ctx(deps)

    print("→ list_generation_templates (через registry)")
    for item in list_generation_templates(registry):
        print(
            f"  - {item.name}: {item.description or '—'}, "
            f"mix_default={item.mix_default}, "
            f"lang={item.language}, emotion={item.emotion}"
        )

    print("\n→ run_preview_speech_text (helper)")
    preview = await run_preview_speech_text(
        PreviewSpeechTextRequest(text=SCRIPT, template="investigation", emotion="serious"),
        registry=registry,
    )
    print(f"  prepared: {preview.prepared_text[:100]}...")

    synth_request = SynthesizeSpeechRequest(
        text=SCRIPT,
        template="brief",
        # mix не задан — возьмётся mix_default=False из шаблона brief
        emotion="serious",
        output_filename="pydantic_ai_tool_speech.mp3",
    )
    print("\n→ Tool: synthesize_speech (brief, mix из шаблона)")
    synth_fn = toolset.tools["synthesize_speech"].function
    result = await synth_fn(ctx, synth_request)
    print(f"  path: {result.path}")
    print(f"  template_name: {result.template_name}")
    print(f"  duration: {result.duration_seconds:.2f}s, mixed: {result.mixed}")
    return Path(result.path)


async def demo_tools_via_helper(
    deps: SmartTTSDeps,
    registry: ExampleTemplateRegistry,
) -> None:
    """Синтез через run_synthesize_speech с pre-resolved template и on_synthesized."""
    resolved = resolve_template("investigation", registry)
    resolved = resolved.with_overrides(name="investigation-resolved")

    request = SynthesizeSpeechRequest(
        text="Проверка связи. Конец.",
        template="ignored-slug",
        mix=False,
        output_filename="pydantic_ai_helper_speech.mp3",
    )
    print("\n→ Helper: run_synthesize_speech(template=pre-resolved, on_synthesized=...)")
    result = await run_synthesize_speech(
        deps,
        request,
        template=resolved,
        registry=registry,
    )
    print(f"  path: {result.path}, template_name: {result.template_name}")


async def demo_has_smart_tts(tts: AsyncSmartTTS, output_dir: Path, registry: ExampleTemplateRegistry) -> None:
    """Синтез через HasSmartTTS deps (AgentDeps), без SmartTTSDeps."""
    deps = AgentDeps(_tts=tts, _output=output_dir)
    request = SynthesizeSpeechRequest(
        text="Проверка HasSmartTTS protocol.",
        template="brief",
        output_filename="has_smart_tts_speech.mp3",
    )
    print("\n→ HasSmartTTS: run_synthesize_speech с AgentDeps")
    result = await run_synthesize_speech(deps, request, registry=registry)
    print(f"  path: {result.path}, mixed: {result.mixed}")


def _format_tool_content(content: object) -> str:
    if hasattr(content, "model_dump"):
        payload: object = content.model_dump()
    elif isinstance(content, list) and content and hasattr(content[0], "model_dump"):
        payload = [item.model_dump() for item in content]
    else:
        payload = content
    return json.dumps(payload, ensure_ascii=False)[:200]


async def demo_agent(
    deps: SmartTTSDeps,
    registry: ExampleTemplateRegistry,
    *,
    live: bool,
    model: str | None,
) -> None:
    """Агент с toolset, сконфигурированным через registry."""
    toolset = make_toolset(registry)

    if live:
        require_openrouter_api_key()
        resolved_model = resolve_openrouter_model(model)
        tool_names = [
            "list_generation_templates",
            "preview_speech_text",
            "synthesize_speech",
        ]
        print(f"→ Agent: OpenRouter ({resolved_model})")
        prompt = (
            "Покажи шаблоны, сделай preview текста и озвучь донесение: "
            "Срочное донесение. Обнаружена цель. "
            "Шаблон brief, файл agent_tool_speech.mp3."
        )
        agent_model: object = resolved_model
    else:
        from pydantic_ai.models.test import TestModel

        agent_model = TestModel(
            call_tools=["list_generation_templates", "preview_speech_text"],
        )
        tool_names = ["list_generation_templates", "preview_speech_text"]
        print("→ Agent: TestModel (без OpenRouter)")
        print("  synthesize_speech вызывается отдельно после агента (см. ниже)")
        prompt = (
            "Покажи доступные шаблоны и сделай preview для brief: "
            "Срочное донесение. Обнаружена цель."
        )

    agent = Agent(
        agent_model,
        deps_type=SmartTTSDeps,
        toolsets=[toolset],
        instructions=AGENT_INSTRUCTIONS,
    )

    print(f"\n→ Agent.run: {prompt[:80]}...")
    result = await agent.run(prompt, deps=deps)

    print("\n→ Tool calls:")
    for message in result.all_messages():
        for part in getattr(message, "parts", []):
            if getattr(part, "part_kind", None) != "tool-return":
                continue
            tool_name = getattr(part, "tool_name", None)
            if tool_name and tool_name in tool_names:
                content = getattr(part, "content", None)
                print(f"  {tool_name}: {_format_tool_content(content)}")

    print(f"\n→ Agent output:\n{result.output}")

    if not live:
        ctx = _make_ctx(deps)
        synth_request = SynthesizeSpeechRequest(
            text="Срочное донесение. Обнаружена цель.",
            template="brief",
            output_filename="agent_tool_speech.mp3",
        )
        print("\n→ Tool: synthesize_speech (после агента, mix из шаблона brief)")
        synth_fn = toolset.tools["synthesize_speech"].function
        synth_result = await synth_fn(ctx, synth_request)
        print(f"  path: {synth_result.path}, template_name: {synth_result.template_name}")


def parse_args() -> argparse.Namespace:
    load_dotenv()
    parser = argparse.ArgumentParser(description="smart-tts Pydantic AI tools example")
    parser.add_argument(
        "--agent",
        action="store_true",
        help="Запустить Pydantic AI агента (по умолчанию — прямой вызов tools).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Использовать OpenRouter LLM вместо TestModel (нужен OPENROUTER_API_KEY).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="OpenRouter model id, например google/gemini-2.5-flash (или openrouter:...).",
    )
    parser.add_argument("-o", "--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    registry = ExampleTemplateRegistry()

    async with AsyncSmartTTS.from_env() as tts:
        deps = SmartTTSDeps(
            tts=tts,
            output_dir=args.output_dir,
            on_synthesized=_on_synthesized,
        )

        if args.agent:
            await demo_agent(deps, registry, live=args.live, model=args.model)
        else:
            path = await demo_tools(deps, registry)
            await demo_tools_via_helper(deps, registry)
            await demo_has_smart_tts(tts, args.output_dir, registry)
            print(f"\nГотово! Основной файл: {path.resolve()}")
            print(f"  investigation mix_default={INVESTIGATION.mix_default}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except Exception as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
