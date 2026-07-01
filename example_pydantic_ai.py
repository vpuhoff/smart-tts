#!/usr/bin/env python3
"""
Пример работы smart-tts через Pydantic AI tools.

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
from pathlib import Path
from unittest.mock import MagicMock

from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext

from smart_tts.async_tts import AsyncSmartTTS
from smart_tts.extensions.pydantic_ai import (
    PreviewSpeechTextRequest,
    SmartTTSDeps,
    SynthesizeSpeechRequest,
    create_smart_tts_toolset,
    require_openrouter_api_key,
    resolve_openrouter_model,
    run_synthesize_speech,
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
3. Вызови synthesize_speech с mix=false для речи без фона, если пользователь просит озвучить.
Всегда сообщай путь к созданному MP3.
""".strip()


def _make_ctx(deps: SmartTTSDeps) -> RunContext[SmartTTSDeps]:
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


async def demo_tools(deps: SmartTTSDeps) -> Path:
    """Прямой вызов tools из toolset с Pydantic-схемами."""
    toolset = create_smart_tts_toolset()
    ctx = _make_ctx(deps)

    print("→ Tool: list_generation_templates")
    templates = toolset.tools["list_generation_templates"].function()
    for item in templates:
        print(
            f"  - {item.name}: lang={item.language}, emotion={item.emotion}, "
            f"music={item.has_music}, ambient={item.has_ambient}"
        )

    preview_request = PreviewSpeechTextRequest(
        text=SCRIPT,
        template="investigation",
        emotion="serious",
    )
    print("\n→ Tool: preview_speech_text")
    preview_fn = toolset.tools["preview_speech_text"].function
    preview = await preview_fn(ctx, preview_request)
    print(f"  prepared: {preview.prepared_text[:100]}...")

    synth_request = SynthesizeSpeechRequest(
        text=SCRIPT,
        template="investigation",
        mix=False,
        emotion="serious",
        output_filename="pydantic_ai_tool_speech.mp3",
    )
    print("\n→ Tool: synthesize_speech")
    synth_fn = toolset.tools["synthesize_speech"].function
    result = await synth_fn(ctx, synth_request)
    print(f"  path: {result.path}")
    print(f"  duration: {result.duration_seconds:.2f}s")
    print(f"  model: {result.model} ({result.metadata.fish_model})")
    return Path(result.path)


async def demo_tools_via_helper(deps: SmartTTSDeps) -> None:
    """Тот же синтез через run_synthesize_speech без обёртки tool."""
    request = SynthesizeSpeechRequest(
        text="Проверка связи. Конец.",
        template="investigation",
        mix=False,
        output_filename="pydantic_ai_helper_speech.mp3",
    )
    print("\n→ Helper: run_synthesize_speech()")
    result = await run_synthesize_speech(deps, request)
    print(f"  path: {result.path}")


def _format_tool_content(content: object) -> str:
    if hasattr(content, "model_dump"):
        payload: object = content.model_dump()
    elif isinstance(content, list) and content and hasattr(content[0], "model_dump"):
        payload = [item.model_dump() for item in content]
    else:
        payload = content
    return json.dumps(payload, ensure_ascii=False)[:200]


async def demo_agent(deps: SmartTTSDeps, *, live: bool, model: str | None) -> None:
    """Агент сам выбирает и вызывает tools."""
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
            "Шаблон investigation, mix=false, файл agent_tool_speech.mp3."
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
            "Покажи доступные шаблоны и сделай preview для investigation: "
            "Срочное донесение. Обнаружена цель."
        )

    agent = Agent(
        agent_model,
        deps_type=SmartTTSDeps,
        toolsets=[create_smart_tts_toolset()],
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
            template="investigation",
            mix=False,
            output_filename="agent_tool_speech.mp3",
        )
        print("\n→ Tool: synthesize_speech (после агента, mix=false)")
        synth_fn = create_smart_tts_toolset().tools["synthesize_speech"].function
        synth_result = await synth_fn(ctx, synth_request)
        print(f"  path: {synth_result.path}")


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

    async with AsyncSmartTTS.from_env() as tts:
        deps = SmartTTSDeps(tts=tts, output_dir=args.output_dir)

        if args.agent:
            await demo_agent(deps, live=args.live, model=args.model)
        else:
            path = await demo_tools(deps)
            await demo_tools_via_helper(deps)
            print(f"\nГотово! Основной файл: {path.resolve()}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except Exception as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
