from pathlib import Path
from unittest.mock import MagicMock, patch

from photowalk.photo_extractors import (
    extract_photo_exif,
    _format_exposure_time,
    _format_focal_length,
)


def test_format_exposure_time_fraction():
    assert _format_exposure_time((1, 250)) == "1/250"


def test_format_exposure_time_non_one_numerator():
    assert _format_exposure_time((2, 500)) == "2/500"


def test_format_exposure_time_float():
    assert _format_exposure_time(0.004) == "1/250"
    assert _format_exposure_time(0.008) == "1/125"
    assert _format_exposure_time(1.0) == "1s"
    assert _format_exposure_time(2.5) == "2.5s"


def test_format_exposure_time_zero():
    assert _format_exposure_time(0.0) is None


def test_format_focal_length_fraction():
    assert _format_focal_length((350, 10)) == "35mm"


def test_format_focal_length_decimal():
    assert _format_focal_length((245, 10)) == "24.5mm"


def test_format_focal_length_float():
    assert _format_focal_length(35.0) == "35mm"
    assert _format_focal_length(24.5) == "24.5mm"


def test_extract_photo_exif_success():
    mock_exif = {
        0x0132: "2024:07:15 14:32:10",   # DateTime
        0x010F: "Canon",                   # Make
        0x0110: "EOS R6",                  # Model
    }

    mock_exif_ifd = {
        0x9003: "2024:07:15 14:32:10",   # DateTimeOriginal
        0x829A: 0.004,                     # ExposureTime (float)
        0x8827: 400,                       # ISOSpeedRatings
        0x920A: 35.0,                      # FocalLength (float)
    }

    mock_img = MagicMock()
    mock_exif_obj = MagicMock()
    mock_exif_obj.items.return_value = mock_exif.items()
    mock_exif_obj.get.return_value = 216  # ExifOffset
    mock_exif_ifd_obj = MagicMock()
    mock_exif_ifd_obj.items.return_value = mock_exif_ifd.items()
    mock_exif_obj.get_ifd.return_value = mock_exif_ifd_obj
    mock_img.getexif.return_value = mock_exif_obj
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
    mock_exif_obj = MagicMock()
    mock_exif_obj.items.return_value = {}.items()
    mock_exif_obj.get.return_value = None
    mock_img.getexif.return_value = mock_exif_obj
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
    mock_exif_obj = MagicMock()
    mock_exif_obj.items.return_value = mock_exif.items()
    mock_exif_obj.get.return_value = None
    mock_img.getexif.return_value = mock_exif_obj
    mock_img.__enter__.return_value = mock_img

    with patch("photowalk.photo_extractors.Image.open", return_value=mock_img):
        result = extract_photo_exif(Path("/tmp/photo.jpg"))

    assert result["timestamp"] == "2023-01-01 00:00:00"
