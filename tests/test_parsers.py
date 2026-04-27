import json
from datetime import datetime, timezone
from pathlib import Path

from photowalk.parsers import parse_photo, parse_photo_from_exif, parse_video
from photowalk.models import PhotoMetadata, VideoMetadata

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    with open(FIXTURES / name) as f:
        return json.load(f)


def test_parse_photo_full():
    data = load_fixture("ffprobe_photo.json")
    result = parse_photo(Path("/tmp/photo.jpg"), data)

    assert isinstance(result, PhotoMetadata)
    assert result.source_path == Path("/tmp/photo.jpg")
    assert result.timestamp == datetime(2024, 7, 15, 14, 32, 10, tzinfo=timezone.utc)
    assert result.camera_model == "Canon EOS R6"
    assert result.shutter_speed == "1/250"
    assert result.iso == 400
    assert result.focal_length == "35mm"


def test_parse_photo_minimal():
    data = {"format": {"tags": {}}}
    result = parse_photo(Path("/tmp/photo.jpg"), data)

    assert isinstance(result, PhotoMetadata)
    assert result.timestamp is None
    assert result.camera_model is None


def test_parse_photo_missing_tags():
    data = {"format": {}}
    result = parse_photo(Path("/tmp/photo.jpg"), data)

    assert isinstance(result, PhotoMetadata)
    assert result.timestamp is None


def test_parse_video_full():
    data = load_fixture("ffprobe_video.json")
    result = parse_video(Path("/tmp/video.mp4"), data)

    assert isinstance(result, VideoMetadata)
    assert result.source_path == Path("/tmp/video.mp4")
    assert result.start_timestamp == datetime(2024, 7, 15, 14, 0, 0, tzinfo=timezone.utc)
    assert result.duration_seconds == 330.5
    assert result.end_timestamp == datetime(2024, 7, 15, 14, 5, 30, 500000, tzinfo=timezone.utc)


def test_parse_video_no_duration():
    data = {
        "format": {
            "tags": {"creation_time": "2024-07-15T14:00:00.000000Z"}
        }
    }
    result = parse_video(Path("/tmp/video.mp4"), data)

    assert result.start_timestamp == datetime(2024, 7, 15, 14, 0, 0, tzinfo=timezone.utc)
    assert result.duration_seconds is None
    assert result.end_timestamp is None


def test_parse_photo_from_exif_full():
    data = {
        "timestamp": "2024-07-15 14:32:10",
        "make": "Canon",
        "model": "EOS R6",
        "shutter_speed": "1/250",
        "iso": 400,
        "focal_length": "35mm",
    }
    result = parse_photo_from_exif(Path("/tmp/photo.jpg"), data)

    assert isinstance(result, PhotoMetadata)
    assert result.source_path == Path("/tmp/photo.jpg")
    assert result.timestamp == datetime(2024, 7, 15, 14, 32, 10)
    assert result.camera_model == "Canon EOS R6"
    assert result.shutter_speed == "1/250"
    assert result.iso == 400
    assert result.focal_length == "35mm"


def test_parse_photo_from_exif_minimal():
    result = parse_photo_from_exif(Path("/tmp/photo.jpg"), {})

    assert isinstance(result, PhotoMetadata)
    assert result.timestamp is None
    assert result.camera_model is None
    assert result.shutter_speed is None


def test_parse_photo_from_exif_model_only():
    result = parse_photo_from_exif(Path("/tmp/photo.jpg"), {"model": "iPhone 15 Pro"})

    assert result.camera_model == "iPhone 15 Pro"


def test_parse_video_empty():
    data = {}
    result = parse_video(Path("/tmp/video.mp4"), data)

    assert isinstance(result, VideoMetadata)
    assert result.start_timestamp is None
    assert result.duration_seconds is None
