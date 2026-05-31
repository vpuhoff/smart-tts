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
        use_case="customer_support",
    ),
    Path("output.mp3"),
)

print(result.enhanced_text)
```

See [`example.py`](example.py) for a full runnable example.

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
