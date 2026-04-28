"""Tests for the formatters module."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from photowalk.formatters import (
    format_table,
    format_csv,
    format_timedelta,
    format_sync_preview,
    format_timeline,
)
from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.timeline import TimelineEntry


# --- format_table ---


def test_format_table_photo():
    results = [
        PhotoMetadata(
            source_path=Path("/photos/pic.jpg"),
            timestamp=datetime(2024, 7, 15, 14, 32, 10),
            camera_model="Canon EOS R6",
            iso=400,
            focal_length="35mm",
        )
    ]
    output = format_table(results)
    assert "pic.jpg" in output
    assert "photo" in output
    assert "Canon EOS R6" in output
    assert "ISO 400" in output


def test_format_table_video():
    results = [
        VideoMetadata(
            source_path=Path("/videos/clip.mp4"),
            start_timestamp=datetime(2024, 7, 15, 14, 0, 0),
            end_timestamp=datetime(2024, 7, 15, 14, 5, 30),
            duration_seconds=330.5,
        )
    ]
    output = format_table(results)
    assert "clip.mp4" in output
    assert "video" in output
    assert "330.5s" in output


def test_format_table_mixed():
    results = [
        PhotoMetadata(source_path=Path("/a.jpg"), timestamp=datetime(2024, 1, 1)),
        VideoMetadata(source_path=Path("/b.mp4"), start_timestamp=datetime(2024, 1, 2), duration_seconds=10.0),
    ]
    output = format_table(results)
    assert "a.jpg" in output
    assert "b.mp4" in output


def test_format_table_none_values():
    results = [PhotoMetadata(source_path=Path("/a.jpg"))]
    output = format_table(results)
    assert "N/A" in output


# --- format_csv ---


def test_format_csv_photo():
    results = [
        PhotoMetadata(
            source_path=Path("/photos/pic.jpg"),
            timestamp=datetime(2024, 7, 15, 14, 32, 10),
            camera_model="Canon EOS R6",
            iso=400,
            focal_length="35mm",
            shutter_speed="1/250",
        )
    ]
    output = format_csv(results)
    lines = output.split("\n")
    assert lines[0].startswith("source_path,")
    assert "pic.jpg" in lines[1]
    assert "Canon EOS R6" in lines[1]
    assert "400" in lines[1]


def test_format_csv_video():
    results = [
        VideoMetadata(
            source_path=Path("/videos/clip.mp4"),
            start_timestamp=datetime(2024, 7, 15, 14, 0, 0),
            duration_seconds=330.5,
        )
    ]
    output = format_csv(results)
    assert "clip.mp4" in output
    assert "video" in output


# --- format_timedelta ---


def test_format_timedelta_positive_hours():
    td = timedelta(hours=8, minutes=23, seconds=5)
    assert format_timedelta(td) == "+8h 23m 5s"


def test_format_timedelta_negative():
    td = timedelta(hours=-2, minutes=-30)
    assert format_timedelta(td) == "-2h 30m"


def test_format_timedelta_seconds_only():
    td = timedelta(seconds=45)
    assert format_timedelta(td) == "+45s"


def test_format_timedelta_zero():
    td = timedelta(0)
    assert format_timedelta(td) == "0s"


# --- format_sync_preview ---


def test_format_sync_preview_with_entries():
    preview = [
        (Path("/a.jpg"), datetime(2024, 1, 1), datetime(2024, 1, 2), None),
        (Path("/b.mp4"), None, None, "No timestamp found"),
    ]
    delta = timedelta(days=1)
    output = format_sync_preview(preview, delta)
    assert "a.jpg" in output
    assert "b.mp4" in output
    assert "No timestamp found" in output
    assert "+1d" in output or "+24h" in output


# --- format_timeline ---


def test_format_timeline_entries():
    entries = [
        TimelineEntry(
            start_time=datetime(2024, 7, 15, 12, 0, 0),
            duration_seconds=10.0,
            kind="video_segment",
            source_path=Path("video.mp4"),
        ),
        TimelineEntry(
            start_time=datetime(2024, 7, 15, 12, 0, 10),
            duration_seconds=0.0,
            kind="image",
            source_path=Path("photo.jpg"),
        ),
    ]
    output = format_timeline(entries, image_duration=3.5)
    assert "video.mp4" in output
    assert "photo.jpg" in output
    assert "video_segment" in output
    assert "image" in output
    assert "3.5" in output  # image duration
    assert "10.0" in output  # video duration
