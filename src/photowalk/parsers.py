"""Parse ffprobe JSON output into typed metadata models."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from photowalk.models import PhotoMetadata, VideoMetadata


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp string into a datetime."""
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _get_tag(data: dict, *keys: str) -> Optional[str]:
    """Walk into ffprobe format.tags and return the first matching key."""
    tags = data.get("format", {}).get("tags") or {}
    for key in keys:
        if key in tags:
            return tags[key]
    return None


def parse_photo(path: Path, data: dict) -> PhotoMetadata:
    """Parse ffprobe JSON into PhotoMetadata."""
    tags = data.get("format", {}).get("tags") or {}

    timestamp = _parse_timestamp(_get_tag(data, "creation_time", "date"))

    make = tags.get("Make", "")
    model = tags.get("Model", "")
    camera_model = None
    if make or model:
        camera_model = " ".join(part for part in [make, model] if part).strip() or None

    shutter_speed = _get_tag(data, "ExposureTime", "ShutterSpeedValue")

    iso_raw = _get_tag(data, "ISOSpeedRatings", "ISO")
    iso = None
    if iso_raw:
        try:
            iso = int(iso_raw)
        except ValueError:
            iso = None

    focal_length = _get_tag(data, "FocalLength")

    return PhotoMetadata(
        source_path=path,
        timestamp=timestamp,
        camera_model=camera_model,
        shutter_speed=shutter_speed,
        iso=iso,
        focal_length=focal_length,
    )


def parse_video(path: Path, data: dict) -> VideoMetadata:
    """Parse ffprobe JSON into VideoMetadata."""
    fmt = data.get("format", {})
    tags = fmt.get("tags") or {}

    start_timestamp = _parse_timestamp(tags.get("creation_time"))

    duration = None
    duration_raw = fmt.get("duration")
    if duration_raw is None:
        streams = data.get("streams", [])
        if streams:
            duration_raw = streams[0].get("duration")
    if duration_raw is not None:
        try:
            duration = float(duration_raw)
        except ValueError:
            duration = None

    end_timestamp = None
    if start_timestamp is not None and duration is not None:
        end_timestamp = start_timestamp + timedelta(seconds=duration)

    return VideoMetadata(
        source_path=path,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        duration_seconds=duration,
    )
