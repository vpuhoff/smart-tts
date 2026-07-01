#!/usr/bin/env python3
"""
«Следствие ведут…» — радиодонесение в духе криминального детектива.

Голос: Fish Audio S2.1 Pro через smart_tts.
Фон: музыка и эмбиент — ElevenLabs, сведение — ffmpeg.

Запуск:
  uv run python example.py
  uv run python example.py --variants 2
  uv run python example.py --remix-only --music back.mp3
  uv run python example.py --remix-only --music back.mp3 --no-ambient
  uv run python example.py --remix-only --music back.mp3 -mv 0.15 -sv 1.3
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from smart_tts import INVESTIGATION, GenerationTemplate, SmartTTS, VoiceSettings
from smart_tts.audio import audio_duration_seconds, require_tool
from smart_tts.config import SmartTTSConfig
from smart_tts.models import TTSModel

OUTPUT_DIR = Path("output")

VOICES = {
    "kanevsky": "67d37d81cb7340b391e9461d6671de03",
}
DEFAULT_VOICE = "kanevsky"

RAW_SCRIPT = """
Центр, <break time="0.6s" /> на связи резидентура. <break time="1.2s" />
Срочное донесение. <break time="1.0s" />
Обнаружена цель. <break time="0.8s" />
Объект Каспа, <break time="0.4s" /> тикер КАС. <break time="1.2s" />
Зрелая фаза накопления, <break time="0.5s" /> многомесячное сжатие на минимумах. <break time="1.2s" />
На календаре хардфорк в июне, <break time="0.5s" /> катализатор подтвержден. <break time="1.5s" />
Полные разведданные по объекту <break time="0.3s" /> уже направлены в центр. <break time="1.2s" />
Следующей передачей высылаю детальную сводку: <break time="0.8s" /> рубежи, <break time="0.5s" /> вектор, <break time="0.5s" /> перспективы цели. <break time="1.5s" />
Резидентура ведет. <break time="1.0s" />
Конец связи.
""".strip()

MODEL_BY_NAME: dict[str, TTSModel] = {
    "s2.1-pro": TTSModel.ELEVEN_V3,
    "s2.1-pro-free": TTSModel.S2_1_PRO_FREE,
    "s2-pro": TTSModel.ELEVEN_MULTILINGUAL_V2,
    "s1": TTSModel.ELEVEN_FLASH_V2_5,
}


def template_from_args(args: argparse.Namespace) -> GenerationTemplate:
    ambient_prompt = None if args.no_ambient else INVESTIGATION.ambient_prompt
    return INVESTIGATION.with_overrides(
        voice_id=VOICES[args.voice],
        model=MODEL_BY_NAME[args.model],
        music_path=args.music,
        ambient_path=args.ambient_file,
        ambient_prompt=ambient_prompt,
        music_volume=args.music_volume,
        ambient_volume=args.ambient_volume,
        speech_volume=args.speech_volume,
        bed_weight=args.bed_weight,
    )


def parse_args() -> argparse.Namespace:
    load_dotenv()
    p = argparse.ArgumentParser()
    p.add_argument("-o", "--output-dir", type=Path, default=OUTPUT_DIR)
    p.add_argument("--remix-only", action="store_true")
    p.add_argument("--voice", choices=list(VOICES), default=DEFAULT_VOICE)
    p.add_argument("--variants", type=int, default=1)
    p.add_argument("--music", type=Path, default=None, metavar="FILE")
    p.add_argument("--ambient-file", type=Path, default=None, metavar="FILE")
    p.add_argument("--no-ambient", action="store_true")
    p.add_argument(
        "--music-volume",
        "-mv",
        type=float,
        default=float(os.getenv("MUSIC_VOLUME", "0.32")),
    )
    p.add_argument("--ambient-volume", type=float, default=0.18)
    p.add_argument("--speech-volume", "-sv", type=float, default=1.0)
    p.add_argument("--bed-weight", type=float, default=0.68)
    p.add_argument("--model", default="s2.1-pro", choices=list(MODEL_BY_NAME))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    template = template_from_args(args)
    config = SmartTTSConfig.from_env()
    require_tool("ffmpeg")
    require_tool("ffprobe")

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    speech_path = out / "speech_full.mp3"
    speech_v1 = out / "speech_v1.mp3"
    speech_v2 = out / "speech_v2.mp3"
    final_path = out / "investigation_final.mp3"

    generate_music = args.music is None and bool(template.music_prompt)
    generate_ambient = (
        not args.no_ambient and args.ambient_file is None and bool(template.ambient_prompt)
    )

    if not args.remix_only:
        print(f"→ Fish Audio {args.model} через smart_tts (шаблон: {template.name})")
        print(f"  Голос: {args.voice} ({template.voice_id})")
        print(f"  Вариантов: {args.variants}")

        with SmartTTS(config) as tts:
            for i in range(1, args.variants + 1):
                path = out / f"speech_v{i}.mp3"
                temp = 0.65 + i * 0.05 if args.variants > 1 else 0.7
                print(f"  Генерация v{i} (temperature={temp:.2f})...")
                result = tts.synthesize_text_to_file(
                    RAW_SCRIPT,
                    template,
                    path,
                    mix=False,
                    voice_settings=VoiceSettings(temperature=temp, speed=1.0),
                )
                print(f"    {audio_duration_seconds(path):.1f} с → {path.name}")
                print(f"    Модель: {result.metadata['fish_model']}")
                print(f"    Текст: {result.enhanced_text[:80]}...")

        best = speech_v1
        if args.variants >= 2 and speech_v2.exists():
            best = speech_v2
        shutil.copy2(best, speech_path)
        print(f"  Основа речи: {best.name}")
    elif not speech_path.exists():
        raise SystemExit(f"Нет {speech_path}. Запустите без --remix-only.")

    print(f"  Речь: {audio_duration_seconds(speech_path):.1f} с")

    if template.music_path:
        print(f"→ Музыка: {Path(template.music_path).name}")
    elif generate_music:
        print("→ Музыка: ElevenLabs API")
    elif not template.music_path:
        print("→ Музыка: пропуск")

    if args.no_ambient:
        print("→ Эмбиент: пропуск (--no-ambient)")
    elif template.ambient_path:
        print(f"→ Эмбиент: {Path(template.ambient_path).name}")
    elif generate_ambient:
        print("→ Эмбиент: ElevenLabs API")
    else:
        print("→ Эмбиент: пропуск")

    vol_parts = [
        f"речь={template.speech_volume:.2f}",
        f"музыка={template.music_volume:.2f}",
        f"эмбиент={template.ambient_volume:.2f}",
        f"bed={template.bed_weight:.2f}",
    ]
    print(f"→ Сведение ({', '.join(vol_parts)})...")

    with SmartTTS(config) as tts:
        tts.remix_file(
            speech_path,
            final_path,
            template,
            generate_music=generate_music,
            generate_ambient=generate_ambient,
        )

    print()
    print("Готово!")
    if not args.remix_only and args.variants > 1:
        print(f"  Сравните: {speech_v1.name} и {speech_v2.name}")
    print(f"  Итог: {final_path.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(exc.stderr.decode() if exc.stderr else exc, file=sys.stderr)
        raise SystemExit(1) from exc
