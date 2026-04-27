from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from photowalk.cli import main


def test_info_photo():
    mock_exif = {
        "timestamp": "2024-07-15 14:32:10",
        "model": "EOS R6",
        "shutter_speed": "1/250",
        "iso": 400,
        "focal_length": "35mm",
    }

    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("photo.jpg").touch()
        with patch("photowalk.api.extract_photo_exif", return_value=mock_exif):
            result = runner.invoke(main, ["info", "photo.jpg"])

    assert result.exit_code == 0
    assert "EOS R6" in result.output
    assert "1/250" in result.output


def test_info_video():
    mock_ffprobe = {
        "format": {
            "duration": "120.0",
            "tags": {"creation_time": "2024-07-15T14:00:00.000000Z"}
        }
    }

    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("video.mp4").touch()
        with patch("photowalk.api.run_ffprobe", return_value=mock_ffprobe):
            result = runner.invoke(main, ["info", "video.mp4"])

    assert result.exit_code == 0
    assert "14:00:00" in result.output


def test_info_unsupported():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("file.txt").touch()
        result = runner.invoke(main, ["info", "file.txt"])

    assert result.exit_code == 0
    assert "Unsupported" in result.output


def test_batch_json():
    mock_exif = {
        "timestamp": "2024-07-15 14:32:10",
        "model": "EOS R6",
    }

    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("photo.jpg").touch()
        with patch("photowalk.api.extract_photo_exif", return_value=mock_exif):
            result = runner.invoke(main, ["batch", ".", "--output", "json"])

    assert result.exit_code == 0
    assert '"media_type": "photo"' in result.output
    assert "EOS R6" in result.output


def test_batch_empty():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["batch", "."])

    assert result.exit_code == 0
    assert "No media files found" in result.output or result.output.strip() == ""
