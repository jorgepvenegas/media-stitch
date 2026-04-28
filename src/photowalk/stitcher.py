"""Stitch video segments and image clips into a single output video."""

import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import List

from PIL import Image

from photowalk.ffmpeg_config import (
    FfmpegEncodeConfig,
    build_scale_pad_filter,
    ffmpeg_not_found_error,
)
from photowalk.image_clip import compute_scaled_dimensions, generate_image_clip
from photowalk.timeline import TimelineEntry, TimelineMap


def compute_draft_resolution(width: int, height: int) -> tuple[int, int]:
    """Scale resolution proportionally so it fits within 1280x720.

    Output dimensions are rounded down to the nearest even number so they
    are always valid inputs for libx264 (which requires even width and height).
    """
    max_w, max_h = 1280, 720
    scale = min(max_w / width, max_h / height, 1.0)
    w = int(width * scale)
    h = int(height * scale)
    return (w // 2) * 2, (h // 2) * 2


def _resolve_encode_config(draft: bool) -> FfmpegEncodeConfig:
    """Return the appropriate encoding config for draft or final quality."""
    return FfmpegEncodeConfig.draft() if draft else FfmpegEncodeConfig()


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


def run_concat(concat_list_path: Path, output_path: Path, encode_config: FfmpegEncodeConfig | None = None) -> bool:
    """Run ffmpeg concat demuxer."""
    if encode_config is None:
        encode_config = FfmpegEncodeConfig()
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_path),
        "-c:v", "libx264",
        "-preset", encode_config.preset,
        "-crf", str(encode_config.crf),
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise RuntimeError(ffmpeg_not_found_error())
    return result.returncode == 0


def _split_video_segment(
    video_path: Path,
    trim_start: float,
    trim_end: float,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    encode_config: FfmpegEncodeConfig | None = None,
) -> bool:
    """Extract a segment from a video using ffmpeg trim.

    Re-encodes instead of -c copy to ensure frame-accurate cuts at
    non-keyframe boundaries.
    """
    if encode_config is None:
        encode_config = FfmpegEncodeConfig()
    duration = trim_end - trim_start
    vf = build_scale_pad_filter(frame_width, frame_height)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(trim_start),
        "-i", str(video_path),
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", encode_config.preset,
        "-crf", str(encode_config.crf),
        "-c:a", "aac",
        "-b:a", encode_config.audio_bitrate,
        "-ar", str(encode_config.audio_sample_rate),
        "-r", str(encode_config.fps),
        "-video_track_timescale", str(encode_config.video_track_timescale),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise RuntimeError(ffmpeg_not_found_error())
    return result.returncode == 0


def generate_plan(
    timeline_map: TimelineMap,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    image_duration: float = 3.5,
    draft: bool = False,
    margin: float = 15.0,
) -> dict:
    """Generate a plan dict describing how stitch() would process the timeline."""
    encode_config = _resolve_encode_config(draft)
    if draft:
        frame_width, frame_height = compute_draft_resolution(frame_width, frame_height)
    temp_dir = Path(tempfile.gettempdir()) / f"photowalk_stitch_{uuid.uuid4().hex[:8]}"
    timeline_entries = []
    ffmpeg_commands = []

    for entry in timeline_map.all_entries:
        if entry.kind == "image":
            clip_path = temp_dir / f"img_{entry.source_path.stem}.mp4"
            # Use placeholder dimensions if image cannot be read (for testing)
            try:
                with Image.open(entry.source_path) as img:
                    img_width, img_height = img.size
            except Exception:
                img_width, img_height = frame_width, frame_height
            scaled_w, scaled_h = compute_scaled_dimensions(
                img_width, img_height, frame_width, frame_height, margin
            )
            vf = (
                f"color=c=white:s={frame_width}x{frame_height}:d={image_duration}[bg];"
                f"[0:v]scale={scaled_w}:{scaled_h}[img];"
                f"[bg][img]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2:enable='between(t,0,{image_duration})'"
            )
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", str(entry.source_path.resolve()),
                "-f", "lavfi",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-t", str(image_duration),
                "-vf", vf,
                "-c:v", "libx264",
                "-preset", encode_config.preset,
                "-crf", str(encode_config.crf),
                "-c:a", "aac",
                "-b:a", encode_config.audio_bitrate,
                "-ar", str(encode_config.audio_sample_rate),
                "-r", str(encode_config.fps),
                "-video_track_timescale", str(encode_config.video_track_timescale),
                "-pix_fmt", "yuv420p",
                "-shortest",
                str(clip_path),
            ]
            ffmpeg_commands.append({
                "step": "image_clip",
                "source": str(entry.source_path),
                "output": str(clip_path),
                "command": cmd,
            })
            timeline_entries.append({
                "start_time": entry.start_time.isoformat(),
                "duration": image_duration,
                "kind": "image",
                "source": str(entry.source_path),
                "original_video": None,
                "trim_start": None,
                "trim_end": None,
            })

        elif entry.kind == "video_segment":
            seg_path = temp_dir / f"seg_{entry.trim_start:.3f}_{entry.source_path.stem}.mp4"
            duration = (entry.trim_end or 0) - (entry.trim_start or 0)
            vf = build_scale_pad_filter(frame_width, frame_height)
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(entry.trim_start or 0.0),
                "-i", str(entry.source_path.resolve()),
                "-t", str(duration),
                "-vf", vf,
                "-c:v", "libx264",
                "-preset", encode_config.preset,
                "-crf", str(encode_config.crf),
                "-c:a", "aac",
                "-b:a", encode_config.audio_bitrate,
                "-ar", str(encode_config.audio_sample_rate),
                "-r", str(encode_config.fps),
                "-video_track_timescale", str(encode_config.video_track_timescale),
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(seg_path),
            ]
            ffmpeg_commands.append({
                "step": "video_segment",
                "source": str(entry.source_path),
                "output": str(seg_path),
                "command": cmd,
            })
            timeline_entries.append({
                "start_time": entry.start_time.isoformat(),
                "duration": entry.duration_seconds,
                "kind": "video_segment",
                "source": str(entry.source_path),
                "original_video": str(entry.original_video) if entry.original_video else None,
                "trim_start": entry.trim_start,
                "trim_end": entry.trim_end,
            })

    # Build concat command
    concat_list_path = temp_dir / "concat_list.txt"
    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_path),
        "-c:v", "libx264",
        "-preset", encode_config.preset,
        "-crf", str(encode_config.crf),
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]
    ffmpeg_commands.append({
        "step": "concat",
        "input": str(concat_list_path),
        "output": str(output_path),
        "command": concat_cmd,
    })

    return {
        "settings": {
            "output": str(output_path),
            "resolution": [frame_width, frame_height],
            "image_duration": image_duration,
            "draft": draft,
            "margin": margin,
        },
        "timeline": timeline_entries,
        "temp_dir": str(temp_dir),
        "ffmpeg_commands": ffmpeg_commands,
    }


def stitch(
    timeline_map: TimelineMap,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    image_duration: float = 3.5,
    keep_temp: bool = False,
    draft: bool = False,
    margin: float = 15.0,
) -> bool:
    """Stitch all segments into a single output video."""
    temp_dir = Path(tempfile.mkdtemp(prefix="photowalk_stitch_"))
    encode_config = _resolve_encode_config(draft)
    if draft:
        frame_width, frame_height = compute_draft_resolution(frame_width, frame_height)
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
                    encode_config=encode_config,
                    margin=margin,
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
                    encode_config=encode_config,
                )
                if not ok:
                    return False
                entry.clip_path = seg_path

        concat_list_path = temp_dir / "concat_list.txt"
        build_concat_list(timeline_map.all_entries, concat_list_path)
        ok = run_concat(concat_list_path, output_path, encode_config=encode_config)
        return ok
    finally:
        if keep_temp:
            print(f"Temp files preserved at: {temp_dir}")
        else:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
