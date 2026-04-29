"""Apply pending offsets by writing new timestamps to disk."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.timeline import MediaInput
from photowalk.web.sync_models import OffsetEntry
from photowalk.web.sync_preview import compute_net_deltas


WriterFn = Callable[[Path, datetime], bool]


def _current_timestamp(meta) -> datetime | None:
    if isinstance(meta, PhotoMetadata):
        return meta.timestamp
    if isinstance(meta, VideoMetadata):
        return meta.start_timestamp
    return None


def apply_offsets(
    pairs: list[MediaInput],
    offsets: list[OffsetEntry],
    *,
    write_photo: WriterFn,
    write_video: WriterFn,
) -> dict:
    """Write shifted timestamps to disk, one path at a time.

    Returns { "applied": [...], "failed": [...] }.  Per-file errors do
    not abort the batch.
    """
    deltas = compute_net_deltas(offsets)
    pairs_by_path = {str(p): (p, m) for p, m in pairs}

    applied: list[dict] = []
    failed: list[dict] = []

    for path_str, delta in deltas.items():
        if path_str not in pairs_by_path:
            failed.append({"path": path_str, "error": "Path not in scan set"})
            continue

        path, meta = pairs_by_path[path_str]
        old_ts = _current_timestamp(meta)
        if old_ts is None:
            continue  # silently skip — UI shouldn't allow selecting these

        new_ts = old_ts + timedelta(seconds=delta)
        writer = write_photo if isinstance(meta, PhotoMetadata) else write_video

        try:
            ok = writer(path, new_ts)
        except Exception as e:
            failed.append({"path": path_str, "error": str(e)})
            continue

        if ok:
            applied.append({
                "path": path_str,
                "old_ts": old_ts.isoformat(),
                "new_ts": new_ts.isoformat(),
            })
        else:
            failed.append({"path": path_str, "error": "Writer returned False"})

    return {"applied": applied, "failed": failed}
