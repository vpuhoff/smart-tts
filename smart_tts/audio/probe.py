from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from smart_tts.exceptions import AudioMixError


def require_tool(name: str) -> None:
    if not shutil.which(name):
        raise AudioMixError(f"Required tool not found in PATH: {name}")


def audio_duration_seconds(path: Path) -> float:
    require_tool("ffprobe")
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())
