# smart-tts

High-level Python library for expressive speech production: [Fish Audio](https://fish.audio) TTS, [ElevenLabs](https://elevenlabs.io) music and ambient beds, and ffmpeg layer mixing.

Pass raw text (optionally with SSML `<break>` tags) — the library converts pauses to Fish Audio paralanguage, synthesizes speech in one continuous pass, and can mix music and ambient underneath.

## Features

- **SmartTTS facade** — one pipeline from text to audio
- **Fish Audio speech** — single-pass synthesis via `s2.1-pro` (fallback to `s2.1-pro-free` on 402)
- **SSML breaks → Fish S2 tags** — `<break time="1.2s"/>` becomes `[long pause]`
- **ElevenLabs beds** — optional music (`music.compose`) and ambient (`text_to_sound_effects`)
- **ffmpeg mixing** — speech + music + ambient with volume weights
- **Sync & async API** — `SmartTTS` / `AsyncSmartTTS` with the same signatures
- **Voice registry** — local `diskcache` for registered Fish `reference_id` voices

## Requirements

- Python 3.11+
- `ffmpeg` and `ffprobe` in `PATH` (only when mixing layers)

## Installation

```bash
pip install smart-tts
```

Or from source:

```bash
git clone https://github.com/vpuhoff/smart-tts.git
cd smart-tts
uv sync --dev
```

## Quick start

1. Copy `.env.example` to `.env` and set your API keys:

```bash
cp .env.example .env
```

2. Run synthesis:

```python
from pathlib import Path

from smart_tts import SmartTTS, SynthesisTask, VoiceSettings

tts = SmartTTS.from_env()
tts.sync_voices()

result = tts.synthesize_to_file(
    SynthesisTask(
        text='Центр, <break time="1.2s" /> на связи резидентура.',
        language="ru",
        style="serious",
        emotion="serious",
        voice_id="67d37d81cb7340b391e9461d6671de03",
        voice_settings=VoiceSettings(temperature=0.7, speed=1.0),
    ),
    Path("output.mp3"),
)

print(result.enhanced_text)
```

See [`example.py`](example.py) for a full demo: detective radio report with speech variants, custom music, and remix.

```bash
uv run python example.py
uv run python example.py --variants 2
uv run python example.py --remix-only --music back.mp3
```

## Synthesis with music and ambient

Pass bed prompts or file paths in `SynthesisTask` — `synthesize()` generates speech, then mixes layers automatically:

```python
result = tts.synthesize(
    SynthesisTask(
        text="...",
        voice_id="your-fish-reference-id",
        music_prompt="Melancholic noir piano, instrumental, no vocals",
        ambient_prompt="Subtle radio hum, tape hiss, seamless loop",
        music_volume=0.32,
        ambient_volume=0.18,
        bed_weight=0.68,
    )
)
```

Or provide pre-recorded files:

```python
SynthesisTask(
    text="...",
    music_path="back.mp3",
    ambient_path="ambient.wav",
)
```

`ELEVENLABS_API_KEY` is required for API-generated beds. Custom files work without it.

## Task parameters

### Core fields

| Field | Description |
|-------|-------------|
| `text` | Source script; SSML `<break time="Xs"/>` converted to Fish pauses when `enhance_text=True` |
| `voice_id` | Fish Audio `reference_id` |
| `language` | Language hint (metadata / emotion mapping) |
| `style`, `emotion`, `use_case` | Context hints; `emotion` adds Fish paralanguage prefix |
| `enhance_text` | `True` — break conversion + emotion prefix; `False` — raw text |
| `voice_settings` | `temperature`, `speed`, `top_p`, `repetition_penalty` for Fish API |
| `model` | Fish model (see table below) |

### Mixing fields

| Field | Default | Description |
|-------|---------|-------------|
| `music_prompt` | — | ElevenLabs Music API prompt |
| `ambient_prompt` | — | ElevenLabs Sound Effects API prompt |
| `music_path` | — | Pre-recorded music file |
| `ambient_path` | — | Pre-recorded ambient file |
| `music_volume` | `0.32` | Music level in mix |
| `ambient_volume` | `0.18` | Ambient level in mix |
| `speech_volume` | `1.0` | Speech gain in mix (`1.0` = unchanged) |
| `bed_weight` | `0.68` | Background bed weight vs speech |

### SSML breaks

```python
# Input
'Срочное донесение. <break time="1.2s" /> Обнаружена цель.'

# After enhance_text (Fish S2 [bracket] tags)
'Срочное донесение. [long pause] Обнаружена цель.'
```

| Pause | Fish markup |
|-------|-------------|
| ≥ 1.2 s | `[long pause]` |
| ≥ 0.75 s | `[pause]` |
| ≥ 0.4 s | `...` |

### Emotion tags

Fish Audio S2/S2.1 interprets `[bracket]` tags as delivery hints (not spoken text). Parenthesis prose like `(soft tone)` is **not** supported and may be read aloud.

| `emotion` | Tag added |
|-----------|-----------|
| `warm` | `[warm]` |
| `serious` | `[serious]` |
| `excited` | `[excited]` |
| `sad` | `[sad]` |
| `whisper` | `[whisper]` |
| `calm` | `[calm]` |

## Configuration

### Required

| Variable | Description |
|----------|-------------|
| `FISH_API_KEY` | Fish Audio API key |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `ELEVENLABS_API_KEY` | — | For music/ambient generation |
| `FISH_DEFAULT_MODEL` | `s2.1-pro` | Fish model (`s2.1-pro-free` if no paid credits) |
| `FISH_DEFAULT_VOICE_ID` | Kanevsky ref id | Fallback `reference_id` |
| `FISH_API_URL` | `https://api.fish.audio/v1/tts` | Fish TTS endpoint |
| `ELEVENLABS_CACHE_DIR` | `~/.cache/smart-tts` | Voice registry cache |
| `ELEVENLABS_DEFAULT_OUTPUT_FORMAT` | `mp3_44100_128` | Output format |

Programmatic configuration:

```python
from smart_tts import SmartTTS, SmartTTSConfig, TTSModel

config = SmartTTSConfig(
    fish_api_key="...",
    elevenlabs_api_key="...",  # optional
    default_model=TTSModel.ELEVEN_V3,
    default_voice_id="67d37d81cb7340b391e9461d6671de03",
)
tts = SmartTTS(config)
```

## Usage

### Synthesis pipeline

```python
from smart_tts import SmartTTS, SynthesisTask, TTSModel, VoiceSettings

with SmartTTS.from_env() as tts:
    tts.sync_voices()
    result = tts.synthesize(
        SynthesisTask(
            text="Срочное донесение.",
            voice_id="67d37d81cb7340b391e9461d6671de03",
            model=TTSModel.ELEVEN_V3,
            emotion="serious",
            voice_settings=VoiceSettings(temperature=0.7),
        )
    )
    audio_bytes = result.audio
    prepared_text = result.enhanced_text
```

### Generation templates

Use `GenerationTemplate` to bundle speech, background, and mix settings. Pass only the script text at synthesis time:

```python
from pathlib import Path

from smart_tts import INVESTIGATION, GenerationTemplate, SmartTTS, synthesize_with_template

# Built-in preset
with SmartTTS.from_env() as tts:
    speech = tts.synthesize_text(
        'Срочное донесение. <break time="1.2s" /> Обнаружена цель.',
        INVESTIGATION,
        mix=False,  # speech only
    )
    tts.synthesize_text_to_file(
        "Конец связи.",
        INVESTIGATION,
        Path("output/speech.mp3"),
        mix=False,
    )
    tts.remix_file(
        Path("output/speech.mp3"),
        Path("output/final.mp3"),
        INVESTIGATION,
    )

# Custom template or overrides
template = INVESTIGATION.with_overrides(
    speech_volume=1.2,
    music_path="back.mp3",
    ambient_path=None,
)
result = synthesize_with_template("Привет!", template, mix=True)

# Load/save JSON recipes (see templates/investigation.json)
template = GenerationTemplate.from_json_file("templates/investigation.json")
```

| Method | Description |
|--------|-------------|
| `template.to_task(text, mix=True, **overrides)` | Build `SynthesisTask` |
| `template.with_overrides(**kwargs)` | Copy with changed fields |
| `GenerationTemplate.from_dict()` / `from_json_file()` | Deserialize |
| `template.save_json(path)` | Serialize to JSON |
| `get_template("investigation")` | Built-in preset lookup |
| `tts.synthesize_text(text, template)` | Synthesize with template |
| `tts.remix_file(speech, output, template)` | Mix speech + beds |

### Preview prepared text without TTS

```python
prepared = tts.enhance_text_only(
    SynthesisTask(
        text='Центр, <break time="1.2s" /> на связи.',
        emotion="warm",
    )
)
```

### One-liner

```python
from smart_tts import synthesize

result = synthesize(
    "Привет, мир!",
    language="ru",
    style="neutral",
)
```

### Async API

```python
import asyncio
from pathlib import Path

from smart_tts import AsyncSmartTTS, SynthesisTask, asynthesize

async def main() -> None:
    async with AsyncSmartTTS.from_env() as tts:
        result = await tts.synthesize_to_file(
            SynthesisTask(text="Привет!", language="ru"),
            Path("output.mp3"),
        )
        print(result.enhanced_text)

asyncio.run(main())
```

### Pydantic AI tools (optional)

Install the extension::

```bash
pip install smart-tts[pydantic-ai]
```

Register a toolset with an agent and pass `SmartTTSDeps` as runtime dependencies:

```python
from pathlib import Path

from pydantic_ai import Agent

from smart_tts.async_tts import AsyncSmartTTS
from smart_tts.extensions.pydantic_ai import (
    SmartTTSDeps,
    create_smart_tts_toolset,
    resolve_openrouter_model,
)

async with AsyncSmartTTS.from_env() as tts:
    agent = Agent(
        resolve_openrouter_model(),  # OPENROUTER_API_KEY + model from .env
        deps_type=SmartTTSDeps,
        toolsets=[create_smart_tts_toolset()],
    )
    result = await agent.run(
        "Озвучь донесение: Обнаружена цель.",
        deps=SmartTTSDeps(tts=tts, output_dir=Path("output")),
    )
```

Tools:

| Tool | Description |
|------|-------------|
| `synthesize_speech` | Synthesize audio from text + template, save MP3, return metadata |
| `list_generation_templates` | List built-in templates |
| `preview_speech_text` | Preview prepared Fish text without API call |

Полный пример: [`example_pydantic_ai.py`](example_pydantic_ai.py)

```bash
pip install smart-tts[pydantic-ai]
uv run python example_pydantic_ai.py              # прямой вызов tools
uv run python example_pydantic_ai.py --agent        # агент + TestModel
uv run python example_pydantic_ai.py --agent --live # агент + OpenRouter LLM
```

Requires `OPENROUTER_API_KEY`. Model is taken from `--model`, `PYDANTIC_AI_MODEL`, or `OPENROUTER_API_TTS_PROMPT_MODEL`.

### OpenTelemetry tracing (optional)

```bash
pip install smart-tts[otel-sdk]
```

```python
from smart_tts.extensions.otel import configure_tracing, shutdown_tracing

configure_tracing()  # uses OTEL_EXPORTER_OTLP_ENDPOINT
with SmartTTS.from_env() as tts:
    tts.synthesize_text("Привет!", INVESTIGATION, mix=False)
shutdown_tracing()
```

Spans are emitted for synthesis, Fish/ElevenLabs calls, ffmpeg mix, and Pydantic AI tools. Without `opentelemetry-api`, tracing is a no-op.

### Voice registry

```python
voices = tts.list_voices()
voice = tts.get_voice("reference-id")
tts.sync_voices(force=True)  # refresh default voice in cache
```

Fish voices are referenced by `reference_id` from the Fish Audio console. Register custom voices via `VoiceRegistry.register_voice()` or set `FISH_DEFAULT_VOICE_ID`.

## Models (`TTSModel`)

Legacy enum names map to Fish Audio models:

| Enum | Fish model | Notes |
|------|------------|-------|
| `TTSModel.ELEVEN_V3` | `s2.1-pro` | Default; auto-fallback to `s2.1-pro-free` on 402 |
| `TTSModel.ELEVEN_MULTILINGUAL_V2` | `s2-pro` | |
| `TTSModel.ELEVEN_FLASH_V2_5` | `s1` | |

## Package layout

```
smart_tts/
├── tts.py, async_tts.py     # SmartTTS facade
├── telemetry.py             # OpenTelemetry spans (optional)
├── templates.py             # GenerationTemplate presets
├── config.py, models.py
├── client/
│   ├── fish.py              # Fish Audio TTS
│   └── elevenlabs.py        # Music + ambient beds
├── script/breaks.py         # SSML → Fish paralanguage
├── audio/mixer.py           # ffmpeg mix_tracks
├── text.py                  # prepare_text()
└── voices/registry.py       # diskcache voice registry
```

## Development

```bash
uv sync --dev
uv run pytest
uv run ruff check .
```

## License

MIT — see [LICENSE](LICENSE).

## Links

- [Agent integration guide](agents.md)
- [GitHub repository](https://github.com/vpuhoff/smart-tts)
- [PyPI package](https://pypi.org/project/smart-tts/)
- [Design specification (Russian)](spec.md)
