"""Write corrected timestamps back to photo and video files."""

import os
import subprocess
from datetime import datetime
from pathlib import Path

import piexif


def _format_exif_datetime(dt: datetime) -> bytes:
    """Format a datetime as EXIF DateTime string: '2024:07:15 14:32:10'."""
    return dt.strftime("%Y:%m:%d %H:%M:%S").encode("ascii")


def write_photo_timestamp(path: Path, new_timestamp: datetime) -> bool:
    """Write DateTimeOriginal EXIF tag via piexif. Returns True on success."""
    try:
        exif_dict = piexif.load(str(path))
    except Exception:
        return False

    dt_bytes = _format_exif_datetime(new_timestamp)

    # Ensure Exif IFD exists
    if "Exif" not in exif_dict:
        exif_dict["Exif"] = {}

    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = dt_bytes
    exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = dt_bytes

    # Also update IFD0 DateTime as fallback
    if "0th" not in exif_dict:
        exif_dict["0th"] = {}
    exif_dict["0th"][piexif.ImageIFD.DateTime] = dt_bytes

    try:
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, str(path))
        return True
    except Exception:
        return False


def write_video_timestamp(path: Path, new_timestamp: datetime) -> bool:
    """Write creation_time metadata via ffmpeg -c copy. Returns True on success."""
    temp_path = path.parent / (path.stem + ".tmp" + path.suffix)
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(path),
        "-c", "copy",
        "-metadata", f'creation_time={new_timestamp.isoformat()}',
        str(temp_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False

    if result.returncode != 0:
        # Clean up temp file if it exists
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False

    # Atomic swap
    os.replace(temp_path, path)
    return True
