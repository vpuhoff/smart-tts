from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from smart_tts.audio.mixer import mix_tracks
from smart_tts.audio.probe import audio_duration_seconds
from smart_tts.client.elevenlabs import ElevenLabsBedsClient
from smart_tts.client.fish import FishClient
from smart_tts.config import SmartTTSConfig
from smart_tts.models import (
    CONTENT_TYPE_BY_FORMAT,
    CachedVoice,
    SynthesisResult,
    SynthesisTask,
    TTSModel,
)
from smart_tts.templates import GenerationTemplate
from smart_tts.telemetry import set_span_attributes, span, task_attributes
from smart_tts.text import prepare_text
from smart_tts.voices.registry import VoiceRegistry

logger = logging.getLogger(__name__)


def _needs_mix(task: SynthesisTask) -> bool:
    return bool(task.music_prompt or task.ambient_prompt or task.music_path or task.ambient_path)


def _resolve_path(value: Path | str | None) -> Path | None:
    if value is None:
        return None
    return Path(value).expanduser().resolve()


class SmartTTS:
    def __init__(self, config: SmartTTSConfig) -> None:
        self._config = config
        self._registry = VoiceRegistry(config)
        self._fish = FishClient(config)

    @classmethod
    def from_env(cls, *, dotenv_path: str | Path | None = None) -> SmartTTS:
        return cls(SmartTTSConfig.from_env(dotenv_path=dotenv_path))

    def close(self) -> None:
        self._fish.close()

    def __enter__(self) -> SmartTTS:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def synthesize(self, task: SynthesisTask) -> SynthesisResult:
        with span("smart_tts.synthesize", **task_attributes(task)) as root_span:
            started = time.perf_counter()
            model = task.model or self._config.default_model
            output_format = task.output_format or self._config.default_output_format
            voice_settings = task.voice_settings or self._config.default_voice_settings

            voices = self._registry.list_voices()
            if not voices:
                self.sync_voices(force=True)
            voice = self._registry.resolve_voice(task)

            prepared_text = prepare_text(task) if task.enhance_text else task.text.strip()
            speech_audio, fish_model = self._fish.synthesize(
                prepared_text,
                voice_id=voice.voice_id,
                model=model,
                voice_settings=voice_settings,
                output_format=output_format,
            )

            mixed = False
            music_used = False
            ambient_used = False
            if _needs_mix(task):
                speech_audio, music_used, ambient_used = self._mix_layers(task, speech_audio)
                mixed = music_used or ambient_used

            duration_ms = int((time.perf_counter() - started) * 1000)
            content_type = CONTENT_TYPE_BY_FORMAT.get(output_format.value, "audio/mpeg")

            set_span_attributes(
                root_span,
                {
                    "smart_tts.fish_model": fish_model,
                    "smart_tts.prepared_char_count": len(prepared_text),
                    "smart_tts.audio_bytes": len(speech_audio),
                    "smart_tts.duration_ms": duration_ms,
                    "smart_tts.mixed": mixed,
                    "smart_tts.music": music_used,
                    "smart_tts.ambient": ambient_used,
                },
            )

            logger.info(
                "tts_complete",
                extra={
                    "duration_ms": duration_ms,
                    "char_count": len(prepared_text),
                    "voice_id": voice.voice_id,
                    "model": model.value,
                    "fish_model": fish_model,
                    "mixed": mixed,
                },
            )

            return SynthesisResult(
                audio=speech_audio,
                content_type=content_type,
                enhanced_text=prepared_text,
                original_text=task.text,
                voice=voice,
                model=model,
                voice_settings=voice_settings,
                metadata={
                    "duration_ms": duration_ms,
                    "char_count": len(prepared_text),
                    "voice_id": voice.voice_id,
                    "model": model.value,
                    "fish_model": fish_model,
                    "mixed": music_used or ambient_used,
                    "music": music_used,
                    "ambient": ambient_used,
                },
            )

    def _mix_layers(self, task: SynthesisTask, speech_audio: bytes) -> tuple[bytes, bool, bool]:
        with span("smart_tts.mix_layers", **task_attributes(task)):
            with tempfile.TemporaryDirectory(prefix="smart-tts-") as tmp:
                tmp_dir = Path(tmp)
                speech_path = tmp_dir / "speech.mp3"
                final_path = tmp_dir / "final.mp3"
                speech_path.write_bytes(speech_audio)
                duration = audio_duration_seconds(speech_path)

                music_path = _resolve_path(task.music_path)
                ambient_path = _resolve_path(task.ambient_path)
                music_ok = music_path is not None and music_path.is_file()
                ambient_ok = ambient_path is not None and ambient_path.is_file()

                beds_client: ElevenLabsBedsClient | None = None
                if (task.music_prompt and not music_ok) or (task.ambient_prompt and not ambient_ok):
                    if not self._config.elevenlabs_api_key:
                        logger.warning("mix_skipped_no_elevenlabs_key")
                    else:
                        beds_client = ElevenLabsBedsClient(self._config)

                try:
                    if task.music_prompt and not music_ok and beds_client is not None:
                        generated = tmp_dir / "music.mp3"
                        music_ok = beds_client.generate_music(
                            generated,
                            prompt=task.music_prompt,
                            duration_ms=int(duration * 1000),
                        )
                        if music_ok:
                            music_path = generated

                    if task.ambient_prompt and not ambient_ok and beds_client is not None:
                        generated = tmp_dir / "ambient.mp3"
                        ambient_ok = beds_client.generate_ambient(
                            generated,
                            prompt=task.ambient_prompt,
                            duration_seconds=min(duration, 30.0),
                        )
                        if ambient_ok:
                            ambient_path = generated

                    if music_ok or ambient_ok:
                        mix_tracks(
                            speech_path,
                            final_path,
                            music=music_path if music_ok else None,
                            ambient=ambient_path if ambient_ok else None,
                            music_volume=task.music_volume,
                            ambient_volume=task.ambient_volume,
                            speech_volume=task.speech_volume,
                            bed_weight=task.bed_weight,
                        )
                        return final_path.read_bytes(), music_ok, ambient_ok
                finally:
                    if beds_client is not None:
                        beds_client.close()

        return speech_audio, False, False

    def synthesize_to_file(self, task: SynthesisTask, path: Path) -> SynthesisResult:
        result = self.synthesize(task)
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(result.audio)
        return result

    def synthesize_text(
        self,
        text: str,
        template: GenerationTemplate,
        *,
        mix: bool = True,
        **overrides: Any,
    ) -> SynthesisResult:
        """Синтез по шаблону: все настройки из template, текст передаётся отдельно."""
        with span("smart_tts.synthesize_text", template=template.name, mix=mix):
            return self.synthesize(template.to_task(text, mix=mix, **overrides))

    def synthesize_text_to_file(
        self,
        text: str,
        template: GenerationTemplate,
        path: Path,
        *,
        mix: bool = True,
        **overrides: Any,
    ) -> SynthesisResult:
        return self.synthesize_to_file(template.to_task(text, mix=mix, **overrides), path)

    def remix_file(
        self,
        speech_path: Path,
        output_path: Path,
        template: GenerationTemplate,
        *,
        generate_music: bool | None = None,
        generate_ambient: bool | None = None,
    ) -> None:
        """Свести готовую речь с фоном по настройкам шаблона."""
        with span(
            "smart_tts.remix_file",
            template=template.name,
            speech_path=str(speech_path),
            output_path=str(output_path),
        ):
            from smart_tts.client.elevenlabs import ElevenLabsBedsClient

            duration = audio_duration_seconds(speech_path)
            music_path = _resolve_path(template.music_path)
            ambient_path = _resolve_path(template.ambient_path)
            music_ok = music_path is not None and music_path.is_file()
            ambient_ok = ambient_path is not None and ambient_path.is_file()

            want_music = generate_music if generate_music is not None else bool(template.music_prompt)
            want_ambient = generate_ambient if generate_ambient is not None else bool(template.ambient_prompt)

            beds_client: ElevenLabsBedsClient | None = None
            if self._config.elevenlabs_api_key and (
                (want_music and not music_ok) or (want_ambient and not ambient_ok)
            ):
                beds_client = ElevenLabsBedsClient(self._config)

            try:
                if want_music and not music_ok and beds_client is not None and template.music_prompt:
                    generated = output_path.parent / f"{template.name}_music.mp3"
                    music_ok = beds_client.generate_music(
                        generated,
                        prompt=template.music_prompt,
                        duration_ms=int(duration * 1000),
                    )
                    if music_ok:
                        music_path = generated

                if want_ambient and not ambient_ok and beds_client is not None and template.ambient_prompt:
                    generated = output_path.parent / f"{template.name}_ambient.mp3"
                    ambient_ok = beds_client.generate_ambient(
                        generated,
                        prompt=template.ambient_prompt,
                        duration_seconds=min(duration, 30.0),
                    )
                    if ambient_ok:
                        ambient_path = generated

                if music_ok or ambient_ok:
                    mix_tracks(
                        speech_path,
                        output_path,
                        music=music_path if music_ok else None,
                        ambient=ambient_path if ambient_ok else None,
                        speech_volume=template.speech_volume,
                        music_volume=template.music_volume,
                        ambient_volume=template.ambient_volume,
                        bed_weight=template.bed_weight,
                    )
                else:
                    mix_tracks(speech_path, output_path, speech_volume=template.speech_volume)
            finally:
                if beds_client is not None:
                    beds_client.close()

    def sync_voices(self, force: bool = False) -> int:
        return self._registry.sync_voices(force=force)

    def list_voices(
        self,
        *,
        category: str | None = None,
        language: str | None = None,
        tags: list[str] | None = None,
    ) -> list[CachedVoice]:
        return self._registry.list_voices(
            category=category,
            language=language,
            tags=tags,
        )

    def get_voice(self, voice_id: str) -> CachedVoice | None:
        return self._registry.get_voice(voice_id)

    def enhance_text_only(self, task: SynthesisTask) -> str:
        return prepare_text(task) if task.enhance_text else task.text.strip()


def synthesize_with_template(
    text: str,
    template: GenerationTemplate,
    *,
    mix: bool = True,
    config: SmartTTSConfig | None = None,
    **overrides: Any,
) -> SynthesisResult:
    tts = SmartTTS(config or SmartTTSConfig.from_env())
    try:
        return tts.synthesize_text(text, template, mix=mix, **overrides)
    finally:
        tts.close()


def synthesize(
    text: str,
    *,
    language: str = "ru",
    style: str = "neutral",
    voice_description: str | None = None,
    model: TTSModel = TTSModel.ELEVEN_V3,
    config: SmartTTSConfig | None = None,
) -> SynthesisResult:
    tts = SmartTTS(config or SmartTTSConfig.from_env())
    try:
        return tts.synthesize(
            SynthesisTask(
                text=text,
                language=language,
                style=style,
                voice_description=voice_description,
                model=model,
            )
        )
    finally:
        tts.close()
