"""Timeline builder for video stitcher.

Builds a sorted timeline that associates inline images with the video
whose time range contains them.  Pure algorithm — no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Literal, Optional, Tuple, Union

from photowalk.models import PhotoMetadata, VideoMetadata

# A pre-extracted metadata pair: (file_path, metadata).
MediaInput = Tuple[Path, Union[PhotoMetadata, VideoMetadata]]


@dataclass
class TimelineEntry:
    start_time: datetime
    duration_seconds: float
    kind: Literal["video", "image", "video_segment"]
    source_path: Path
    clip_path: Optional[Path] = None
    original_video: Optional[Path] = None
    trim_start: Optional[float] = None
    trim_end: Optional[float] = None


@dataclass
class VideoTimeline:
    video_path: Path
    video_start: datetime
    video_end: datetime
    segments: List[TimelineEntry] = field(default_factory=list)


@dataclass
class TimelineMap:
    video_timelines: List[VideoTimeline] = field(default_factory=list)
    standalone_images: List[TimelineEntry] = field(default_factory=list)
    all_entries: List[TimelineEntry] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_naive(dt: Optional[datetime]) -> Optional[datetime]:
    """Strip timezone info from a datetime for consistent comparison.

    EXIF timestamps are timezone-naive; ffprobe timestamps are often
    timezone-aware.  The timeline builder needs to compare them.
    """
    if dt is None:
        return None
    return dt.replace(tzinfo=None)


def _make_video_segments(
    video_path: Path,
    video_start: datetime,
    duration_seconds: float,
    inline_images: List[TimelineEntry],
) -> List[TimelineEntry]:
    """Split a video into segments around inline images.

    Returns an ordered list of video_segment and image entries.
    """
    segments: List[TimelineEntry] = []
    sorted_images = sorted(inline_images, key=lambda e: e.start_time)

    current_offset = 0.0

    for image in sorted_images:
        # Offset in seconds of this image relative to the video start
        image_offset = (image.start_time - video_start).total_seconds()

        # Video segment before the image (skip zero-length segments)
        if image_offset > current_offset:
            seg_start = video_start + timedelta(seconds=current_offset)
            segments.append(
                TimelineEntry(
                    start_time=seg_start,
                    duration_seconds=image_offset - current_offset,
                    kind="video_segment",
                    source_path=video_path,
                    original_video=video_path,
                    trim_start=current_offset,
                    trim_end=image_offset,
                )
            )

        segments.append(image)
        current_offset = image_offset

    # Final video segment after the last image (or the whole video if no images)
    if current_offset < duration_seconds:
        seg_start = video_start + timedelta(seconds=current_offset)
        segments.append(
            TimelineEntry(
                start_time=seg_start,
                duration_seconds=duration_seconds - current_offset,
                kind="video_segment",
                source_path=video_path,
                original_video=video_path,
                trim_start=current_offset,
                trim_end=duration_seconds,
            )
        )

    return segments


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_timeline(metadata_pairs: List[MediaInput]) -> TimelineMap:
    """Build a sorted timeline from pre-extracted metadata.

    Pure algorithm — no I/O.  Each pair is (file_path, metadata).
    For each video, images whose timestamp falls within [video_start, video_end]
    are treated as inline and the video is split around them.  Images outside
    all video ranges are standalone.
    """
    if not metadata_pairs:
        return TimelineMap()

    # --- Classify entries -----------------------------------------------
    photo_entries: List[TimelineEntry] = []
    video_timelines: List[VideoTimeline] = []

    for path, meta in metadata_pairs:
        if isinstance(meta, PhotoMetadata) and meta.timestamp is not None:
            photo_entries.append(
                TimelineEntry(
                    start_time=_make_naive(meta.timestamp),
                    duration_seconds=0.0,
                    kind="image",
                    source_path=path,
                )
            )

        elif isinstance(meta, VideoMetadata):
            if (
                meta.start_timestamp is not None
                and meta.duration_seconds is not None
            ):
                end_ts = meta.end_timestamp or (
                    meta.start_timestamp + timedelta(seconds=meta.duration_seconds)
                )
                video_timelines.append(
                    VideoTimeline(
                        video_path=path,
                        video_start=_make_naive(meta.start_timestamp),
                        video_end=_make_naive(end_ts),
                    )
                )

    # Sort videos by start time
    video_timelines.sort(key=lambda vt: vt.video_start)

    # --- Associate images with videos ------------------------------------
    standalone_images: List[TimelineEntry] = []

    for image_entry in photo_entries:
        placed = False
        for vt in video_timelines:
            if vt.video_start <= image_entry.start_time <= vt.video_end:
                vt.segments.append(image_entry)
                placed = True
                break
        if not placed:
            standalone_images.append(image_entry)

    # --- Build segments for each video -----------------------------------
    all_entries: List[TimelineEntry] = []

    for vt in video_timelines:
        duration = (vt.video_end - vt.video_start).total_seconds()
        vt.segments = _make_video_segments(
            vt.video_path, vt.video_start, duration, vt.segments
        )
        all_entries.extend(vt.segments)

    all_entries.extend(standalone_images)
    all_entries.sort(key=lambda e: e.start_time)

    return TimelineMap(
        video_timelines=video_timelines,
        standalone_images=standalone_images,
        all_entries=all_entries,
    )


def build_timeline_from_files(files: List[Path]) -> TimelineMap:
    """Extract metadata from files and build a timeline.

    Convenience wrapper around build_timeline() that handles I/O.
    Files that fail to extract or have no usable metadata are silently skipped.
    """
    from photowalk.api import extract_metadata

    pairs: List[MediaInput] = []
    for path in files:
        meta = extract_metadata(path)
        if meta is not None:
            pairs.append((path, meta))

    return build_timeline(pairs)
