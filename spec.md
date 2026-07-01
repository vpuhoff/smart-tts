# Спецификация библиотеки smart-tts

## 1. Обзор

**Название:** `smart-tts` (пакет `smart_tts`)

**Назначение:** Python-библиотека высокого уровня для производства озвучки: речь через Fish Audio, фоновая музыка и эмбиент через ElevenLabs, сведение слоёв через ffmpeg.

**Ключевая идея:** пользователь передаёт текст (с опциональными SSML-паузами `<break>`) и контекст задачи — библиотека подготавливает текст под Fish Audio paralanguage, синтезирует речь одним непрерывным проходом и при необходимости сводит музыку и эмбиент.

**Референсная реализация:** [`example.py`](example.py) — радиодонесение «Следствие ведут…».

---

## 2. Цели и не-цели

### Цели
- Единый интерфейс `SmartTTS.synthesize(task)` → `SynthesisResult`
- Fish Audio S2.1 Pro — один непрерывный TTS-проход (без склейки фраз)
- Конвертация SSML `<break time="Xs"/>` → Fish S2-теги `[pause]` / `[long pause]`
- ElevenLabs Music API и Sound Effects API для фоновых дорожек
- ffmpeg-сведение речи + музыка + эмбиент (`mix_tracks`)
- Sync и async API с одинаковыми сигнатурами
- Локальный реестр голосов Fish (`reference_id`) в `diskcache`

### Не-цели
- ElevenLabs TTS / OpenRouter LLM-enhancement (удалены в текущей версии)
- Создание голосов Fish Audio
- Streaming TTS
- Web UI

---

## 3. Архитектура

```
┌──────────────────────────────────────────────────────────────┐
│                     SmartTTS (фасад)                         │
│  synthesize(task) → SynthesisResult                          │
└──────────┬───────────────────────────────┬─────────────────┘
           │                               │
  ┌────────▼────────┐              ┌───────▼────────────┐
  │   FishClient    │              │ ElevenLabsBedsClient│
  │  (речь, httpx)  │              │ (музыка + эмбиент)  │
  └────────┬────────┘              └───────┬────────────┘
           │                               │
  ┌────────▼────────┐              ┌───────▼────────┐
  │  prepare_text   │              │  mix_tracks    │
  │  script/breaks  │              │  ffmpeg        │
  └─────────────────┘              └────────────────┘
```

### Компоненты

| Компонент | Ответственность |
|-----------|-----------------|
| `SmartTTS` / `AsyncSmartTTS` | Оркестрация pipeline |
| `FishClient` | POST `api.fish.audio/v1/tts` |
| `ElevenLabsBedsClient` | `music.compose`, `text_to_sound_effects` |
| `prepare_text` | SSML breaks + emotion prefix |
| `VoiceRegistry` | Кэш `reference_id` в diskcache |
| `mix_tracks` | Сведение дорожек через ffmpeg |

---

## 4. Конфигурация

### Переменные окружения

| Переменная | Обязательна | По умолчанию | Описание |
|------------|-------------|--------------|----------|
| `FISH_API_KEY` | да | — | API-ключ Fish Audio |
| `ELEVENLABS_API_KEY` | нет | — | Для генерации музыки/эмбиента |
| `FISH_DEFAULT_MODEL` | нет | `s2.1-pro` | Модель Fish по умолчанию |
| `FISH_DEFAULT_VOICE_ID` | нет | Kanevsky ref | `reference_id` по умолчанию |
| `FISH_API_URL` | нет | `https://api.fish.audio/v1/tts` | Endpoint TTS |
| `ELEVENLABS_CACHE_DIR` | нет | `~/.cache/smart-tts` | Кэш реестра голосов |
| `ELEVENLABS_DEFAULT_OUTPUT_FORMAT` | нет | `mp3_44100_128` | Формат выхода |

### Объект конфигурации

```python
@dataclass
class SmartTTSConfig:
    fish_api_key: str
    elevenlabs_api_key: str | None = None
    cache_dir: Path = Path("~/.cache/smart-tts")
    default_model: TTSModel = TTSModel.ELEVEN_V3  # → s2.1-pro
    default_output_format: OutputFormat = OutputFormat.MP3_44100_128
    default_voice_settings: VoiceSettings = field(default_factory=VoiceSettings)
    default_voice_id: str | None = "67d37d81cb7340b391e9461d6671de03"
    fish_api_url: str = "https://api.fish.audio/v1/tts"
    cache_ttl_voices: int = 86400
```

---

## 5. Модели данных

### 5.1 TTSModel (маппинг на Fish Audio)

Имена enum сохранены для обратной совместимости API:

```python
class TTSModel(str, Enum):
    ELEVEN_V3 = "s2.1-pro"           # fallback → s2.1-pro-free при 402
    ELEVEN_MULTILINGUAL_V2 = "s2-pro"
    ELEVEN_FLASH_V2_5 = "s1"
```

### 5.2 VoiceSettings (Fish API)

```python
@dataclass
class VoiceSettings:
    stability: float = 0.5          # legacy, не отправляется в Fish
    similarity_boost: float = 0.75  # legacy
    style: float = 0.0              # legacy
    speed: float = 1.0              # prosody.speed
    use_speaker_boost: bool = True  # legacy
    temperature: float = 0.7
    top_p: float = 0.7
    repetition_penalty: float = 1.2
```

### 5.3 SynthesisTask

```python
@dataclass
class SynthesisTask:
    text: str
    language: str | None = None
    model: TTSModel | None = None
    voice_id: str | None = None           # Fish reference_id
    voice_description: str | None = None
    style: str | None = None
    emotion: str | None = None            # → paralanguage prefix
    use_case: str | None = None
    enhance_text: bool = True             # breaks + emotion
    normalize_text: bool = True           # legacy flag
    voice_settings: VoiceSettings | None = None
    output_format: OutputFormat | None = None
    language_override: bool = False       # legacy
    # Сведение слоёв:
    music_prompt: str | None = None
    ambient_prompt: str | None = None
    music_path: Path | str | None = None
    ambient_path: Path | str | None = None
    music_volume: float = 0.32
    ambient_volume: float = 0.18
    speech_volume: float = 1.0
    bed_weight: float = 0.68
```

### 5.4 SynthesisResult

```python
@dataclass
class SynthesisResult:
    audio: bytes                        # речь или сведённый микс
    content_type: str
    enhanced_text: str                  # подготовленный текст для Fish
    original_text: str
    voice: CachedVoice
    model: TTSModel
    voice_settings: VoiceSettings
    metadata: dict                      # duration_ms, mixed, music, ambient
```

---

## 6. Подготовка текста

### 6.1 SSML breaks → Fish S2 tags

| Пауза (сек) | Тег |
|-------------|-----|
| ≥ 1.2 | `[long pause]` |
| ≥ 0.75 | `[pause]` |
| ≥ 0.4 | `...` |

Пример:

```
Вход:  'Центр, <break time="1.2s" /> на связи.'
Выход: 'Центр, [long pause] на связи.'
```

> **Важно:** для S2/S2.1 используются `[квадратные скобки]`. Синтаксис `(soft tone)` и прочий произвольный текст в круглых скобках модель может **озвучить вслух**.

### 6.2 Emotion tags (S2/S2.1)

| emotion | Тег |
|---------|-----|
| warm | `[warm]` |
| serious | `[serious]` |
| excited | `[excited]` |
| sad | `[sad]` |
| whisper | `[whisper]` |
| calm | `[calm]` |

### 6.3 enhance_text_only

Возвращает подготовленный текст без вызова Fish API — для preview и отладки.

---

## 7. FishClient — синтез речи

### Endpoint

```
POST https://api.fish.audio/v1/tts
Header: model: s2.1-pro
```

### Payload (ключевые поля)

```python
{
    "text": "<prepared text>",
    "reference_id": "<voice_id>",
    "format": "mp3",
    "mp3_bitrate": 128,
    "sample_rate": 44100,
    "normalize": True,
    "latency": "normal",
    "temperature": 0.7,
    "top_p": 0.7,
    "repetition_penalty": 1.2,
    "condition_on_previous_chunks": True,
    "prosody": {"speed": 1.0, "volume": 0},
}
```

### Fallback

При HTTP 402 на `s2.1-pro` — повтор с `s2.1-pro-free`.

---

## 8. ElevenLabsBedsClient — фоновые дорожки

Не используется для TTS. Только:

| Метод SDK | Назначение |
|-----------|------------|
| `client.music.compose()` | Инструментальная музыка по промпту |
| `client.text_to_sound_effects.convert()` | Эмбиент, loop |

При `missing_permissions` / `subscription_required` — тихий пропуск (возврат `False`).

При `bad_prompt` на музыке — fallback-промпт noir strings.

---

## 9. Сведение (mix_tracks)

Требует `ffmpeg` и `ffprobe` в PATH.

Алгоритм (из `example_cinematic.py` / `example.py`):

1. Фоновые дорожки зацикливаются (`-stream_loop -1`)
2. Fade in/out на музыке
3. `amix` с `normalize=0` и `weights=1 {bed_weight}` — речь доминирует

Параметры по умолчанию (как в детективном примере):

- `music_volume=0.32`
- `ambient_volume=0.18`
- `bed_weight=0.68`

---

## 10. VoiceRegistry

Fish Audio не предоставляет публичный list-voices API как ElevenLabs. Реестр хранит известные `reference_id`:

```python
registry.sync_voices()       # регистрирует default_voice_id
registry.register_voice(v)   # добавить свой голос
registry.list_voices()       # из кэша
registry.get_voice(id)
registry.resolve_voice(task) # voice_id из task или default
```

Кэш: `diskcache` в `{ELEVENLABS_CACHE_DIR}/voices/`.

---

## 11. Pipeline синтеза

```
SynthesisTask
     │
     ▼
┌─────────────────────────┐
│ 1. Resolve model        │ task.model ?? config.default_model
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 2. Resolve voice        │ VoiceRegistry.resolve_voice()
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 3. Prepare text         │ prepare_text() if enhance_text
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 4. Fish TTS             │ FishClient.synthesize()
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 5. Mix layers (opt.)    │ if music/ambient prompts or paths
│    ElevenLabs beds +    │
│    mix_tracks           │
└───────────┬─────────────┘
            ▼
     SynthesisResult
```

---

## 12. Обработка ошибок

```python
class SmartTTSError(Exception): ...
class VoiceNotFoundError(SmartTTSError): ...
class VoiceCacheEmptyError(SmartTTSError): ...
class TextEnhancementError(SmartTTSError): ...
class FishAPIError(SmartTTSError): ...
class ElevenLabsAPIError(SmartTTSError): ...
class AudioMixError(SmartTTSError): ...
```

---

## 13. Зависимости

```toml
dependencies = [
    "elevenlabs>=2.0",
    "httpx>=0.27",
    "diskcache>=5.6",
    "python-dotenv>=1.0",
]
```

Внешние утилиты: `ffmpeg`, `ffprobe` (для сведения).

---

## 14. Структура пакета

```
smart_tts/
├── __init__.py
├── config.py
├── models.py
├── tts.py                   # SmartTTS
├── async_tts.py             # AsyncSmartTTS
├── text.py                  # prepare_text
├── exceptions.py
├── client/
│   ├── fish.py              # FishClient, AsyncFishClient
│   └── elevenlabs.py        # ElevenLabsBedsClient
├── script/
│   └── breaks.py            # parse_break_script, script_to_fish_text
├── audio/
│   ├── mixer.py             # mix_tracks, collect_chunks
│   └── probe.py             # audio_duration_seconds, require_tool
└── voices/
    └── registry.py          # VoiceRegistry
```

---

## 15. Примеры

### Простая озвучка

```python
from smart_tts import SmartTTS, SynthesisTask

with SmartTTS.from_env() as tts:
    result = tts.synthesize(SynthesisTask(
        text="Срочное донесение.",
        voice_id="67d37d81cb7340b391e9461d6671de03",
        emotion="serious",
    ))
```

### С паузами и сведением

```python
result = tts.synthesize(SynthesisTask(
    text='Центр, <break time="1.2s" /> на связи.',
    voice_id="67d37d81cb7340b391e9461d6671de03",
    music_prompt="Melancholic noir piano, instrumental",
    ambient_prompt="Radio hum, tape hiss, loop",
    music_volume=0.32,
    ambient_volume=0.18,
))
```

### Демо-скрипт

```bash
uv run python example.py
uv run python example.py --variants 2
uv run python example.py --remix-only --music back.mp3 --no-ambient
```

---

## 16. Критерии готовности

- [x] `SmartTTS.from_env()` загружает конфиг из env
- [x] `FishClient` синтезирует речь, fallback на free-модель
- [x] SSML breaks конвертируются в Fish paralanguage
- [x] `synthesize()` с `music_prompt` / `ambient_prompt` сводит слои
- [x] `mix_tracks` через ffmpeg
- [x] Sync и async API
- [x] Unit-тесты с respx (mock Fish API)

---

## 17. История изменений

| Версия | Изменение |
|--------|-----------|
| v1 (legacy) | ElevenLabs TTS + OpenRouter LLM enhancement |
| v2 (текущая) | Fish Audio speech + ElevenLabs beds + ffmpeg mix |

Публичные сигнатуры `SmartTTS.synthesize()`, `SynthesisTask`, `SynthesisResult` сохранены.
