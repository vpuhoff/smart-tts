from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any

from smart_tts.models import OutputFormat, SynthesisTask, TTSModel, VoiceSettings


@dataclass
class GenerationTemplate:
    """Полный рецепт генерации: речь, фон, сведение."""

    name: str = "default"

    # Речь (Fish Audio)
    voice_id: str | None = None
    model: TTSModel | None = None
    language: str | None = None
    style: str | None = None
    emotion: str | None = None
    use_case: str | None = None
    enhance_text: bool = True
    normalize_text: bool = True
    voice_settings: VoiceSettings | None = None
    output_format: OutputFormat | None = None

    # Фон
    music_prompt: str | None = None
    ambient_prompt: str | None = None
    music_path: Path | str | None = None
    ambient_path: Path | str | None = None

    # Сведение (ffmpeg)
    music_volume: float = 0.32
    ambient_volume: float = 0.18
    speech_volume: float = 1.0
    bed_weight: float = 0.68
    mix_default: bool = False

    def with_overrides(self, **kwargs: Any) -> GenerationTemplate:
        return replace(self, **kwargs)

    def to_task(self, text: str, *, mix: bool = True, **overrides: Any) -> SynthesisTask:
        """Собрать SynthesisTask из шаблона и текста."""
        data: dict[str, Any] = {
            "text": text,
            "language": self.language,
            "model": self.model,
            "voice_id": self.voice_id,
            "style": self.style,
            "emotion": self.emotion,
            "use_case": self.use_case,
            "enhance_text": self.enhance_text,
            "normalize_text": self.normalize_text,
            "voice_settings": self.voice_settings,
            "output_format": self.output_format,
            "music_prompt": self.music_prompt,
            "ambient_prompt": self.ambient_prompt,
            "music_path": self.music_path,
            "ambient_path": self.ambient_path,
            "music_volume": self.music_volume,
            "ambient_volume": self.ambient_volume,
            "speech_volume": self.speech_volume,
            "bed_weight": self.bed_weight,
        }
        data.update(overrides)

        if not mix:
            data["music_prompt"] = None
            data["ambient_prompt"] = None
            data["music_path"] = None
            data["ambient_path"] = None

        task_fields = {f.name for f in fields(SynthesisTask)}
        return SynthesisTask(**{k: v for k, v in data.items() if k in task_fields})

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.model is not None:
            data["model"] = self.model.value
        if self.output_format is not None:
            data["output_format"] = self.output_format.value
        if self.voice_settings is not None:
            data["voice_settings"] = asdict(self.voice_settings)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> GenerationTemplate:
        payload = dict(data)
        if "model" in payload and payload["model"] is not None:
            payload["model"] = TTSModel(payload["model"])
        if "output_format" in payload and payload["output_format"] is not None:
            payload["output_format"] = OutputFormat(payload["output_format"])
        if vs := payload.get("voice_settings"):
            if isinstance(vs, Mapping):
                payload["voice_settings"] = VoiceSettings(**dict(vs))
        template_fields = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in payload.items() if k in template_fields})

    @classmethod
    def from_json_file(cls, path: str | Path) -> GenerationTemplate:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @property
    def has_mix_sources(self) -> bool:
        return bool(
            self.music_prompt or self.ambient_prompt or self.music_path or self.ambient_path
        )


INVESTIGATION = GenerationTemplate(
    name="investigation",
    voice_id="67d37d81cb7340b391e9461d6671de03",
    model=TTSModel.ELEVEN_V3,
    language="ru",
    style="serious",
    emotion="serious",
    use_case="investigation",
    voice_settings=VoiceSettings(temperature=0.7, speed=1.0),
    music_prompt=(
        "Melancholic retro crime drama soundtrack, sad vintage piano, slow mournful cello, "
        "1980s nostalgic thriller atmosphere, dramatic pauses, deep emotional sorrow, "
        "cold ambient, instrumental, no vocals, classic television documentary."
    ),
    ambient_prompt=(
        "Subtle old radio receiver hum, faint tape hiss, quiet surveillance room tone, "
        "very low, seamless loop, noir detective atmosphere"
    ),
    music_volume=0.32,
    ambient_volume=0.18,
    speech_volume=1.0,
    bed_weight=0.68,
    mix_default=True,
)

BUILTIN_TEMPLATES: dict[str, GenerationTemplate] = {
    "investigation": INVESTIGATION,
    "default": GenerationTemplate(),
}

BUILTIN_TEMPLATE_DESCRIPTIONS: dict[str, str] = {
    "investigation": "Noir detective narration with music and ambient beds.",
    "default": "Minimal speech-only defaults.",
}


def get_template(name: str) -> GenerationTemplate:
    try:
        return BUILTIN_TEMPLATES[name]
    except KeyError as exc:
        known = ", ".join(sorted(BUILTIN_TEMPLATES))
        raise KeyError(f"Unknown template {name!r}. Known: {known}") from exc
