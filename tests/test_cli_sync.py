from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from photowalk.cli import main


class TestSyncDryRun:
    def test_sync_dry_run_offset(self):
        mock_photo_exif = {
            "timestamp": "2026-04-27 15:28:01",
            "make": "Canon",
            "model": "EOS R6",
        }

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("photo.jpg").touch()
            with patch("photowalk.api.extract_photo_exif", return_value=mock_photo_exif):
                result = runner.invoke(main, ["sync", "photo.jpg", "--offset", "-8h23m5s", "--dry-run"])

        assert result.exit_code == 0
        assert "photo.jpg" in result.output
        assert "2026-04-27T15:28:01" in result.output or "2026-04-27 15:28:01" in result.output
        assert "2026-04-27T07:04:56" in result.output or "2026-04-27 07:04:56" in result.output

    def test_sync_dry_run_reference(self):
        mock_photo_exif = {
            "timestamp": "2026-04-27 15:28:01",
            "make": "Canon",
            "model": "EOS R6",
        }

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("photo.jpg").touch()
            with patch("photowalk.api.extract_photo_exif", return_value=mock_photo_exif):
                result = runner.invoke(main, [
                    "sync", "photo.jpg",
                    "--reference", "2026-04-27T23:28:01+00:00=2026-04-27T07:05:00",
                    "--dry-run",
                ])

        assert result.exit_code == 0
        assert "photo.jpg" in result.output

    def test_sync_missing_offset_and_reference(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("photo.jpg").touch()
            result = runner.invoke(main, ["sync", "photo.jpg"])

        assert result.exit_code != 0
        assert "--offset" in result.output or "--reference" in result.output

    def test_sync_both_offset_and_reference(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("photo.jpg").touch()
            result = runner.invoke(main, ["sync", "photo.jpg", "--offset", "+1h", "--reference", "a=b"])

        assert result.exit_code != 0

    def test_sync_no_media_files(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["sync", ".", "--offset", "+1h"])

        assert result.exit_code == 0
        assert "No media files found" in result.output


class TestSyncWrite:
    def test_sync_with_yes_writes_photo(self):
        mock_photo_exif = {
            "timestamp": "2026-04-27 15:28:01",
            "make": "Canon",
            "model": "EOS R6",
        }

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("photo.jpg").touch()
            with patch("photowalk.api.extract_photo_exif", return_value=mock_photo_exif):
                with patch("photowalk.cli.write_photo_timestamp", return_value=True) as mock_write:
                    result = runner.invoke(main, ["sync", "photo.jpg", "--offset", "-8h23m5s", "--yes"])

        assert result.exit_code == 0
        mock_write.assert_called_once()

    def test_sync_confirmation_no_cancels(self):
        mock_photo_exif = {
            "timestamp": "2026-04-27 15:28:01",
            "make": "Canon",
            "model": "EOS R6",
        }

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("photo.jpg").touch()
            with patch("photowalk.api.extract_photo_exif", return_value=mock_photo_exif):
                with patch("photowalk.cli.write_photo_timestamp") as mock_write:
                    result = runner.invoke(main, ["sync", "photo.jpg", "--offset", "-8h23m5s"], input="n\n")

        assert result.exit_code == 0
        assert "Cancelled" in result.output or "cancelled" in result.output
        mock_write.assert_not_called()

    def test_sync_confirmation_yes_writes(self):
        mock_photo_exif = {
            "timestamp": "2026-04-27 15:28:01",
            "make": "Canon",
            "model": "EOS R6",
        }

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("photo.jpg").touch()
            with patch("photowalk.api.extract_photo_exif", return_value=mock_photo_exif):
                with patch("photowalk.cli.write_photo_timestamp", return_value=True) as mock_write:
                    result = runner.invoke(main, ["sync", "photo.jpg", "--offset", "-8h23m5s"], input="y\n")

        assert result.exit_code == 0
        mock_write.assert_called_once()
