from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from smart_tts.audio.probe import audio_duration_seconds, require_tool
from smart_tts.exceptions import AudioMixError


def _export_speech_only(speech: Path, output: Path, *, speech_volume: float, output_bitrate: str) -> None:
    if speech_volume == 1.0:
        shutil.copy2(speech, output)
        return
    require_tool("ffmpeg")
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(speech),
            "-af",
            f"volume={speech_volume}",
            "-c:a",
            "libmp3lame",
            "-b:a",
            output_bitrate,
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AudioMixError(result.stderr or "ffmpeg speech gain failed")


def mix_tracks(
    speech: Path,
    output: Path,
    *,
    music: Path | None = None,
    ambient: Path | None = None,
    speech_volume: float = 1.0,
    music_volume: float = 0.40,
    ambient_volume: float = 0.30,
    bed_weight: float = 0.75,
    output_bitrate: str = "192k",
) -> None:
    """Свести речь + фоновые дорожки (weights + normalize=0, без sidechain)."""
    if music is None and ambient is None:
        _export_speech_only(speech, output, speech_volume=speech_volume, output_bitrate=output_bitrate)
        return

    require_tool("ffmpeg")
    duration = audio_duration_seconds(speech)
    fade_out_start = max(0.0, duration - 2.0)
    speech_weight = speech_volume

    if music is not None and ambient is not None:
        filter_complex = (
            f"[1]volume={music_volume},afade=t=in:st=0:d=2,"
            f"afade=t=out:st={fade_out_start:.3f}:d=2[m];"
            f"[2]volume={ambient_volume},afade=t=in:st=0:d=1.5[a];"
            "[m][a]amix=inputs=2:duration=longest:normalize=0[bed];"
            f"[0][bed]amix=inputs=2:duration=first:normalize=0:weights={speech_weight} {bed_weight}[out]"
        )
        inputs = [
            "-i",
            str(speech),
            "-stream_loop",
            "-1",
            "-i",
            str(music),
            "-stream_loop",
            "-1",
            "-i",
            str(ambient),
        ]
    elif music is not None:
        filter_complex = (
            f"[1]volume={music_volume},afade=t=in:st=0:d=2,"
            f"afade=t=out:st={fade_out_start:.3f}:d=2[m];"
            f"[0][m]amix=inputs=2:duration=first:normalize=0:weights={speech_weight} {bed_weight}[out]"
        )
        inputs = ["-i", str(speech), "-stream_loop", "-1", "-i", str(music)]
    else:
        assert ambient is not None
        filter_complex = (
            f"[1]volume={ambient_volume},afade=t=in:st=0:d=1.5[a];"
            f"[0][a]amix=inputs=2:duration=first:normalize=0:weights={speech_weight} {bed_weight}[out]"
        )
        inputs = ["-i", str(speech), "-stream_loop", "-1", "-i", str(ambient)]

    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-c:a",
            "libmp3lame",
            "-b:a",
            output_bitrate,
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AudioMixError(result.stderr or "ffmpeg mix failed")


def collect_chunks(chunks) -> bytes:
    return b"".join(chunk for chunk in chunks if isinstance(chunk, bytes))
