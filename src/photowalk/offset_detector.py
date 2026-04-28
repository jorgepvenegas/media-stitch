"""Detect temporal offset between original and trimmed videos via audio cross-correlation."""

import subprocess
import tempfile
from pathlib import Path


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
