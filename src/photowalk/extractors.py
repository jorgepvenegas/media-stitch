"""Low-level ffprobe subprocess wrappers."""

import json
import subprocess
from pathlib import Path
from typing import Optional


def ffprobe_not_found_error() -> str:
    return "ffprobe not found in PATH. Install FFmpeg: https://ffmpeg.org"


def run_ffprobe(path: Path) -> Optional[dict]:
    """Run ffprobe on a file and return parsed JSON, or None on failure."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        raise RuntimeError(ffprobe_not_found_error())

    if result.returncode != 0:
        return None

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
