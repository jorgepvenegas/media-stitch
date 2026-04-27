from pathlib import Path
from unittest.mock import patch

from photowalk.api import extract_metadata
from photowalk.models import PhotoMetadata, VideoMetadata


def test_extract_metadata_photo():
    mock_exif = {
        "timestamp": "2024-07-15 14:32:10",
        "model": "EOS R6",
        "shutter_speed": "1/250",
        "iso": 400,
        "focal_length": "35mm",
    }

    with patch("photowalk.api.extract_photo_exif", return_value=mock_exif):
        result = extract_metadata(Path("/tmp/photo.jpg"))

    assert isinstance(result, PhotoMetadata)
    assert result.camera_model == "EOS R6"
    assert result.shutter_speed == "1/250"


def test_extract_metadata_video():
    mock_ffprobe = {
        "format": {
            "duration": "120.0",
            "tags": {"creation_time": "2024-07-15T14:00:00.000000Z"}
        }
    }

    with patch("photowalk.api.run_ffprobe", return_value=mock_ffprobe):
        result = extract_metadata(Path("/tmp/video.mp4"))

    assert isinstance(result, VideoMetadata)
    assert result.duration_seconds == 120.0


def test_extract_metadata_unknown_extension():
    result = extract_metadata(Path("/tmp/file.txt"))
    assert result is None


def test_extract_metadata_photo_empty_exif():
    with patch("photowalk.api.extract_photo_exif", return_value={}):
        result = extract_metadata(Path("/tmp/photo.jpg"))

    assert isinstance(result, PhotoMetadata)
    assert result.timestamp is None
    assert result.camera_model is None
