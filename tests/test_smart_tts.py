from __future__ import annotations

import httpx
import respx

from smart_tts.models import SynthesisTask, TTSModel
from smart_tts.tts import SmartTTS
from smart_tts.voices.registry import VoiceRegistry


@respx.mock
def test_smart_tts_end_to_end(config, sample_voice, tmp_path) -> None:
    respx.post("https://api.fish.audio/v1/tts").mock(
        return_value=httpx.Response(200, content=b"mp3-data")
    )

    registry = VoiceRegistry(config)
    registry.register_voice(sample_voice)

    with SmartTTS(config) as tts:
        tts._registry = registry
        result = tts.synthesize(
            SynthesisTask(
                text='Центр, <break time="1.2s" /> на связи.',
                language="ru",
                style="serious",
                emotion="warm",
                use_case="investigation",
                voice_id=sample_voice.voice_id,
            )
        )
        output_path = tmp_path / "out.mp3"
        file_result = tts.synthesize_to_file(
            SynthesisTask(
                text="Добро пожаловать.",
                language="ru",
                voice_id=sample_voice.voice_id,
                enhance_text=False,
            ),
            output_path,
        )
        enhanced = tts.enhance_text_only(
            SynthesisTask(
                text='Центр, <break time="1.2s" /> на связи.',
                language="ru",
                emotion="warm",
                voice_id=sample_voice.voice_id,
            )
        )

    assert result.audio == b"mp3-data"
    assert "[long pause]" in result.enhanced_text
    assert result.voice.voice_id == sample_voice.voice_id
    assert result.model == TTSModel.ELEVEN_V3
    assert file_result.audio == b"mp3-data"
    assert output_path.read_bytes() == b"mp3-data"
    assert "[warm]" in enhanced
    assert "[long pause]" in enhanced


def test_list_voices_offline_from_cache(config, sample_voice) -> None:
    registry = VoiceRegistry(config)
    registry.register_voice(sample_voice)

    with SmartTTS(config) as tts:
        tts._registry = registry
        voices = tts.list_voices(language="ru")
        voice = tts.get_voice(sample_voice.voice_id)

    assert len(voices) == 1
    assert voice is not None
    assert voice.voice_id == sample_voice.voice_id
