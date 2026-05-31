# Спецификация библиотеки: умный генератор озвучки ElevenLabs

## 1. Обзор

**Название (рабочее):** `elevenlabs-smart-tts` (или `smart_tts`)

**Назначение:** Python-библиотека высокого уровня для генерации выразительной озвучки через ElevenLabs API с предобработкой текста LLM через OpenRouter. Библиотека автоматически подбирает голос, обогащает текст audio-тегами Eleven v3 и управляет локальным кэшем голосов.

**Ключевая идея:** пользователь передаёт «сырой» текст и описание задачи (стиль, эмоции, язык, контекст) — библиотека сама выбирает подходящий голос из кэша, обрабатывает текст по best practices Eleven v3 и возвращает аудио.

---

## 2. Цели и не-цели

### Цели
- Единый интерфейс для TTS с учётом модели, языка, стиля и голоса
- Локальный кэш каталога голосов ElevenLabs (`diskcache`)
- LLM-предобработка текста (audio-теги, пунктуация, нормализация) через OpenRouter
- Выбор голоса из кэша по описанию задачи
- Поддержка Eleven v3 как основной модели с expressive audio tags

### Не-цели (v1)
- Создание/клонирование голосов (Voice Design, IVC/PVC)
- Постобработка аудио (удаление тегов, монтаж)
- Streaming TTS
- Web UI
- Multi-speaker dialogue с разными `voice_id` в одном запросе (можно заложить в v2)

---

## 3. Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                     SmartTTS (фасад)                            │
│  synthesize(text, task) → AudioResult                           │
└────────────┬───────────────────────────────┬────────────────────┘
             │                               │
    ┌────────▼────────┐              ┌───────▼────────┐
    │  VoiceManager   │              │ TextEnhancer   │
    │  (diskcache)    │              │ (OpenRouter)   │
    └────────┬────────┘              └───────┬────────┘
             │                               │
    ┌────────▼────────┐              ┌───────▼────────┐
    │ ElevenLabsClient│              │ PromptBuilder  │
    │ (REST/SDK)      │              │ (best practices│
    └─────────────────┘              │  templates)    │
                                       └────────────────┘
```

### Компоненты

| Комponent | Ответственность |
|-----------|-----------------|
| `SmartTTS` | Главный фасад, оркестрация pipeline |
| `VoiceManager` | Загрузка, кэширование, поиск голосов |
| `VoiceSelector` | Выбор голоса по описанию задачи |
| `TextEnhancer` | LLM-обогащение текста через OpenRouter |
| `PromptBuilder` | Сборка system/user промптов по best practices |
| `ElevenLabsClient` | HTTP-клиент к ElevenLabs TTS API |
| `Config` | Конфигурация из env и параметров |
| `CacheStore` | Абстракция над `diskcache` |

---

## 4. Конфигурация

### Переменные окружения

| Переменная | Обязательна | Описание |
|------------|-------------|----------|
| `ELEVENLABS_API_KEY` | да | API-ключ ElevenLabs |
| `OPENROUTER_API_KEY` | да | API-ключ OpenRouter |
| `OPENROUTER_API_TTS_PROMPT_MODEL` | да | Модель для предобработки текста (напр. `anthropic/claude-3.5-sonnet`) |

### Опциональные параметры

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `ELEVENLABS_CACHE_DIR` | `~/.cache/elevenlabs-smart-tts` | Директория diskcache |
| `ELEVENLABS_DEFAULT_MODEL` | `eleven_v3` | Модель TTS по умолчанию |
| `ELEVENLABS_DEFAULT_OUTPUT_FORMAT` | `mp3_44100_128` | Формат аудио |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Base URL OpenRouter |

### Объект конфигурации

```python
@dataclass
class SmartTTSConfig:
    elevenlabs_api_key: str
    openrouter_api_key: str
    openrouter_tts_prompt_model: str
    cache_dir: Path = Path("~/.cache/elevenlabs-smart-tts")
    default_model: TTSModel = TTSModel.ELEVEN_V3
    default_output_format: OutputFormat = OutputFormat.MP3_44100_128
    default_voice_settings: VoiceSettings = field(default_factory=VoiceSettings)
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    cache_ttl_voices: int = 86400  # 24 часа
    cache_ttl_enhanced_text: int = 3600  # 1 час (опционально)
```

---

## 5. Модели данных

### 5.1 TTS-модели ElevenLabs

```python
class TTSModel(str, Enum):
    ELEVEN_V3 = "eleven_v3"
    ELEVEN_MULTILINGUAL_V2 = "eleven_multilingual_v2"
    ELEVEN_FLASH_V2_5 = "eleven_flash_v2_5"
    # расширяемо
```

**Правила выбора модели:**

| Модель | Когда использовать |
|--------|-------------------|
| `eleven_v3` | Экспрессивная озвучка, audio tags, эмоции |
| `eleven_multilingual_v2` | PVC, высокая схожесть голоса, мультиязычность |
| `eleven_flash_v2_5` | Низкая latency, conversational agents |

### 5.2 Настройки голоса

```python
@dataclass
class VoiceSettings:
    stability: float = 0.5          # 0.0 Creative … 1.0 Robust (v3)
    similarity_boost: float = 0.75  # для v2-моделей
    style: float = 0.0              # v2 only
    speed: float = 1.0              # 0.7–1.2
    use_speaker_boost: bool = True
```

**Рекомендации для v3 (из документации):**
- Экспрессивность + audio tags → `stability` 0.0–0.5 (Creative/Natural)
- Стабильность, минимум вариативности → `stability` 0.7–1.0 (Robust)

### 5.3 Кэшированный голос

```python
@dataclass
class CachedVoice:
    voice_id: str
    name: str
    description: str | None
    labels: dict[str, str]          # age, accent, gender, use_case, etc.
    category: str                   # premade, cloned, generated
    preview_url: str | None
    language: str | None            # если известен
    cached_at: datetime
    # метаданные для матчинга задач:
    tags: list[str] = field(default_factory=list)  # user-defined
    task_profiles: list[str] = field(default_factory=list)  # "narration", "support", etc.
```

### 5.4 Задача на озвучку

```python
@dataclass
class SynthesisTask:
    text: str
    language: str | None = None           # ISO 639-1, None = auto
    model: TTSModel | None = None
    voice_id: str | None = None           # явный выбор
    voice_description: str | None = None  # для автовыбора
    style: str | None = None              # "professional", "casual", "dramatic"
    emotion: str | None = None            # "excited", "calm", "sympathetic"
    use_case: str | None = None           # "narration", "dialogue", "announcement"
    enhance_text: bool = True             # LLM-предобработка
    normalize_text: bool = True           # нормализация чисел/дат
    voice_settings: VoiceSettings | None = None
    output_format: OutputFormat | None = None
    language_override: bool = False       # ElevenLabs language_code override
```

### 5.5 Результат

```python
@dataclass
class SynthesisResult:
    audio: bytes
    content_type: str                   # audio/mpeg
    enhanced_text: str                  # текст после LLM
    original_text: str
    voice: CachedVoice
    model: TTSModel
    voice_settings: VoiceSettings
    metadata: dict                      # duration, char_count, etc.
```

---

## 6. VoiceManager — управление голосами

### 6.1 Кэширование (diskcache)

**Namespace `voices`:**
```
cache_dir/
├── voices/           # diskcache: voice_id → CachedVoice (JSON)
├── voice_list/       # diskcache: "all_voices" → list[voice_id], TTL
├── voice_index/      # diskcache: search queries → list[voice_id]
└── enhanced_text/    # diskcache: hash(task+text) → enhanced_text (опционально)
```

### 6.2 API VoiceManager

```python
class VoiceManager:
    def sync_voices(self, *, force: bool = False) -> int:
        """Загрузить все голоса из ElevenLabs API и обновить кэш."""

    def get_voice(self, voice_id: str) -> CachedVoice | None:
        """Получить голос из кэша."""

    def list_voices(
        self,
        *,
        category: str | None = None,
        language: str | None = None,
        tags: list[str] | None = None,
    ) -> list[CachedVoice]:
        """Список кэшированных голосов с фильтрацией."""

    def search_voices(self, query: str, limit: int = 10) -> list[CachedVoice]:
        """Поиск по name, description, labels."""

    def tag_voice(self, voice_id: str, tags: list[str]) -> None:
        """Добавить пользовательские теги для матчинга задач."""

    def set_task_profiles(self, voice_id: str, profiles: list[str]) -> None:
        """Привязать голос к профилям задач."""
```

### 6.3 VoiceSelector — выбор голоса по задаче

```python
class VoiceSelector:
    def select(
        self,
        task: SynthesisTask,
        voices: list[CachedVoice],
    ) -> CachedVoice:
        """
        Алгоритм выбора (приоритет):
        1. task.voice_id — явный выбор
        2. task.voice_description — семантический/keyword match
        3. task.use_case + task.style + task.language → scoring по labels/tags
        4. fallback: default voice из конфига
        """
```

**Scoring-критерии:**
- Совпадение `labels.use_case`, `labels.accent`, `labels.gender`, `labels.age`
- Пользовательские `tags` и `task_profiles`
- Совместимость с моделью (v3 → предпочитать IVC/designed voices, не PVC)
- Язык (если указан)

**Опционально (v2):** LLM-ранжирование голосов через OpenRouter при неоднозначном выборе.

---

## 7. TextEnhancer — предобработка через OpenRouter

### 7.1 Pipeline обогащения текста

```
original_text
    │
    ├─[normalize_text=True]─→ TextNormalizer (regex/inflect)
    │                              │
    └──────────────────────────────┤
                                   ▼
                          PromptBuilder.build(task, voice, model)
                                   │
                                   ▼
                          OpenRouterClient.chat()
                                   │
                                   ▼
                          Enhanced text with [audio tags]
```

### 7.2 Стратегии промптов по модели

| Модель | Стратегия |
|--------|-----------|
| `eleven_v3` | Audio tags `[whispers]`, `[excited]`, ellipses, CAPS; **без** SSML `<break>` |
| `eleven_multilingual_v2` | Narrative context, `<break time="x.xs" />`, alias tags |
| `eleven_flash_v2_5` | Минимальная разметка + агрессивная нормализация чисел |

### 7.3 System prompt для Eleven v3

Базируется на [официальном промпте Enhance](https://elevenlabs.io/docs/overview/capabilities/text-to-speech/best-practices#prompting-eleven-v3) с расширениями:

**Core directives (из документации):**
- DO: добавлять audio tags `[laughs]`, `[whispers]`, `[sighs]`, `[excited]` и т.п.
- DO: CAPS, ellipses, пунктуация для emphasis
- DO NOT: изменять слова оригинала
- DO NOT: теги для non-vocal ([standing], [music])
- DO NOT: SSML break tags (v3 не поддерживает)

**Контекст задачи (динамически):**
```
Task context:
- Language: {language}
- Style: {style}
- Emotion: {emotion}
- Use case: {use_case}
- Voice character: {voice.name}, {voice.labels}
- Model: eleven_v3
```

**Audio tags reference (в system prompt):**
- Voice-related: `[laughs]`, `[whispers]`, `[sighs]`, `[sarcastic]`, `[curious]`, `[excited]`, `[crying]`
- Pauses: `[short pause]`, `[long pause]` (вместо SSML break)
- Sound effects (опционально): `[applause]`, `[clapping]`
- Accents: `[strong French accent]`

### 7.4 TextNormalizer

Пред-LLM нормализация (из best practices):

```python
class TextNormalizer:
    def normalize(self, text: str, language: str) -> str:
        """
        - Деньги: $42.50 → "forty-two dollars and fifty cents"
        - Телефоны: 555-555-5555 → "five five five..."
        - Даты, время, URL, аббревиатуры
        - Языко-зависимые правила
        """
```

Использует `inflect` (EN) + regex; для других языков — инструкции в LLM-промпте.

### 7.5 OpenRouterClient

```python
class OpenRouterClient:
    def enhance_text(
        self,
        text: str,
        system_prompt: str,
        *,
        model: str | None = None,  # OPENROUTER_API_TTS_PROMPT_MODEL
        temperature: float = 0.3,
    ) -> str:
        """POST /chat/completions, return content only."""
```

**Кэширование enhanced text (опционально):**
- Ключ: `hash(model + system_prompt + text + task_params)`
- TTL: `cache_ttl_enhanced_text`

---

## 8. ElevenLabsClient — генерация аудио

### 8.1 API endpoint

```
POST /v1/text-to-speech/{voice_id}
```

### 8.2 Request body

```python
@dataclass
class TTSRequest:
    text: str                           # enhanced text
    model_id: str
    voice_settings: VoiceSettings
    language_code: str | None = None    # если language_override=True
    output_format: str = "mp3_44100_128"
    optimize_streaming_latency: int | None = None
```

### 8.3 Методы клиента

```python
class ElevenLabsClient:
    def synthesize(self, voice_id: str, request: TTSRequest) -> bytes:
        """Вернуть audio bytes."""

    def list_voices(self) -> list[VoiceAPIResponse]:
        """GET /v1/voices — для sync в VoiceManager."""

    def get_voice(self, voice_id: str) -> VoiceAPIResponse:
        """GET /v1/voices/{voice_id}."""
```

---

## 9. Главный фасад SmartTTS

### 9.1 Основной API

```python
class SmartTTS:
    def __init__(self, config: SmartTTSConfig | None = None): ...

    # --- Синтез ---
    def synthesize(self, task: SynthesisTask) -> SynthesisResult:
        """
        Полный pipeline:
        1. Выбор/валидация голоса
        2. Нормализация текста
        3. LLM-обогащение (если enhance_text)
        4. Генерация TTS
        5. Возврат результата
        """

    def synthesize_to_file(
        self, task: SynthesisTask, path: Path
    ) -> SynthesisResult: ...

    # --- Голоса ---
    def sync_voices(self, force: bool = False) -> int: ...
    def list_voices(self, **filters) -> list[CachedVoice]: ...
    def get_voice(self, voice_id: str) -> CachedVoice | None: ...

    # --- Утилиты ---
    def enhance_text_only(self, task: SynthesisTask) -> str:
        """Только LLM-обогащение без TTS (для preview/debug)."""
```

### 9.2 Convenience-функции

```python
def synthesize(
    text: str,
    *,
    language: str = "ru",
    style: str = "neutral",
    voice_description: str | None = None,
    model: TTSModel = TTSModel.ELEVEN_V3,
) -> SynthesisResult:
    """One-liner для простых случаев."""
```

---

## 10. Pipeline синтеза (детально)

```
SynthesisTask
     │
     ▼
┌─────────────────────────┐
│ 1. Resolve model        │ task.model ?? config.default_model
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 2. Select voice         │ VoiceSelector.select() or explicit voice_id
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 3. Resolve voice_settings│ task ?? model-specific defaults
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 4. Normalize text       │ TextNormalizer (if normalize_text)
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 5. Enhance text (LLM)   │ PromptBuilder + OpenRouterClient
│    Skip if enhance_text │ Check enhanced_text cache
│    == False             │
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 6. Build TTSRequest     │
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 7. ElevenLabs TTS       │ ElevenLabsClient.synthesize()
└───────────┬─────────────┘
            ▼
     SynthesisResult
```

---

## 11. Обработка ошибок

```python
class SmartTTSError(Exception): ...
class VoiceNotFoundError(SmartTTSError): ...
class VoiceCacheEmptyError(SmartTTSError): ...
class TextEnhancementError(SmartTTSError): ...
class ElevenLabsAPIError(SmartTTSError):
    status_code: int
    detail: str
class OpenRouterAPIError(SmartTTSError): ...
class ModelVoiceIncompatibleError(SmartTTSError): ...
```

**Retry policy:**
- ElevenLabs 429/5xx → exponential backoff, max 3 retries
- OpenRouter 429/5xx → exponential backoff, max 2 retries
- При ошибке LLM → fallback: синтез без enhancement (с warning) или raise (configurable)

---

## 12. Логирование

```python
# structlog или stdlib logging
logger.info("voice_selected", voice_id=..., score=...)
logger.info("text_enhanced", original_len=..., enhanced_len=..., model=...)
logger.debug("enhanced_text", text=...)
logger.info("tts_complete", duration_ms=..., char_count=...)
```

---

## 13. Зависимости

```toml
[project]
dependencies = [
    "httpx>=0.27",           # HTTP-клиент (async-ready)
    "diskcache>=5.6",        # локальный кэш
    "pydantic>=2.0",         # валидация моделей (опционально)
    "inflect>=7.0",          # нормализация чисел (EN)
    "python-dotenv>=1.0",    # загрузка .env
]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "respx", "ruff"]
```

**Опционально:**
- `elevenlabs` — официальный SDK (можно обернуть или использовать httpx напрямую)
- `structlog` — structured logging

---

## 14. Структура пакета

```
elevenlabs_smart_tts/
├── __init__.py              # SmartTTS, synthesize, exports
├── config.py                # SmartTTSConfig, from_env()
├── models.py                # dataclasses/enums
├── client/
│   ├── elevenlabs.py        # ElevenLabsClient
│   └── openrouter.py        # OpenRouterClient
├── voices/
│   ├── manager.py           # VoiceManager
│   ├── selector.py          # VoiceSelector
│   └── cache.py             # CacheStore (diskcache wrapper)
├── enhancement/
│   ├── enhancer.py          # TextEnhancer
│   ├── normalizer.py        # TextNormalizer
│   └── prompts/
│       ├── v3.py            # Eleven v3 system prompt
│       ├── v2.py            # Multilingual v2 prompt
│       └── base.py          # Shared normalization instructions
├── tts.py                   # SmartTTS facade
└── exceptions.py
```

---

## 15. Примеры использования (целевой API)

```python
from elevenlabs_smart_tts import SmartTTS, SynthesisTask, TTSModel

tts = SmartTTS.from_env()
tts.sync_voices()

# Простая озвучка
result = tts.synthesize(SynthesisTask(
    text="Добро пожаловать в наш сервис поддержки.",
    language="ru",
    style="professional",
    emotion="warm",
    use_case="customer_support",
))
result.audio  # bytes
result.enhanced_text  # "[professional] Добро пожаловать..."

# Явный голос + v3
result = tts.synthesize(SynthesisTask(
    text="Are you serious? I can't believe you did that!",
    voice_id="abc123",
    model=TTSModel.ELEVEN_V3,
    style="dramatic",
    emotion="appalled",
))

# Preview обогащённого текста
enhanced = tts.enhance_text_only(SynthesisTask(
    text="Спасибо за звонок. Чем могу помочь?",
    language="ru",
    style="sympathetic",
))
# → "[sympathetic] Спасибо за звонок. [reassuring] Чем могу помочь?"

# Работа с кэшем голосов
voices = tts.list_voices(language="ru", tags=["narration"])
tts.get_voice("voice_id").task_profiles  # ["audiobook", "narration"]
```

---

## 16. Расширения (v2+)

| Функция | Описание |
|---------|----------|
| Async API | `async def synthesize(...)` |
| Multi-speaker | Разные `voice_id` для Speaker 1/2 в dialogue |
| LLM voice ranking | OpenRouter выбирает голос из shortlist |
| Voice Design integration | Создание голоса по описанию → кэш |
| Streaming TTS | WebSocket/streaming endpoint |
| Pronunciation dictionary | Загрузка `.pls` lexicon |
| Batch synthesis | Очередь задач с rate limiting |
| CLI | `smart-tts synthesize --text "..." --style professional` |

---

## 17. Ограничения и риски

1. **Eleven v3 + PVC:** PVC пока хуже работает с v3 — селектор должен предупреждать или исключать PVC для v3.
2. **Audio tags vs голос:** `[whisper]` на «громком» голосе может не сработать — LLM-промпт должен учитывать `voice.labels`.
3. **Язык v3:** auto-detect по умолчанию; override только при явном `language_override=True`.
4. **Стоимость:** каждый синтез = 1 OpenRouter call + 1 ElevenLabs call; кэш enhanced text снижает повторные затраты.
5. **LLM может нарушить directive «не менять текст»** — post-validation: diff original vs enhanced, reject при изменении слов (Levenshtein/word-level check).

---

## 18. Критерии готовности v1

- [ ] `SmartTTS.from_env()` загружает конфиг из env
- [ ] `sync_voices()` кэширует голоса в diskcache с TTL
- [ ] `list_voices()` / `get_voice()` работают offline из кэша
- [ ] `VoiceSelector` выбирает голос по `voice_description` / `use_case`
- [ ] `TextEnhancer` обогащает текст audio-тегами для v3 через OpenRouter
- [ ] `TextNormalizer` нормализует числа/даты для EN (минимум)
- [ ] `synthesize()` возвращает audio + enhanced_text + metadata
- [ ] Retry и typed exceptions для API errors
- [ ] Unit-тесты с mocked httpx (respx)

---

Спецификация описывает полный контракт библиотеки без реализации. Если нужно, могу детализировать отдельные разделы — промпты для OpenRouter, схему scoring в `VoiceSelector` или формат diskcache.