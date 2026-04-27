from pathlib import Path
from unittest.mock import patch, MagicMock

from photowalk.api import extract_metadata
from photowalk.models import PhotoMetadata, VideoMetadata


def test_extract_metadata_photo():
    mock_ffprobe = {
        "format": {
            "tags": {
                "creation_time": "2024-07-15T14:32:10.000000Z",
                "Model": "EOS R6",
            }
        }
    }

    with patch("photowalk.api.run_ffprobe", return_value=mock_ffprobe):
        result = extract_metadata(Path("/tmp/photo.jpg"))

    assert isinstance(result, PhotoMetadata)
    assert result.camera_model == "EOS R6"


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


def test_extract_metadata_ffprobe_failure():
    with patch("photowalk.api.run_ffprobe", return_value=None):
        result = extract_metadata(Path("/tmp/photo.jpg"))

    assert isinstance(result, PhotoMetadata)
    assert result.timestamp is None
