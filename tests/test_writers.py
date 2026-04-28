from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import piexif

from photowalk.writers import write_photo_timestamp, write_video_timestamp


class TestWritePhotoTimestamp:
    def test_success(self):
        mock_exif = {"0th": {}, "Exif": {}}

        with patch("photowalk.writers.piexif.load", return_value=mock_exif) as mock_load:
            with patch("photowalk.writers.piexif.dump", return_value=b"exifbytes") as mock_dump:
                with patch("photowalk.writers.piexif.insert") as mock_insert:
                    result = write_photo_timestamp(Path("/tmp/photo.jpg"), datetime(2024, 7, 15, 14, 32, 10))

        assert result is True
        mock_load.assert_called_once_with("/tmp/photo.jpg")
        mock_dump.assert_called_once()
        mock_insert.assert_called_once_with(b"exifbytes", "/tmp/photo.jpg")
        # Verify DateTimeOriginal was set
        assert mock_exif["Exif"][piexif.ExifIFD.DateTimeOriginal] == b"2024:07:15 14:32:10"

    def test_load_failure_returns_false(self):
        with patch("photowalk.writers.piexif.load", side_effect=Exception("bad exif")):
            result = write_photo_timestamp(Path("/tmp/photo.jpg"), datetime(2024, 7, 15, 14, 32, 10))
        assert result is False

    def test_insert_failure_returns_false(self):
        mock_exif = {"0th": {}, "Exif": {}}
        with patch("photowalk.writers.piexif.load", return_value=mock_exif):
            with patch("photowalk.writers.piexif.dump", return_value=b"exifbytes"):
                with patch("photowalk.writers.piexif.insert", side_effect=Exception("write failed")):
                    result = write_photo_timestamp(Path("/tmp/photo.jpg"), datetime(2024, 7, 15, 14, 32, 10))
        assert result is False


class TestWriteVideoTimestamp:
    def test_success(self):
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("photowalk.writers.subprocess.run", return_value=mock_result) as mock_run:
            with patch("photowalk.writers.os.replace") as mock_replace:
                result = write_video_timestamp(Path("/tmp/video.mp4"), datetime(2024, 7, 15, 14, 32, 10, tzinfo=timezone.utc))

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "ffmpeg"
        assert "-y" in call_args
        assert "-i" in call_args
        assert "/tmp/video.mp4" in call_args
        assert "-c" in call_args
        assert "copy" in call_args
        assert "-metadata" in call_args
        assert "creation_time=2024-07-15T14:32:10+00:00" in call_args
        assert "/tmp/video.tmp.mp4" in call_args
        mock_replace.assert_called_once_with(Path("/tmp/video.tmp.mp4"), Path("/tmp/video.mp4"))

    def test_ffmpeg_failure_returns_false(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error msg"

        with patch("photowalk.writers.subprocess.run", return_value=mock_result):
            with patch("photowalk.writers.os.path.exists", return_value=True):
                with patch("photowalk.writers.os.remove") as mock_remove:
                    result = write_video_timestamp(Path("/tmp/video.mp4"), datetime(2024, 7, 15, 14, 32, 10))

        assert result is False
        mock_remove.assert_called_once_with(Path("/tmp/video.tmp.mp4"))

    def test_ffmpeg_not_found_returns_false(self):
        with patch("photowalk.writers.subprocess.run", side_effect=FileNotFoundError()):
            result = write_video_timestamp(Path("/tmp/video.mp4"), datetime(2024, 7, 15, 14, 32, 10))
        assert result is False
