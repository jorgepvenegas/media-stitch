from pathlib import Path
from unittest.mock import MagicMock, patch

from photowalk.photo_extractors import extract_photo_exif, _format_exposure_time, _format_focal_length


def test_format_exposure_time_fraction():
    assert _format_exposure_time((1, 250)) == "1/250"


def test_format_exposure_time_non_one_numerator():
    assert _format_exposure_time((2, 500)) == "2/500"


def test_format_focal_length_fraction():
    assert _format_focal_length((350, 10)) == "35mm"


def test_format_focal_length_decimal():
    assert _format_focal_length((245, 10)) == "24.5mm"


def test_format_focal_length_int():
    assert _format_focal_length(35) == "35mm"


def test_extract_photo_exif_success():
    mock_exif = {
        0x9003: "2024:07:15 14:32:10",   # DateTimeOriginal
        0x010F: "Canon",                   # Make
        0x0110: "EOS R6",                  # Model
        0x829A: (1, 250),                  # ExposureTime
        0x8827: 400,                       # ISOSpeedRatings
        0x920A: (350, 10),                 # FocalLength
    }

    mock_img = MagicMock()
    mock_img.getexif.return_value = mock_exif
    mock_img.__enter__.return_value = mock_img

    with patch("photowalk.photo_extractors.Image.open", return_value=mock_img):
        result = extract_photo_exif(Path("/tmp/photo.jpg"))

    assert result["timestamp"] == "2024-07-15 14:32:10"
    assert result["make"] == "Canon"
    assert result["model"] == "EOS R6"
    assert result["shutter_speed"] == "1/250"
    assert result["iso"] == 400
    assert result["focal_length"] == "35mm"


def test_extract_photo_exif_no_exif():
    mock_img = MagicMock()
    mock_img.getexif.return_value = None
    mock_img.__enter__.return_value = mock_img

    with patch("photowalk.photo_extractors.Image.open", return_value=mock_img):
        result = extract_photo_exif(Path("/tmp/photo.jpg"))

    assert result == {}


def test_extract_photo_exif_empty_exif():
    mock_img = MagicMock()
    mock_img.getexif.return_value = {}
    mock_img.__enter__.return_value = mock_img

    with patch("photowalk.photo_extractors.Image.open", return_value=mock_img):
        result = extract_photo_exif(Path("/tmp/photo.jpg"))

    assert result == {}


def test_extract_photo_exif_fallback_datetime():
    # Uses DateTime when DateTimeOriginal is absent
    mock_exif = {
        0x0132: "2023:01:01 00:00:00",   # DateTime
    }

    mock_img = MagicMock()
    mock_img.getexif.return_value = mock_exif
    mock_img.__enter__.return_value = mock_img

    with patch("photowalk.photo_extractors.Image.open", return_value=mock_img):
        result = extract_photo_exif(Path("/tmp/photo.jpg"))

    assert result["timestamp"] == "2023-01-01 00:00:00"
