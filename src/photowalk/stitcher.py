"""Stitch video segments and image clips into a single output video."""

import subprocess
import tempfile
from pathlib import Path
from typing import List

from photowalk.image_clip import generate_image_clip
from photowalk.timeline import TimelineEntry, TimelineMap


def _compute_draft_resolution(width: int, height: int) -> tuple[int, int]:
    """Scale resolution proportionally so it fits within 1280x720.

    Output dimensions are rounded down to the nearest even number so they
    are always valid inputs for libx264 (which requires even width and height).
    """
    max_w, max_h = 1280, 720
    scale = min(max_w / width, max_h / height, 1.0)
    w = int(width * scale)
    h = int(height * scale)
    return (w // 2) * 2, (h // 2) * 2


def build_concat_list(entries: List[TimelineEntry], output_path: Path) -> Path:
    """Write an ffmpeg concat demuxer list file.

    Each entry is a pre-rendered clip with its own embedded duration, so we
    emit one `file` line per entry — no `duration` directives, no trailing
    duplicate (those are only needed when concatenating still-image inputs).
    """
    lines = []
    for entry in entries:
        path = entry.clip_path or entry.source_path
        lines.append(f"file '{path.resolve()}'")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n")
    return output_path


def run_concat(concat_list_path: Path, output_path: Path) -> bool:
    """Run ffmpeg concat demuxer."""
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_path),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found in PATH. Install FFmpeg: https://ffmpeg.org")
    return result.returncode == 0


def _split_video_segment(
    video_path: Path,
    trim_start: float,
    trim_end: float,
    output_path: Path,
    frame_width: int,
    frame_height: int,
) -> bool:
    """Extract a segment from a video using ffmpeg trim.

    Re-encodes instead of -c copy to ensure frame-accurate cuts at
    non-keyframe boundaries.
    """
    duration = trim_end - trim_start
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(trim_start),
        "-i", str(video_path),
        "-t", str(duration),
        "-vf", f"scale={frame_width}:{frame_height}:force_original_aspect_ratio=decrease,pad={frame_width}:{frame_height}:(ow-iw)/2:(oh-ih)/2:white",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "48000",
        "-r", "30",
        "-video_track_timescale", "15360",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found in PATH. Install FFmpeg: https://ffmpeg.org")
    return result.returncode == 0


def stitch(
    timeline_map: TimelineMap,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    image_duration: float = 3.5,
    keep_temp: bool = False,
) -> bool:
    """Stitch all segments into a single output video."""
    temp_dir = Path(tempfile.mkdtemp(prefix="photowalk_stitch_"))
    try:
        # Generate image clips and split video segments
        for entry in timeline_map.all_entries:
            if entry.kind == "image":
                clip_path = temp_dir / f"img_{entry.source_path.stem}.mp4"
                ok = generate_image_clip(
                    entry.source_path,
                    clip_path,
                    frame_width,
                    frame_height,
                    image_duration,
                )
                if not ok:
                    return False
                entry.clip_path = clip_path
                entry.duration_seconds = image_duration
            elif entry.kind == "video_segment":
                seg_path = temp_dir / f"seg_{entry.trim_start:.3f}_{entry.source_path.stem}.mp4"
                ok = _split_video_segment(
                    entry.source_path,
                    entry.trim_start or 0.0,
                    entry.trim_end or 0.0,
                    seg_path,
                    frame_width,
                    frame_height,
                )
                if not ok:
                    return False
                entry.clip_path = seg_path

        concat_list_path = temp_dir / "concat_list.txt"
        build_concat_list(timeline_map.all_entries, concat_list_path)
        ok = run_concat(concat_list_path, output_path)
        return ok
    finally:
        if keep_temp:
            print(f"Temp files preserved at: {temp_dir}")
        else:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
