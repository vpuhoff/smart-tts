# Инструкция для AI-агентов: интеграция smart-tts

Документ для coding-агентов (Cursor, Claude, Codex и др.), которые подключают библиотеку `smart-tts` в проекты или расширяют этот репозиторий.

## Что делает библиотека

`smart-tts` — Python-библиотека для озвучивания текста:

1. **Речь** — Fish Audio (`s2.1-pro`, fallback на `s2.1-pro-free` при 402)
2. **Фон** — музыка и эмбиент через ElevenLabs (опционально)
3. **Сведение** — ffmpeg (`speech` + `music` + `ambient`)

Пайплайн: сырой текст → подготовка (SSML breaks, emotion-теги) → Fish TTS → опциональный mix → MP3.

## Когда использовать какой API

| Задача | API |
|--------|-----|
| Один вызов, минимум кода | `synthesize()` / `asynthesize()` |
| Полный контроль полей | `SynthesisTask` + `SmartTTS.synthesize()` |
| Повторяемые пресеты (детектив, подкаст…) | `GenerationTemplate` + `synthesize_text()` |
| Агент с tool calling | `smart_tts.extensions.pydantic_ai` |
| Только речь, без фона | `mix=False` в template или не передавать bed-поля |
| Речь уже есть, нужен только mix | `tts.remix_file(speech_path, output_path, template)` |

**Предпочитай `GenerationTemplate`**, если настройки повторяются. Текст передаётся отдельно при каждом синтезе.

## Установка

```bash
pip install smart-tts
# для Pydantic AI tools:
pip install smart-tts[pydantic-ai]
```

Системные зависимости:

- Python 3.11+
- `ffmpeg` и `ffprobe` в `PATH` — **только при сведении** (mix с музыкой/эмбиентом)

## Переменные окружения

Скопируй `.env.example` → `.env`.

| Переменная | Обязательна | Назначение |
|------------|-------------|------------|
| `FISH_API_KEY` | **да** | Fish Audio TTS |
| `ELEVENLABS_API_KEY` | нет | Генерация music/ambient через API |
| `FISH_DEFAULT_VOICE_ID` | нет | Fallback `reference_id` Fish |
| `FISH_DEFAULT_MODEL` | нет | `s2.1-pro` по умолчанию |
| `OPENROUTER_API_KEY` | нет | LLM-агент (режим `--live` в примере) |
| `OPENROUTER_API_TTS_PROMPT_MODEL` | нет | Модель OpenRouter для агента |
| `PYDANTIC_AI_MODEL` | нет | Явный model id для Pydantic AI |

**Не коммить** `.env` и API-ключи.

## Быстрая интеграция (рекомендуемый путь)

### 1. Шаблон + синтез

```python
from pathlib import Path

from smart_tts import INVESTIGATION, SmartTTS

with SmartTTS.from_env() as tts:
    result = tts.synthesize_text_to_file(
        'Срочное донесение. <break time="1.2s" /> Обнаружена цель.',
        INVESTIGATION,
        Path("output/speech.mp3"),
        mix=False,  # только речь
    )
    print(result.enhanced_text)
```

### 2. Кастомный шаблон

```python
from smart_tts import GenerationTemplate, INVESTIGATION, VoiceSettings

template = INVESTIGATION.with_overrides(
    speech_volume=1.2,
    music_path="back.mp3",
    voice_settings=VoiceSettings(temperature=0.7, speed=1.0),
)

# или из JSON
template = GenerationTemplate.from_json_file("templates/investigation.json")
```

Встроенные шаблоны: `investigation`, `default` — через `get_template(name)` или `INVESTIGATION`.

### 3. Async

```python
from pathlib import Path

from smart_tts import AsyncSmartTTS, INVESTIGATION

async with AsyncSmartTTS.from_env() as tts:
    result = await tts.synthesize_text(
        "Привет!",
        INVESTIGATION,
        mix=False,
    )
    audio_bytes = result.audio
```

## Pydantic AI (tool calling)

Установка: `pip install smart-tts[pydantic-ai]`.

### Минимальный агент (OpenRouter)

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
        resolve_openrouter_model(),
        deps_type=SmartTTSDeps,
        toolsets=[create_smart_tts_toolset()],
        instructions=(
            "Для озвучивания вызывай synthesize_speech. "
            "Шаблон investigation — нуар-детектив. "
            "mix=false — только речь без фона."
        ),
    )
    result = await agent.run(
        "Озвучь: Срочное донесение. Обнаружена цель.",
        deps=SmartTTSDeps(tts=tts, output_dir=Path("output")),
    )
```

### Доступные tools

| Tool | Вход | Выход |
|------|------|-------|
| `synthesize_speech` | `SynthesizeSpeechRequest` | `SynthesizeSpeechResult` (path, metadata) |
| `list_generation_templates` | — | `list[TemplateInfo]` |
| `preview_speech_text` | `PreviewSpeechTextRequest` | `PreviewSpeechTextResult` |

Все схемы — Pydantic-модели с `Field(description=...)`. Агент получает JSON Schema автоматически.

### Прямой вызов без агента

```python
from smart_tts.extensions.pydantic_ai import (
    SmartTTSDeps,
    SynthesizeSpeechRequest,
    run_synthesize_speech,
)

result = await run_synthesize_speech(
    deps,
    SynthesizeSpeechRequest(
        text="Текст для озвучки.",
        template="investigation",
        mix=False,
        output_filename="out.mp3",
    ),
)
```

### Интеграция с существующим AgentDeps

Если у агента уже есть свой `deps_type`, не создавай отдельный `SmartTTSDeps`. Реализуй протокол `HasSmartTTS` — два property: `tts` и `tts_output_dir`.

Шаблоны подключай через `TemplateRegistry` (например PostgreSQL в продукте):

```python
from dataclasses import dataclass
from pathlib import Path

from pydantic_ai import Agent

from smart_tts.async_tts import AsyncSmartTTS
from smart_tts.extensions.pydantic_ai import (
    TemplateInfo,
    create_smart_tts_toolset,
    run_synthesize_speech,
    SynthesizeSpeechRequest,
    SynthesizeSpeechResult,
)
from smart_tts.templates import GenerationTemplate, TemplateRegistry, TemplateRegistryInfo


@dataclass
class AgentDeps:
    _tts: AsyncSmartTTS
    _output: Path

    @property
    def tts(self) -> AsyncSmartTTS:
        return self._tts

    @property
    def tts_output_dir(self) -> Path:
        return self._output


class PostgresTemplateRegistry:
    """Пример: шаблоны из JSONB в PostgreSQL."""

    def get(self, slug: str) -> GenerationTemplate:
        row = ...  # SELECT template_config FROM templates WHERE slug = slug
        return GenerationTemplate.from_dict(row.template_config)

    def list_info(self) -> list[TemplateRegistryInfo]:
        rows = ...  # SELECT slug, description, template_config FROM templates
        return [
            TemplateRegistryInfo(
                name=row.slug,
                template=GenerationTemplate.from_dict(row.template_config),
                description=row.description,
            )
            for row in rows
        ]


async def deliver_speech(result: SynthesizeSpeechResult) -> None:
    ...  # S3, Telegram и т.д.


registry = PostgresTemplateRegistry(...)
toolset = create_smart_tts_toolset(registry=registry)

agent = Agent(
    "openrouter:google/gemini-2.5-flash",
    deps_type=AgentDeps,
    toolsets=[toolset],
)

# Прямой вызов с уже resolved шаблоном (project → agent → default):
template = registry.get("investigation")
await run_synthesize_speech(
    deps,
    SynthesizeSpeechRequest(text="..."),
    template=template,
)

# Post-synthesis hook на SmartTTSDeps:
# async def on_synthesized(ctx, result):
#     agent_id = getattr(ctx.deps, "active_agent_id", None)
#     await deliver_speech_from_path(result.path, agent_id=agent_id)
# deps.on_synthesized = on_synthesized
```

### Template resolve chain (v1.9.5)

Когда `SynthesizeSpeechRequest.template` не задан (`None`) или пустой:

```text
request.template (if non-empty)
  → registry.get_default()
  → "investigation"  # hard fallback (HARD_TEMPLATE_FALLBACK)
```

Пример registry с project/agent default:

```python
class PostgresChainedTemplateRegistry:
    def get_default(self) -> str | None:
        if self._project.default_tts_template_slug:
            return self._project.default_tts_template_slug
        if self._agent_config.get("default_tts_template_slug"):
            return self._agent_config["default_tts_template_slug"]
        return None  # chain → builtin "default"
```

Voiceover fallback без явного template:

```python
from smart_tts.extensions.pydantic_ai import make_run_context, run_synthesize_speech

await run_synthesize_speech(
    deps,
    SynthesizeSpeechRequest(text=script),
    registry=registry,
    ctx=make_run_context(deps),
    timeout_sec=120,
)
```

### on_synthesized(ctx, result)

Hook вызывается **после** успешной записи MP3, **до** return из `run_synthesize_speech`.
При ошибке синтеза hook не вызывается; при ошибке hook exception пробрасывается наверх.

Legacy `on_synthesized(result)` поддерживается с `DeprecationWarning`.
Tool path всегда передаёт `ctx`; для fallback вне агента используй `make_run_context(deps)`.

### timeout_sec

```python
await run_synthesize_speech(deps, request, timeout_sec=120)
```

Приоритет: явный аргумент → env `SMART_TTS_SYNTHESIS_TIMEOUT_SEC` → без лимита.

Timeout покрывает Fish TTS + mix + probe duration. **Post-synthesis hook вне timeout** —
медленная доставка (S3/Telegram) не должна ронять tool после успешного synth.
При превышении — `SynthesisTimeoutError` (не generic `TimeoutError`).

Ключевые extension points:

| API | Назначение |
|-----|------------|
| `TemplateRegistry` | Источник шаблонов (БД, builtin chain) |
| `TemplateRegistry.get_default()` | Slug по умолчанию когда template опущен |
| `resolve_request_template()` | Единая точка resolve slug → template |
| `run_synthesize_speech(..., template=)` | Передать уже resolved `GenerationTemplate` |
| `run_synthesize_speech(..., registry=)` | Кастомный registry для `request.template` slug |
| `run_synthesize_speech(..., ctx=)` | RunContext для hook и fallback path |
| `run_synthesize_speech(..., timeout_sec=)` | Pipeline timeout (synth inside, hook outside) |
| `make_run_context(deps)` | Minimal RunContext вне `Agent.iter` |
| `SynthesizeSpeechRequest.mix=None` | Взять `mix_default` из шаблона |
| `SmartTTSDeps.on_synthesized(ctx, result)` | Delivery после записи файла |
| `create_smart_tts_toolset(registry=...)` | Одна точка конфигурации toolset |

### Запуск примера

```bash
uv run python example_pydantic_ai.py              # прямой вызов tools
uv run python example_pydantic_ai.py --agent        # TestModel (без LLM)
uv run python example_pydantic_ai.py --agent --live # OpenRouter
```

## Подготовка текста

### SSML breaks

При `enhance_text=True` (по умолчанию в шаблонах):

| Пауза | Fish-тег |
|-------|----------|
| ≥ 1.2 s | `[long pause]` |
| ≥ 0.75 s | `[pause]` |
| ≥ 0.4 s | `...` |

Пример: `<break time="1.2s"/>` → `[long pause]`.

### Emotion

Используй **квадратные скобки** через поле `emotion`, не prose в скобках:

| `emotion` | Тег |
|-----------|-----|
| `serious` | `[serious]` |
| `warm` | `[warm]` |
| `whisper` | `[whisper]` |

`(soft tone)` и подобное **озвучивается вслух** на Fish S2 — не использовать.

## Модели (`TTSModel`)

| Enum | Fish model |
|------|------------|
| `TTSModel.ELEVEN_V3` | `s2.1-pro` (default) |
| `TTSModel.S2_1_PRO_FREE` | `s2.1-pro-free` |
| `TTSModel.ELEVEN_MULTILINGUAL_V2` | `s2-pro` |
| `TTSModel.ELEVEN_FLASH_V2_5` | `s1` |

Имена enum исторические; значения — Fish Audio model id.

## Типичный workflow в репозитории

```
1. Проверить .env (FISH_API_KEY обязателен)
2. Выбрать шаблон или создать GenerationTemplate
3. Синтез: mix=False для черновика речи
4. Remix: tts.remix_file() с music_path / ambient
5. Проверить output/*.mp3
```

Полный CLI-демо: `example.py`  
Pydantic AI демо: `example_pydantic_ai.py`

## Частые ошибки

| Проблема | Решение |
|----------|---------|
| `Missing FISH_API_KEY` | Добавить ключ в `.env` |
| `ffprobe` failed | Установить ffmpeg; или использовать `mix=False` на этапе черновика |
| 402 Fish Audio | Авто-fallback на `s2.1-pro-free`; или задать `FISH_DEFAULT_MODEL=s2.1-pro-free` |
| Mix без ElevenLabs | Передать `music_path` / `ambient_path` вместо prompts |
| Tool возвращает path, не bytes | Так задумано — файл на диске в `SmartTTSDeps.output_dir` |
| Parenthesis в тексте озвучиваются | Заменить на `[emotion]` теги или SSML breaks |

## Структура пакета

```
smart_tts/
├── tts.py, async_tts.py       # SmartTTS / AsyncSmartTTS
├── templates.py               # GenerationTemplate, INVESTIGATION
├── extensions/pydantic_ai.py  # Pydantic AI toolset (optional)
├── client/fish.py             # Fish TTS
├── client/elevenlabs.py       # Music + ambient
├── script/breaks.py           # SSML → Fish tags
├── audio/mixer.py             # ffmpeg mix
└── voices/registry.py         # Voice cache
```

## Тесты

```bash
uv sync --dev
uv run pytest
```

При изменениях в `extensions/pydantic_ai.py` — `tests/test_pydantic_ai_extension.py`.

## Чеклист для агента перед PR

- [ ] `FISH_API_KEY` не попал в код/коммиты
- [ ] Новые параметры добавлены в `GenerationTemplate`, если это пресет
- [ ] Pydantic-схемы tools имеют `Field(description=...)`
- [ ] `mix=False` в тестах/примерах, если не нужен ffmpeg
- [ ] `uv run pytest` проходит
- [ ] Примеры запускаются (`example.py`, при необходимости `example_pydantic_ai.py`)

## OpenTelemetry (spans / traces)

Библиотека создаёт spans автоматически при установленном `opentelemetry-api`:

```bash
pip install smart-tts[otel]          # только API (no-op без SDK)
pip install smart-tts[otel-sdk]      # SDK + OTLP exporter
```

Экспорт traces:

```python
from smart_tts.extensions.otel import configure_tracing, shutdown_tracing

configure_tracing()  # OTEL_EXPORTER_OTLP_ENDPOINT или console через OTEL_TRACES_CONSOLE=1
try:
    ...
finally:
    shutdown_tracing()
```

Иерархия spans:

| Span | Где |
|------|-----|
| `smart_tts.synthesize` | `SmartTTS` / `AsyncSmartTTS` |
| `smart_tts.synthesize_text` | template-based синтез |
| `smart_tts.mix_layers` | сведение в пайплайне |
| `smart_tts.remix_file` | remix готовой речи |
| `smart_tts.fish.synthesize` / `smart_tts.fish.request` | Fish Audio API |
| `smart_tts.elevenlabs.generate_music` / `generate_ambient` | ElevenLabs beds |
| `smart_tts.audio.mix_tracks` | ffmpeg |
| `smart_tts.tool.synthesize_speech` | Pydantic AI tool |

Полезные атрибуты: `smart_tts.voice_id`, `smart_tts.model`, `smart_tts.fish_model`, `smart_tts.mixed`, `smart_tts.template`, `smart_tts.duration_ms`.

Корреляция в логах:

```python
from smart_tts.telemetry import current_trace_id

trace_id = current_trace_id()
```

## Ссылки

- [README.md](README.md) — пользовательская документация
- [spec.md](spec.md) — дизайн-спецификация (RU)
- [templates/investigation.json](templates/investigation.json) — пример JSON-шаблона
