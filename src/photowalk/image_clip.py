"""Generate white-background video clips from photos."""

import threading
from pathlib import Path
from typing import Tuple

from PIL import Image

from photowalk.ffmpeg_config import (
    FfmpegEncodeConfig,
    build_scale_pad_filter,
    _run_ffmpeg_cmd,
)


def compute_scaled_dimensions(
    img_width: int, img_height: int, frame_width: int, frame_height: int, margin: float = 15.0
) -> Tuple[int, int]:
    """Scale image to fit within the frame with the given margin percentage.

    Args:
        margin: White space percentage on each side (default 15%).
                The photo fills (100 - 2*margin)% of the frame.
    """
    fill_percent = 1.0 - (2 * margin / 100.0)
    available_width = frame_width * fill_percent
    available_height = frame_height * fill_percent

    scale_w = available_width / img_width
    scale_h = available_height / img_height
    scale = min(scale_w, scale_h)
    return int(img_width * scale), int(img_height * scale)


def generate_image_clip(
    image_path: Path,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    duration: float = 3.5,
    encode_config: FfmpegEncodeConfig | None = None,
    margin: float = 15.0,
    cancel_event: threading.Event | None = None,
) -> bool:
    """Generate a video clip with white background and centered image.

    Args:
        margin: White space percentage on each side (default 15%).
        cancel_event: If set, abort before or during ffmpeg execution.
    """
    if cancel_event is not None and cancel_event.is_set():
        return False

    try:
        with Image.open(image_path) as img:
            img_width, img_height = img.size
    except Exception:
        return False

    scaled_w, scaled_h = compute_scaled_dimensions(img_width, img_height, frame_width, frame_height, margin)

    if encode_config is None:
        encode_config = FfmpegEncodeConfig()

    # Scale the image first, then overlay centered using ffmpeg expressions
    filter_str = (
        f"color=c=white:s={frame_width}x{frame_height}:d={duration}[bg];"
        f"[0:v]scale={scaled_w}:{scaled_h}[img];"
        f"[bg][img]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2:enable='between(t,0,{duration})'"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-framerate", str(encode_config.fps),
        "-i", str(image_path),
        "-f", "lavfi",
        "-i", f"anullsrc=channel_layout=stereo:sample_rate={encode_config.audio_sample_rate}",
        "-vf", filter_str,
        "-c:v", "libx264",
        "-preset", encode_config.preset,
        "-crf", str(encode_config.crf),
        "-c:a", "aac",
        "-b:a", encode_config.audio_bitrate,
        "-ar", str(encode_config.audio_sample_rate),
        "-r", str(encode_config.fps),
        "-video_track_timescale", str(encode_config.video_track_timescale),
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(output_path),
    ]

    return _run_ffmpeg_cmd(cmd, cancel_event=cancel_event)
