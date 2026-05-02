"""Sync use-case: preview and execute timestamp offsets."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from photowalk.catalog import MediaCatalog
from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.timeline import MediaInput, TimelineMap, build_timeline
from photowalk.web.file_entry import metadata_to_file_entry
from photowalk.writers import write_photo_timestamp, write_video_timestamp


WriterFn = Callable[[Path, datetime], bool]


@dataclass(frozen=True)
class SyncPreviewEntry:
    path: Path
    current: Optional[datetime]
    new: Optional[datetime]
    skip_reason: Optional[str]


@dataclass(frozen=True)
class SyncPreview:
    entries: list[dict]
    files: list[dict]
    settings: dict
    shifted_paths: set[str]
    timeline_map: TimelineMap | None = None


@dataclass(frozen=True)
class SyncApplyResult:
    applied: list[dict]
    failed: list[dict]
    catalog: MediaCatalog
    preview: SyncPreview


class CancelledError(Exception):
    """Raised when user cancels the sync operation."""


class SyncUseCase:
    @staticmethod
    def compute_net_deltas(offsets: list) -> dict[str, float]:
        """Sum delta_seconds per path across the offset stack.

        Accepts any iterable of objects with ``delta_seconds`` and
        ``target_paths`` attributes (e.g. ``OffsetEntry``).
        """
        totals: dict[str, float] = {}
        for entry in offsets:
            for path in entry.target_paths:
                totals[path] = totals.get(path, 0.0) + entry.delta_seconds
        return {p: d for p, d in totals.items() if d != 0.0}

    @staticmethod
    def shift_pairs(
        catalog: MediaCatalog,
        deltas: dict[str, float],
    ) -> tuple[list[MediaInput], set[str]]:
        """Return new (path, meta) pairs with timestamps shifted per delta map.

        Files with no timestamp, or paths absent from the delta map, are
        returned unchanged.  The original pairs and metadata objects are not
        mutated.
        """
        new_pairs: list[MediaInput] = []
        shifted: set[str] = set()

        for path, meta in catalog.pairs:
            delta = deltas.get(str(path), 0.0)
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

    @staticmethod
    def _serialize_timeline_entry(entry) -> dict:
        data = {
            "kind": entry.kind,
            "source_path": str(entry.source_path),
            "start_time": entry.start_time.isoformat() if entry.start_time else None,
            "duration_seconds": entry.duration_seconds,
        }
        if entry.kind == "video_segment":
            data["trim_start"] = entry.trim_start
            data["trim_end"] = entry.trim_end
        return data

    def build_preview(
        self,
        catalog: MediaCatalog,
        deltas: dict[str, float],
        *,
        image_duration: float = 3.5,
    ) -> SyncPreview:
        """Return the response shape for a projected timeline preview."""
        shifted_pairs, shifted_paths = self.shift_pairs(catalog, deltas)
        timeline = build_timeline(shifted_pairs)
        entries = [self._serialize_timeline_entry(e) for e in timeline.all_entries]
        files = [
            metadata_to_file_entry(p, m, shifted=str(p) in shifted_paths)
            for p, m in sorted(shifted_pairs, key=lambda pm: str(pm[0]))
        ]
        return SyncPreview(
            entries=entries,
            files=files,
            settings={"image_duration": image_duration},
            shifted_paths=shifted_paths,
            timeline_map=timeline,
        )

    def build_cli_preview(
        self,
        catalog: MediaCatalog,
        delta: timedelta,
    ) -> list[SyncPreviewEntry]:
        """Build a CLI-style preview list with per-file skip reasons."""
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        preview: list[SyncPreviewEntry] = []

        for path, meta in catalog.pairs:
            if isinstance(meta, PhotoMetadata):
                current = meta.timestamp
            elif isinstance(meta, VideoMetadata):
                current = meta.start_timestamp
            else:
                current = None

            if current is None:
                preview.append(SyncPreviewEntry(path, None, None, "No timestamp found"))
                continue

            new_time = current + delta
            new_time_aware = new_time.replace(tzinfo=timezone.utc) if new_time.tzinfo is None else new_time
            if new_time_aware < epoch:
                preview.append(SyncPreviewEntry(path, current, None, "Result would be before 1970"))
                continue

            preview.append(SyncPreviewEntry(path, current, new_time, None))

        return preview

    def execute(
        self,
        catalog: MediaCatalog,
        deltas: dict[str, float],
        *,
        write_photo: WriterFn = write_photo_timestamp,
        write_video: WriterFn = write_video_timestamp,
    ) -> SyncApplyResult:
        """Write shifted timestamps to disk, one path at a time.

        Returns applied/failed lists plus a refreshed catalog and preview.
        Per-file errors do not abort the batch.
        """
        writable: list[tuple[Path, object, datetime, float]] = []
        for path, meta in catalog.pairs:
            delta = deltas.get(str(path), 0.0)
            if delta == 0.0:
                continue
            if isinstance(meta, PhotoMetadata) and meta.timestamp is not None:
                writable.append((path, meta, meta.timestamp, delta))
            elif isinstance(meta, VideoMetadata) and meta.start_timestamp is not None:
                writable.append((path, meta, meta.start_timestamp, delta))

        applied: list[dict] = []
        failed: list[dict] = []

        for path, meta, old_ts, delta in writable:
            new_ts = old_ts + timedelta(seconds=delta)
            writer = write_photo if isinstance(meta, PhotoMetadata) else write_video
            try:
                ok = writer(path, new_ts)
            except Exception as e:
                failed.append({"path": str(path), "error": str(e)})
                continue

            if ok:
                applied.append({
                    "path": str(path),
                    "old_ts": old_ts.isoformat(),
                    "new_ts": new_ts.isoformat(),
                })
            else:
                failed.append({"path": str(path), "error": "Writer returned False"})

        refreshed_catalog = catalog.refresh()
        preview = self.build_preview(refreshed_catalog, {}, image_duration=3.5)

        return SyncApplyResult(
            applied=applied,
            failed=failed,
            catalog=refreshed_catalog,
            preview=preview,
        )
