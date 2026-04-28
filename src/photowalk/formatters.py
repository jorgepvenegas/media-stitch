"""Format metadata and preview data for CLI output."""

from datetime import timedelta, datetime
from pathlib import Path
from typing import Optional, Union

from photowalk.models import PhotoMetadata, VideoMetadata


def format_table(results: list[PhotoMetadata | VideoMetadata]) -> str:
    """Format metadata results as an aligned text table."""
    lines = []
    lines.append(f"{'File':<40} {'Type':<8} {'Timestamp':<25} {'Details'}")
    lines.append("-" * 100)
    for r in results:
        name = str(r.source_path)[:39]
        if isinstance(r, PhotoMetadata):
            ts = r.timestamp.isoformat() if r.timestamp else "N/A"
            details = f"{r.camera_model or 'N/A'} | ISO {r.iso or 'N/A'} | {r.focal_length or 'N/A'}"
            lines.append(f"{name:<40} {'photo':<8} {ts:<25} {details}")
        else:
            start = r.start_timestamp.isoformat() if r.start_timestamp else "N/A"
            end = r.end_timestamp.isoformat() if r.end_timestamp else "N/A"
            dur = f"{r.duration_seconds:.1f}s" if r.duration_seconds else "N/A"
            lines.append(f"{name:<40} {'video':<8} {start:<25} end={end} dur={dur}")
    return "\n".join(lines)


def format_csv(results: list[PhotoMetadata | VideoMetadata]) -> str:
    """Format metadata results as CSV."""
    lines = ["source_path,media_type,timestamp,camera_model,shutter_speed,iso,focal_length,start_timestamp,end_timestamp,duration_seconds"]
    for r in results:
        d = r.to_dict()
        lines.append(
            f'"{d["source_path"]}",{d["media_type"]},'
            f'"{d.get("timestamp") or ""}","{d.get("camera_model") or ""}",'
            f'"{d.get("shutter_speed") or ""}",{d.get("iso") or ""},'
            f'"{d.get("focal_length") or ""}","{d.get("start_timestamp") or ""}",'
            f'"{d.get("end_timestamp") or ""}",{d.get("duration_seconds") or ""}'
        )
    return "\n".join(lines)


def format_timedelta(td: timedelta) -> str:
    """Format a timedelta as a human-readable string like '-8h 23m 5s'."""
    total_seconds = int(td.total_seconds())
    sign = "-" if total_seconds < 0 else "+"
    total_seconds = abs(total_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds:
        parts.append(f"{seconds}s")
    return sign + " ".join(parts) if parts else "0s"


# Type alias for sync preview entries: (path, current_ts, new_ts, skip_reason)
SyncPreviewEntry = tuple[Path, Optional[datetime], Optional[datetime], Optional[str]]


def format_sync_preview(
    preview: list[SyncPreviewEntry], delta: timedelta
) -> str:
    """Format the sync command's preview table."""
    lines = []
    lines.append(f"{'File':<40} {'Current Timestamp':<30} {'New Timestamp':<30} {'Delta'}")
    lines.append("-" * 120)
    for f, current, new_time, reason in preview:
        name = str(f)[:39]
        if reason:
            lines.append(f"{name:<40} {'N/A':<30} {'N/A':<30} {reason}")
        else:
            cur_str = current.isoformat() if current else "N/A"
            new_str = new_time.isoformat() if new_time else "N/A"
            lines.append(f"{name:<40} {cur_str:<30} {new_str:<30} {format_timedelta(delta)}")
    return "\n".join(lines)


def format_timeline(
    entries: list,
    image_duration: float,
) -> str:
    """Format a timeline's entries as an aligned text table.

    Args:
        entries: List of TimelineEntry objects.
        image_duration: Duration to display for image entries.
    """
    lines = [f"{'Start':<25} {'Duration':<10} {'Type':<15} {'Source'}"]
    lines.append("-" * 90)
    for entry in entries:
        start = entry.start_time.isoformat() if entry.start_time else "N/A"
        name = str(entry.source_path.name)[:40]
        dur = image_duration if entry.kind == "image" else entry.duration_seconds
        lines.append(f"{start:<25} {dur:<10.1f} {entry.kind:<15} {name}")
    return "\n".join(lines)
