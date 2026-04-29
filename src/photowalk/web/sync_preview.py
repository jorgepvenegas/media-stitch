"""Preview-side logic: compute shifted timelines without touching disk."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.timeline import MediaInput, build_timeline
from photowalk.web.file_entry import metadata_to_file_entry
from photowalk.web.sync_models import OffsetEntry


def compute_net_deltas(offsets: list[OffsetEntry]) -> dict[str, float]:
    """Sum delta_seconds per path across the offset stack.

    Paths with a zero net delta are omitted from the result.
    """
    totals: dict[str, float] = {}
    for entry in offsets:
        for path in entry.target_paths:
            totals[path] = totals.get(path, 0.0) + entry.delta_seconds
    return {p: d for p, d in totals.items() if d != 0.0}


def shift_pairs(
    pairs: list[MediaInput],
    deltas_by_path: dict[str, float],
) -> tuple[list[MediaInput], set[str]]:
    """Return new (path, meta) pairs with timestamps shifted per delta map.

    Files with no timestamp, or paths absent from the delta map, are
    returned with their metadata unchanged.  The original pairs and
    metadata objects are not mutated (PhotoMetadata / VideoMetadata are
    frozen dataclasses; we use dataclasses.replace).

    Returns the new pairs list plus the set of path strings that were
    actually shifted (non-zero delta and a usable timestamp).
    """
    new_pairs: list[MediaInput] = []
    shifted: set[str] = set()

    for path, meta in pairs:
        delta = deltas_by_path.get(str(path), 0.0)

        if delta == 0.0:
            new_pairs.append((path, meta))
            continue

        td = timedelta(seconds=delta)

        if isinstance(meta, PhotoMetadata):
            if meta.timestamp is None:
                new_pairs.append((path, meta))
                continue
            new_meta = replace(meta, timestamp=meta.timestamp + td)
            new_pairs.append((path, new_meta))
            shifted.add(str(path))

        elif isinstance(meta, VideoMetadata):
            if meta.start_timestamp is None:
                new_pairs.append((path, meta))
                continue
            new_start = meta.start_timestamp + td
            new_end = meta.end_timestamp + td if meta.end_timestamp else None
            new_meta = replace(
                meta,
                start_timestamp=new_start,
                end_timestamp=new_end,
            )
            new_pairs.append((path, new_meta))
            shifted.add(str(path))
        else:
            new_pairs.append((path, meta))

    return new_pairs, shifted


def _serialize_entry(entry) -> dict:
    """Mirror the serialization in server.api_timeline."""
    data = {
        "kind": entry.kind,
        "source_path": str(entry.source_path),
        "start_time": entry.start_time.isoformat() if entry.start_time else None,
        "duration_seconds": entry.duration_seconds,
    }
    if entry.kind == "video_segment":
        data["trim_start"] = entry.trim_start
        data["trim_end"] = entry.trim_end
        data["original_video"] = (
            str(entry.original_video) if entry.original_video else None
        )
    return data


def build_preview(
    pairs: list[MediaInput],
    offsets: list[OffsetEntry],
    *,
    image_duration: float,
) -> dict:
    """Return the response shape for POST /api/timeline/preview."""
    deltas = compute_net_deltas(offsets)
    shifted_pairs, shifted_paths = shift_pairs(pairs, deltas)

    timeline = build_timeline(shifted_pairs)
    entries = [_serialize_entry(e) for e in timeline.all_entries]
    files = [
        metadata_to_file_entry(p, m, shifted=str(p) in shifted_paths)
        for p, m in sorted(shifted_pairs, key=lambda pm: str(pm[0]))
    ]
    return {
        "entries": entries,
        "settings": {"image_duration": image_duration},
        "files": files,
    }
