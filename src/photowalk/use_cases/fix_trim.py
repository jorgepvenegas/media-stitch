"""Fix-trim use-case: detect offset and write corrected timestamp."""

import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from photowalk.api import extract_metadata
from photowalk.models import VideoMetadata
from photowalk.offset_detector import detect_trim_offset, OffsetDetectionError
from photowalk.use_cases.errors import UseCaseError
from photowalk.writers import write_video_timestamp


@dataclass(frozen=True)
class FixTrimResult:
    offset_seconds: float
    original_start: datetime
    adjusted_start: datetime
    adjusted_end: Optional[datetime]
    target_path: Path
    dry_run: bool


class FixTrimUseCase:
    def run(
        self,
        original: Path,
        trimmed: Path,
        output: Optional[Path] = None,
        dry_run: bool = False,
    ) -> FixTrimResult:
        original_meta = extract_metadata(original)
        if not isinstance(original_meta, VideoMetadata) or original_meta.start_timestamp is None:
            raise UseCaseError("Could not read start timestamp from original video")

        try:
            offset_seconds = detect_trim_offset(original, trimmed)
        except OffsetDetectionError as e:
            raise UseCaseError(str(e)) from e

        adjusted_start = original_meta.start_timestamp + timedelta(seconds=offset_seconds)

        trimmed_meta = extract_metadata(trimmed)
        duration = trimmed_meta.duration_seconds if isinstance(trimmed_meta, VideoMetadata) else None
        adjusted_end = adjusted_start + timedelta(seconds=duration) if duration else None

        target_path = output if output else trimmed
        if output:
            shutil.copy2(trimmed, output)

        if not dry_run:
            ok = write_video_timestamp(target_path, adjusted_start)
            if not ok:
                raise UseCaseError(f"Failed to write timestamp to {target_path}")

        return FixTrimResult(
            offset_seconds=offset_seconds,
            original_start=original_meta.start_timestamp,
            adjusted_start=adjusted_start,
            adjusted_end=adjusted_end,
            target_path=target_path,
            dry_run=dry_run,
        )
