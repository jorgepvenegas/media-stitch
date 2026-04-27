from datetime import datetime
from pathlib import Path

from photowalk.models import PhotoMetadata, VideoMetadata


def test_photo_metadata_defaults():
    p = PhotoMetadata(source_path=Path("/tmp/test.jpg"))
    assert p.source_path == Path("/tmp/test.jpg")
    assert p.media_type == "photo"
    assert p.timestamp is None
    assert p.camera_model is None
    assert p.shutter_speed is None
    assert p.iso is None
    assert p.focal_length is None


def test_photo_metadata_with_values():
    ts = datetime(2024, 7, 15, 14, 32, 10)
    p = PhotoMetadata(
        source_path=Path("/tmp/test.jpg"),
        timestamp=ts,
        camera_model="Canon EOS R6",
        shutter_speed="1/250",
        iso=400,
        focal_length="35mm",
    )
    assert p.timestamp == ts
    assert p.camera_model == "Canon EOS R6"


def test_photo_metadata_to_dict():
    ts = datetime(2024, 7, 15, 14, 32, 10)
    p = PhotoMetadata(
        source_path=Path("/tmp/test.jpg"),
        timestamp=ts,
        camera_model="Canon EOS R6",
        iso=400,
    )
    d = p.to_dict()
    assert d["source_path"] == "/tmp/test.jpg"
    assert d["media_type"] == "photo"
    assert d["timestamp"] == "2024-07-15T14:32:10"
    assert d["camera_model"] == "Canon EOS R6"
    assert d["iso"] == 400
    assert d["shutter_speed"] is None


def test_video_metadata_defaults():
    v = VideoMetadata(source_path=Path("/tmp/test.mp4"))
    assert v.source_path == Path("/tmp/test.mp4")
    assert v.media_type == "video"
    assert v.start_timestamp is None
    assert v.end_timestamp is None
    assert v.duration_seconds is None


def test_video_metadata_with_values():
    start = datetime(2024, 7, 15, 14, 0, 0)
    end = datetime(2024, 7, 15, 14, 5, 30)
    v = VideoMetadata(
        source_path=Path("/tmp/test.mp4"),
        start_timestamp=start,
        end_timestamp=end,
        duration_seconds=330.0,
    )
    assert v.start_timestamp == start
    assert v.duration_seconds == 330.0


def test_video_metadata_to_dict():
    start = datetime(2024, 7, 15, 14, 0, 0)
    v = VideoMetadata(
        source_path=Path("/tmp/test.mp4"),
        start_timestamp=start,
        duration_seconds=120.5,
    )
    d = v.to_dict()
    assert d["source_path"] == "/tmp/test.mp4"
    assert d["media_type"] == "video"
    assert d["start_timestamp"] == "2024-07-15T14:00:00"
    assert d["duration_seconds"] == 120.5
    assert d["end_timestamp"] is None
