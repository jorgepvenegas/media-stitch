from datetime import datetime
from pathlib import Path

from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.web.file_entry import metadata_to_file_entry


def test_photo_entry_basic_fields():
    meta = PhotoMetadata(
        source_path=Path("/a.jpg"),
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
    )
    entry = metadata_to_file_entry(Path("/a.jpg"), meta)
    assert entry["path"] == "/a.jpg"
    assert entry["type"] == "photo"
    assert entry["timestamp"] == "2024-01-01T12:00:00"
    assert entry["duration_seconds"] is None
    assert entry["has_timestamp"] is True
    assert entry["shifted"] is False


def test_video_entry_basic_fields():
    meta = VideoMetadata(
        source_path=Path("/v.mp4"),
        start_timestamp=datetime(2024, 1, 1, 12, 0, 0),
        end_timestamp=datetime(2024, 1, 1, 12, 1, 0),
        duration_seconds=60.0,
    )
    entry = metadata_to_file_entry(Path("/v.mp4"), meta)
    assert entry["type"] == "video"
    assert entry["timestamp"] == "2024-01-01T12:00:00"
    assert entry["duration_seconds"] == 60.0
    assert entry["has_timestamp"] is True
    assert entry["shifted"] is False


def test_photo_with_no_timestamp_marks_has_timestamp_false():
    meta = PhotoMetadata(source_path=Path("/a.jpg"))
    entry = metadata_to_file_entry(Path("/a.jpg"), meta)
    assert entry["timestamp"] is None
    assert entry["has_timestamp"] is False


def test_shifted_flag_passes_through():
    meta = PhotoMetadata(
        source_path=Path("/a.jpg"),
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
    )
    entry = metadata_to_file_entry(Path("/a.jpg"), meta, shifted=True)
    assert entry["shifted"] is True
