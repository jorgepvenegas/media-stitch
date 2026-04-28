"""Detect temporal offset between original and trimmed videos via audio cross-correlation."""

import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np


class OffsetDetectionError(Exception):
    """Raised when offset detection fails for any reason."""


def extract_audio(path: Path) -> Path:
    """Extract the first audio track to a temporary 16kHz mono WAV file via ffmpeg.

    Returns the path to the temporary WAV. The caller is responsible for cleanup.
    Raises OffsetDetectionError on ffmpeg failure.
    """
    temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp.close()
    temp_path = Path(temp.name)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(temp_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        temp_path.unlink(missing_ok=True)
        raise OffsetDetectionError(
            f"Failed to extract audio from {path}: {result.stderr}"
        )

    return temp_path


def _load_audio(path: Path) -> tuple[np.ndarray, int]:
    """Load a WAV file as a mono float32 numpy array and return (array, sample_rate)."""
    with wave.open(str(path), "rb") as wf:
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        nframes = wf.getnframes()
        data = wf.readframes(nframes)

        if sampwidth == 2:
            arr = np.frombuffer(data, dtype=np.int16)
        else:
            raise OffsetDetectionError(f"Unsupported sample width: {sampwidth}")

        if nchannels > 1:
            arr = arr.reshape(-1, nchannels).mean(axis=1)

        return arr.astype(np.float32), framerate
