"""WebSession — typed, mutable session state behind the FastAPI app."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Set

from photowalk.catalog import MediaCatalog
from photowalk.timeline import TimelineMap, build_timeline
from photowalk.use_cases.sync import SyncUseCase
from photowalk.web.file_entry import metadata_to_file_entry
from photowalk.web.stitch_models import StitchRequest, StitchStatus
from photowalk.web.stitch_runner import StitchJob, cancel_stitch, start_stitch


class StitchConflictError(Exception):
    """Raised when a stitch is requested while another is running."""


@dataclass
class WebSession:
    catalog: MediaCatalog
    timeline_map: TimelineMap
    scan_files: Set[Path]
    image_duration: float = 3.5
    scan_path: Path | None = None
    _stitch_job: StitchJob | None = field(default=None, repr=False)
    _preview_timeline: TimelineMap | None = field(default=None, repr=False)

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    @property
    def files(self) -> list[dict]:
        """Lazy file-list derived from the current catalog."""
        return [
            metadata_to_file_entry(p, m)
            for p, m in sorted(self.catalog.pairs, key=lambda pm: str(pm[0]))
        ]

    def is_allowed_media(self, path: Path) -> bool:
        resolved = path.resolve()
        return resolved in self.scan_files and resolved.exists()

    def get_timeline(self, *, image_duration: float | None = None) -> dict:
        dur = image_duration if image_duration is not None else self.image_duration
        entries = []
        for entry in self.timeline_map.all_entries:
            data = {
                "kind": entry.kind,
                "source_path": str(entry.source_path),
                "start_time": entry.start_time.isoformat() if entry.start_time else None,
                "duration_seconds": entry.duration_seconds,
            }
            if entry.kind == "video_segment":
                data["trim_start"] = entry.trim_start
                data["trim_end"] = entry.trim_end
            entries.append(data)
        result = {"entries": entries, "settings": {"image_duration": dur}}
        if self.scan_path is not None:
            result["scan_path"] = str(self.scan_path)
        return result

    # ------------------------------------------------------------------ #
    # Sync
    # ------------------------------------------------------------------ #

    def preview(self, offsets: list, *, image_duration: float | None = None) -> dict:
        dur = image_duration if image_duration is not None else self.image_duration
        deltas = SyncUseCase.compute_net_deltas(offsets)
        preview = SyncUseCase().build_preview(
            self.catalog,
            deltas,
            image_duration=dur,
        )
        # Store the preview timeline so stitch can use it if the user
        # renders before applying (or after previewing further changes).
        self._preview_timeline = preview.timeline_map
        return {
            "entries": preview.entries,
            "settings": preview.settings,
            "files": preview.files,
        }

    def apply(
        self,
        offsets: list,
        *,
        write_photo,
        write_video,
    ) -> dict:
        deltas = SyncUseCase.compute_net_deltas(offsets)
        result = SyncUseCase().execute(
            self.catalog,
            deltas,
            write_photo=write_photo,
            write_video=write_video,
        )
        self.catalog = result.catalog
        # Rebuild timeline so subsequent stitch / timeline queries stay consistent.
        self.timeline_map = self.catalog.timeline(image_duration=self.image_duration)
        # Clear preview — the applied timeline is now the base.
        self._preview_timeline = None
        return {
            "applied": result.applied,
            "failed": result.failed,
            "files": result.preview.files,
            "timeline": self.get_timeline(),
        }

    # ------------------------------------------------------------------ #
    # Stitch
    # ------------------------------------------------------------------ #

    def start_stitch(self, request: StitchRequest, *, stitch_fn=None) -> StitchJob:
        if self._stitch_job is not None and self._stitch_job.state == "running":
            raise StitchConflictError("A render is already in progress")
        # Use the preview timeline if the user has pending (previewed)
        # offsets; otherwise fall back to the base timeline.
        effective_timeline = self._preview_timeline or self.timeline_map
        job = start_stitch(effective_timeline, request, stitch_fn=stitch_fn)
        self._stitch_job = job
        return job

    def cancel_stitch(self) -> bool:
        job = self._stitch_job
        if job is not None and job.state == "running":
            cancel_stitch(job)
            return True
        return False

    @property
    def stitch_status(self) -> StitchStatus:
        job = self._stitch_job
        if job is None:
            return StitchStatus(state="idle", message="No render in progress")
        return StitchStatus(
            state=job.state,  # type: ignore[arg-type]
            message=job.message,
            output_path=str(job.output_path) if job.output_path else None,
        )
