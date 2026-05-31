from __future__ import annotations

import httpx
import respx

from elevenlabs_smart_tts.models import SynthesisTask, TTSModel
from elevenlabs_smart_tts.tts import SmartTTS
from elevenlabs_smart_tts.voices.cache import CacheStore


@respx.mock
def test_smart_tts_end_to_end(config, sample_voice, default_voice, tmp_path) -> None:
    respx.get("https://api.elevenlabs.io/v1/voices").mock(
        return_value=httpx.Response(
            200,
            json={
                "voices": [
                    {
                        "voice_id": sample_voice.voice_id,
                        "name": sample_voice.name,
                        "description": sample_voice.description,
                        "labels": sample_voice.labels,
                        "category": sample_voice.category,
                    },
                    {
                        "voice_id": default_voice.voice_id,
                        "name": default_voice.name,
                        "description": default_voice.description,
                        "labels": default_voice.labels,
                        "category": default_voice.category,
                    },
                ]
            },
        )
    )
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "[warm] Добро пожаловать в наш сервис поддержки."
                        }
                    }
                ]
            },
        )
    )
    respx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{sample_voice.voice_id}"
    ).mock(return_value=httpx.Response(200, content=b"mp3-data"))

    with SmartTTS(config) as tts:
        tts.sync_voices(force=True)
        result = tts.synthesize(
            SynthesisTask(
                text="Добро пожаловать в наш сервис поддержки.",
                language="ru",
                style="professional",
                emotion="warm",
                use_case="customer_support",
                voice_description="professional support",
            )
        )
        output_path = tmp_path / "out.mp3"
        file_result = tts.synthesize_to_file(
            SynthesisTask(
                text="Добро пожаловать в наш сервис поддержки.",
                language="ru",
                voice_id=sample_voice.voice_id,
                enhance_text=False,
            ),
            output_path,
        )
        enhanced = tts.enhance_text_only(
            SynthesisTask(
                text="Добро пожаловать в наш сервис поддержки.",
                language="ru",
                voice_id=sample_voice.voice_id,
            )
        )

    assert result.audio == b"mp3-data"
    assert result.enhanced_text.startswith("[warm]")
    assert result.voice.voice_id == sample_voice.voice_id
    assert result.model == TTSModel.ELEVEN_V3
    assert result.metadata["char_count"] == len(result.enhanced_text)
    assert file_result.audio == b"mp3-data"
    assert output_path.read_bytes() == b"mp3-data"
    assert enhanced.startswith("[warm]")


def test_list_voices_offline_from_cache(config, sample_voice) -> None:
    cache = CacheStore(config.cache_dir)
    cache.set_voice(sample_voice)
    cache.set_voice_ids([sample_voice.voice_id], ttl=3600)

    with SmartTTS(config) as tts:
        voices = tts.list_voices(language="ru")
        voice = tts.get_voice(sample_voice.voice_id)

    assert len(voices) == 1
    assert voice is not None
    assert voice.voice_id == sample_voice.voice_id
