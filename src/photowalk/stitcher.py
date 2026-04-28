"""Stitch video segments and image clips into a single output video."""

import subprocess
import tempfile
from pathlib import Path
from typing import List

from photowalk.image_clip import generate_image_clip
from photowalk.timeline import TimelineEntry, TimelineMap


def build_concat_list(entries: List[TimelineEntry], output_path: Path) -> Path:
    """Write an ffmpeg concat demuxer list file."""
    lines = []
    for entry in entries:
        path = entry.clip_path or entry.source_path
        lines.append(f"file '{path.resolve()}'")
        lines.append(f"duration {entry.duration_seconds}")
    # ffmpeg concat demuxer requires a final file line without duration
    if entries:
        last_path = entries[-1].clip_path or entries[-1].source_path
        lines.append(f"file '{last_path.resolve()}'")

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
) -> bool:
    """Extract a segment from a video using ffmpeg trim."""
    duration = trim_end - trim_start
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(trim_start),
        "-i", str(video_path),
        "-t", str(duration),
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
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
                )
                if not ok:
                    return False
                entry.clip_path = seg_path

        concat_list_path = temp_dir / "concat_list.txt"
        build_concat_list(timeline_map.all_entries, concat_list_path)
        ok = run_concat(concat_list_path, output_path)
        return ok
    finally:
        if not keep_temp:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
