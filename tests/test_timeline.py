"""Tests for the timeline builder."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.timeline import (
    MediaInput,
    TimelineEntry,
    TimelineMap,
    VideoTimeline,
    build_timeline,
    build_timeline_from_files,
)


def _dt(seconds_offset: float) -> datetime:
    """Create a UTC datetime offset from a fixed epoch for test convenience."""
    return datetime(2024, 7, 15, 14, 0, 0, tzinfo=timezone.utc).replace(
        second=0
    ) + timedelta(seconds=seconds_offset)


# ---------------------------------------------------------------------------
# build_timeline (pure algorithm)
# ---------------------------------------------------------------------------


def test_build_timeline_inline_image():
    """Video 120s, photo at t+30s → 3 segments: video_segment, image, video_segment."""
    video_path = Path("/tmp/video.mp4")
    photo_path = Path("/tmp/photo.jpg")

    pairs: list[MediaInput] = [
        (video_path, VideoMetadata(
            source_path=video_path,
            start_timestamp=_dt(0),
            end_timestamp=_dt(120),
            duration_seconds=120.0,
        )),
        (photo_path, PhotoMetadata(
            source_path=photo_path,
            timestamp=_dt(30),
        )),
    ]

    result = build_timeline(pairs)

    assert isinstance(result, TimelineMap)
    assert len(result.standalone_images) == 0
    assert len(result.video_timelines) == 1

    vt = result.video_timelines[0]
    assert vt.video_path == video_path
    assert len(vt.segments) == 3

    seg0 = vt.segments[0]
    assert seg0.kind == "video_segment"
    assert seg0.trim_start == 0.0
    assert seg0.trim_end == 30.0
    assert seg0.original_video == video_path

    seg1 = vt.segments[1]
    assert seg1.kind == "image"
    assert seg1.source_path == photo_path
    assert seg1.start_time == _dt(30).replace(tzinfo=None)

    seg2 = vt.segments[2]
    assert seg2.kind == "video_segment"
    assert seg2.trim_start == 30.0
    assert seg2.trim_end == 120.0
    assert seg2.original_video == video_path

    assert len(result.all_entries) == 3
    assert result.all_entries[0].kind == "video_segment"
    assert result.all_entries[1].kind == "image"
    assert result.all_entries[2].kind == "video_segment"


def test_build_timeline_standalone_image():
    """Image before video → standalone_images, not in any VideoTimeline."""
    video_path = Path("/tmp/video.mp4")
    photo_path = Path("/tmp/early_photo.jpg")

    pairs: list[MediaInput] = [
        (video_path, VideoMetadata(
            source_path=video_path,
            start_timestamp=_dt(100),
            end_timestamp=_dt(220),
            duration_seconds=120.0,
        )),
        (photo_path, PhotoMetadata(
            source_path=photo_path,
            timestamp=_dt(10),
        )),
    ]

    result = build_timeline(pairs)

    assert len(result.standalone_images) == 1
    assert result.standalone_images[0].source_path == photo_path
    assert result.standalone_images[0].kind == "image"

    assert len(result.video_timelines) == 1
    vt = result.video_timelines[0]
    assert len(vt.segments) == 1
    assert vt.segments[0].kind == "video_segment"
    assert vt.segments[0].trim_start == 0.0
    assert vt.segments[0].trim_end == 120.0


def test_build_timeline_multiple_inline_images():
    """Two inline images → 5 segments: seg, img, seg, img, seg."""
    video_path = Path("/tmp/video.mp4")
    photo1_path = Path("/tmp/photo1.jpg")
    photo2_path = Path("/tmp/photo2.jpg")

    pairs: list[MediaInput] = [
        (video_path, VideoMetadata(
            source_path=video_path,
            start_timestamp=_dt(0),
            end_timestamp=_dt(120),
            duration_seconds=120.0,
        )),
        (photo1_path, PhotoMetadata(source_path=photo1_path, timestamp=_dt(30))),
        (photo2_path, PhotoMetadata(source_path=photo2_path, timestamp=_dt(80))),
    ]

    result = build_timeline(pairs)

    assert len(result.standalone_images) == 0
    vt = result.video_timelines[0]
    assert len(vt.segments) == 5

    kinds = [s.kind for s in vt.segments]
    assert kinds == ["video_segment", "image", "video_segment", "image", "video_segment"]

    trims = [(s.trim_start, s.trim_end) for s in vt.segments if s.kind == "video_segment"]
    assert trims == [(0.0, 30.0), (30.0, 80.0), (80.0, 120.0)]

    assert len(result.all_entries) == 5


def test_build_timeline_empty():
    """No usable entries → empty TimelineMap."""
    pairs: list[MediaInput] = [
        (Path("/tmp/photo.jpg"), PhotoMetadata(source_path=Path("/tmp/photo.jpg"))),
    ]
    result = build_timeline(pairs)

    assert isinstance(result, TimelineMap)
    assert len(result.video_timelines) == 0
    assert len(result.standalone_images) == 0
    assert len(result.all_entries) == 0


def test_build_timeline_empty_list():
    """Empty input list → empty TimelineMap."""
    result = build_timeline([])

    assert isinstance(result, TimelineMap)
    assert len(result.video_timelines) == 0
    assert len(result.standalone_images) == 0
    assert len(result.all_entries) == 0


def test_build_timeline_mixed_timezone_awareness():
    """Regression: video timestamps from ffprobe are often timezone-aware,
    while photo timestamps from EXIF are timezone-naive."""
    video_path = Path("/tmp/video.mp4")
    photo_path = Path("/tmp/photo.jpg")

    pairs: list[MediaInput] = [
        (video_path, VideoMetadata(
            source_path=video_path,
            start_timestamp=datetime(2024, 7, 15, 12, 0, 0, tzinfo=timezone.utc),
            end_timestamp=datetime(2024, 7, 15, 12, 2, 0, tzinfo=timezone.utc),
            duration_seconds=120.0,
        )),
        (photo_path, PhotoMetadata(
            source_path=photo_path,
            timestamp=datetime(2024, 7, 15, 12, 0, 30),  # naive
        )),
    ]

    result = build_timeline(pairs)

    assert len(result.video_timelines) == 1
    assert len(result.video_timelines[0].segments) == 3


# ---------------------------------------------------------------------------
# build_timeline_from_files (I/O wrapper)
# ---------------------------------------------------------------------------


def test_build_timeline_from_files_extracts_and_builds():
    """Wrapper extracts metadata and delegates to pure algorithm."""
    video_path = Path("/tmp/video.mp4")
    photo_path = Path("/tmp/photo.jpg")

    video_meta = VideoMetadata(
        source_path=video_path,
        start_timestamp=_dt(0),
        end_timestamp=_dt(120),
        duration_seconds=120.0,
    )
    photo_meta = PhotoMetadata(source_path=photo_path, timestamp=_dt(30))

    def _mock_extract(path):
        if path == video_path:
            return video_meta
        if path == photo_path:
            return photo_meta
        return None

    with patch("photowalk.api.extract_metadata", side_effect=_mock_extract):
        result = build_timeline_from_files([video_path, photo_path])

    assert len(result.video_timelines) == 1
    assert len(result.video_timelines[0].segments) == 3
