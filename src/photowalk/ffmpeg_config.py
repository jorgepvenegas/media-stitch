"""Shared ffmpeg encoding configuration and helpers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FfmpegEncodeConfig:
    """Encoding parameters for ffmpeg video output."""

    preset: str = "fast"
    crf: int = 23
    fps: int = 30
    audio_bitrate: str = "128k"
    audio_sample_rate: int = 48000
    video_track_timescale: int = 15360

    @classmethod
    def draft(cls) -> "FfmpegEncodeConfig":
        """Return a draft-quality config for faster preview renders."""
        return cls(preset="ultrafast", crf=28)


def ffmpeg_not_found_error() -> str:
    """Return a standard error message for missing ffmpeg/ffprobe."""
    return "ffmpeg not found in PATH. Install FFmpeg: https://ffmpeg.org"


def build_scale_pad_filter(
    frame_width: int, frame_height: int, pad_color: str = "white"
) -> str:
    """Build an ffmpeg scale+pad filter that fits video into frame with padding."""
    return (
        f"scale={frame_width}:{frame_height}:force_original_aspect_ratio=decrease,"
        f"pad={frame_width}:{frame_height}:(ow-iw)/2:(oh-ih)/2:{pad_color}"
    )
