"""Shared serializer for the per-file dict shape returned by web endpoints.

Single source of truth for /api/files, the preview response, and the
apply response.  Earlier the same shape was duplicated across server.py
and sync_preview.py; keep new fields in one place.
"""

from pathlib import Path

from photowalk.models import PhotoMetadata, VideoMetadata


def metadata_to_file_entry(
    path: Path,
    meta: "PhotoMetadata | VideoMetadata",
    *,
    shifted: bool = False,
) -> dict:
    if isinstance(meta, PhotoMetadata):
        return {
            "path": str(path),
            "type": "photo",
            "timestamp": meta.timestamp.isoformat() if meta.timestamp else None,
            "duration_seconds": None,
            "has_timestamp": meta.timestamp is not None,
            "shifted": shifted,
        }
    return {
        "path": str(path),
        "type": "video",
        "timestamp": (
            meta.start_timestamp.isoformat() if meta.start_timestamp else None
        ),
        "duration_seconds": meta.duration_seconds,
        "has_timestamp": meta.start_timestamp is not None,
        "shifted": shifted,
    }
