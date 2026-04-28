"""Generate white-background video clips from photos."""

import subprocess
from pathlib import Path
from typing import Tuple

from PIL import Image


def compute_scaled_dimensions(
    img_width: int, img_height: int, frame_width: int, frame_height: int
) -> Tuple[int, int]:
    """Scale image to fit within frame while preserving aspect ratio."""
    scale_w = frame_width / img_width
    scale_h = frame_height / img_height
    scale = min(scale_w, scale_h)
    return int(img_width * scale), int(img_height * scale)


def generate_image_clip(
    image_path: Path,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    duration: float = 3.5,
) -> bool:
    """Generate a video clip with white background and centered image."""
    try:
        with Image.open(image_path) as img:
            img_width, img_height = img.size
    except Exception:
        return False

    scaled_w, scaled_h = compute_scaled_dimensions(img_width, img_height, frame_width, frame_height)
    x_offset = (frame_width - scaled_w) // 2
    y_offset = (frame_height - scaled_h) // 2

    filter_str = (
        f"color=c=white:s={frame_width}x{frame_height}:d={duration}[bg];"
        f"[bg][0:v]overlay={x_offset}:{y_offset}:enable='between(t,0,{duration})'"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-vf", filter_str,
        "-c:v", "libx264",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        "-an",
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found in PATH. Install FFmpeg: https://ffmpeg.org")

    return result.returncode == 0
