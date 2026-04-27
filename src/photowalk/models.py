"""Typed data models for photo and video metadata."""

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


def _serialize(value):
    """Serialize model values for JSON output."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


@dataclass(frozen=True)
class PhotoMetadata:
    source_path: Path
    media_type: str = "photo"
    timestamp: Optional[datetime] = None
    camera_model: Optional[str] = None
    shutter_speed: Optional[str] = None
    iso: Optional[int] = None
    focal_length: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: _serialize(v) for k, v in asdict(self).items()}


@dataclass(frozen=True)
class VideoMetadata:
    source_path: Path
    media_type: str = "video"
    start_timestamp: Optional[datetime] = None
    end_timestamp: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    def to_dict(self) -> dict:
        return {k: _serialize(v) for k, v in asdict(self).items()}
