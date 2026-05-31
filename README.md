# elevenlabs-smart-tts

High-level Python library for expressive text-to-speech with [ElevenLabs](https://elevenlabs.io) and LLM-powered text enhancement via [OpenRouter](https://openrouter.ai).

Pass raw text plus task context (language, style, emotion, use case) — the library picks a voice, enriches the text with Eleven v3 audio tags, and returns synthesized audio.

## Features

- **SmartTTS facade** — one pipeline from text to audio
- **Voice caching** — local `diskcache` catalog with offline `list_voices()` / `get_voice()`
- **Automatic voice selection** — by `voice_id`, description, use case, style, and language
- **LLM text enhancement** — audio tags, punctuation, and normalization via OpenRouter
- **Eleven v3 first** — expressive tags like `[whispers]`, `[excited]`, `[short pause]`
- **Typed errors & retries** — resilient HTTP clients for ElevenLabs and OpenRouter

## Installation

```bash
pip install elevenlabs-smart-tts
```

Or from source:

```bash
git clone https://github.com/vpuhoff/elevenlabs-smart-tts.git
cd elevenlabs-smart-tts
uv sync --dev
```

## Quick start

1. Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

2. Run synthesis:

```python
from pathlib import Path

from elevenlabs_smart_tts import SmartTTS, SynthesisTask

tts = SmartTTS.from_env()
tts.sync_voices()

result = tts.synthesize_to_file(
    SynthesisTask(
        text="Welcome to our customer support service.",
        language="en",
        style="professional",
        emotion="warm",
        use_case="conversational",
        voice_description="warm professional conversational",
    ),
    Path("output.mp3"),
)

print(result.enhanced_text)
```

See [`example.py`](example.py) for a full runnable example.

## Task parameters

`SynthesisTask` accepts free-text hints that guide **voice selection** and **LLM text enhancement**. After `sync_voices()`, inspect your cached catalog:

```python
for voice in tts.list_voices():
    print(voice.name, voice.labels.get("use_case"), voice.description)
```

The examples below come from the ElevenLabs premade voice catalog.

### `use_case`

Used for voice matching against the ElevenLabs voice label `labels.use_case` (exact match scores highest).

| Value | Typical voices |
|-------|----------------|
| `conversational` | Casual, agentic, podcast-style voices (e.g. Roger, Eric, Juniper) |
| `informative_educational` | Clear educators, broadcasters (e.g. Alice, Matilda, Daniel) |
| `narrative_story` | Storytellers, audiobook voices (e.g. George, Daria Reels) |
| `advertisement` | Promo and ad reads (e.g. Bill) |
| `social_media` | Short-form, trendy content |
| `characters_animation` | Character and animation voices |
| `entertainment_tv` | TV and entertainment narration |

`customer_support` is **not** an ElevenLabs label — it still helps the LLM, but for voice selection prefer `conversational` or pass `voice_description="professional support warm"`.

```python
# Support-style call center message
SynthesisTask(
    text="Thanks for calling. How can I help you today?",
    language="en",
    use_case="conversational",
    style="professional",
    emotion="warm",
    voice_description="trustworthy professional",
)

# Audiobook / long-form narration
SynthesisTask(
    text="Chapter one. It was a dark and stormy night.",
    use_case="narrative_story",
    style="warm",
    emotion="calm",
)

# E-learning explainer
SynthesisTask(
    text="Today we'll learn how photosynthesis works.",
    use_case="informative_educational",
    style="professional",
    emotion="neutral",
)
```

### `style`

Free-form delivery hint. Affects the **LLM enhancement prompt** and weak voice matching against voice name, description, and custom tags.

Common values that match premade voice descriptions:

| Value | Effect |
|-------|--------|
| `professional` | Formal, clear delivery |
| `casual` / `conversational` | Relaxed, everyday tone |
| `warm` | Friendly, inviting tone |
| `neutral` | Balanced, informative |
| `dramatic` | Strong emphasis, expressive pacing |
| `playful` | Light, energetic tone |
| `sympathetic` | Soft, empathetic delivery |

```python
SynthesisTask(text="...", style="professional")   # business / IVR
SynthesisTask(text="...", style="casual")         # laid-back chat
SynthesisTask(text="...", style="dramatic")       # emotional scene
```

### `emotion`

Free-form mood hint for **LLM text enhancement only** (drives audio tags like `[excited]`, `[whispers]`, `[sighs]`). Does not filter voices.

| Value | Typical audio tag behavior |
|-------|----------------------------|
| `warm` | Friendly, reassuring tone |
| `calm` | Steady, subdued delivery |
| `excited` | Higher energy, `[excited]` tags |
| `sympathetic` | Soft, caring tone |
| `curious` | Questioning, engaged tone |
| `appalled` / `sarcastic` | Strong expressive tags |
| `neutral` | Minimal emotional markup |

```python
SynthesisTask(text="...", emotion="warm")         # customer greeting
SynthesisTask(text="...", emotion="excited")      # product launch
SynthesisTask(text="...", emotion="sympathetic")  # apology or support
SynthesisTask(text="...", emotion="neutral")     # plain narration
```

### Combining parameters

| Scenario | Example values |
|----------|----------------|
| Customer support (EN) | `use_case="conversational"`, `style="professional"`, `emotion="warm"` |
| News / podcast intro | `use_case="informative_educational"`, `style="neutral"`, `emotion="calm"` |
| Audiobook chapter | `use_case="narrative_story"`, `style="warm"`, `emotion="calm"` |
| Social reel | `use_case="social_media"`, `style="playful"`, `emotion="excited"` |
| Ad read | `use_case="advertisement"`, `style="confident"`, `emotion="excited"` |

## Configuration

### Required environment variables

| Variable | Description |
|----------|-------------|
| `ELEVENLABS_API_KEY` | ElevenLabs API key |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `OPENROUTER_API_TTS_PROMPT_MODEL` | LLM for text enhancement (e.g. `anthropic/claude-3.5-sonnet`) |

### Optional environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ELEVENLABS_CACHE_DIR` | `~/.cache/elevenlabs-smart-tts` | Local cache directory |
| `ELEVENLABS_DEFAULT_MODEL` | `eleven_v3` | Default TTS model |
| `ELEVENLABS_DEFAULT_OUTPUT_FORMAT` | `mp3_44100_128` | Audio output format |
| `ELEVENLABS_DEFAULT_VOICE_ID` | — | Fallback voice when auto-selection fails |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter API base URL |

Programmatic configuration is also supported:

```python
from elevenlabs_smart_tts import SmartTTS, SmartTTSConfig, TTSModel

config = SmartTTSConfig(
    elevenlabs_api_key="...",
    openrouter_api_key="...",
    openrouter_tts_prompt_model="anthropic/claude-3.5-sonnet",
    default_model=TTSModel.ELEVEN_V3,
)
tts = SmartTTS(config)
```

## Usage

### Synthesis pipeline

```python
from elevenlabs_smart_tts import SmartTTS, SynthesisTask, TTSModel

tts = SmartTTS.from_env()
tts.sync_voices()

result = tts.synthesize(
    SynthesisTask(
        text="Are you serious? I can't believe you did that!",
        voice_id="your-voice-id",
        model=TTSModel.ELEVEN_V3,
        style="dramatic",
        emotion="appalled",
    )
)

audio_bytes = result.audio
enhanced_text = result.enhanced_text
```

### Preview enhanced text without TTS

```python
enhanced = tts.enhance_text_only(
    SynthesisTask(
        text="Thanks for calling. How can I help?",
        language="en",
        style="sympathetic",
    )
)
```

### One-liner

```python
from elevenlabs_smart_tts import synthesize

result = synthesize(
    "Hello world",
    language="en",
    style="neutral",
)
```

### Async API

```python
import asyncio
from pathlib import Path

from elevenlabs_smart_tts import AsyncSmartTTS, SynthesisTask, asynthesize

async def main() -> None:
    async with AsyncSmartTTS.from_env() as tts:
        await tts.sync_voices()
        result = await tts.synthesize_to_file(
            SynthesisTask(text="Hello world", language="en"),
            Path("output.mp3"),
        )
        print(result.enhanced_text)

asyncio.run(main())

# Or as a one-liner:
result = asyncio.run(asynthesize("Hello world", language="en"))
```

### Voice management

```python
voices = tts.list_voices(language="en", tags=["narration"])
voice = tts.get_voice("voice-id")

tts.sync_voices(force=True)  # refresh cache from ElevenLabs API
```

## Supported TTS models

| Model | Best for |
|-------|----------|
| `eleven_v3` | Expressive speech, audio tags, emotions |
| `eleven_multilingual_v2` | Multilingual, high voice similarity |
| `eleven_flash_v2_5` | Low latency, conversational agents |

## Development

```bash
uv sync --dev
uv run pytest
uv run ruff check .
```

## License

MIT — see [LICENSE](LICENSE).

## Links

- [GitHub repository](https://github.com/vpuhoff/elevenlabs-smart-tts)
- [PyPI package](https://pypi.org/project/elevenlabs-smart-tts/)
- [Design specification (Russian)](spec.md)
