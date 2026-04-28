from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from photowalk.cli import main
from photowalk.models import VideoMetadata
from photowalk.offset_detector import OffsetDetectionError


class TestFixTrimDryRun:
    def test_dry_run_shows_computed_timestamps(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("orig.mp4").touch()
            Path("trim.mp4").touch()
            with patch("photowalk.cli.extract_metadata") as mock_meta:
                with patch("photowalk.cli.detect_trim_offset", return_value=5.0):
                    mock_meta.side_effect = [
                        VideoMetadata(
                            source_path=Path("orig.mp4"),
                            start_timestamp=datetime(2024, 7, 15, 14, 0, 0, tzinfo=timezone.utc),
                            duration_seconds=120.0,
                        ),
                        VideoMetadata(
                            source_path=Path("trim.mp4"),
                            start_timestamp=None,
                            duration_seconds=60.0,
                        ),
                    ]
                    result = runner.invoke(main, ["fix-trim", "orig.mp4", "trim.mp4", "--dry-run"])

        assert result.exit_code == 0
        assert "5.000" in result.output
        assert "2024-07-15T14:00:00" in result.output
        assert "2024-07-15T14:00:05" in result.output


class TestFixTrimWrite:
    def test_success_updates_trimmed_in_place(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("orig.mp4").touch()
            Path("trim.mp4").touch()
            with patch("photowalk.cli.extract_metadata") as mock_meta:
                with patch("photowalk.cli.detect_trim_offset", return_value=5.0):
                    with patch("photowalk.cli.write_video_timestamp", return_value=True) as mock_write:
                        mock_meta.side_effect = [
                            VideoMetadata(
                                source_path=Path("orig.mp4"),
                                start_timestamp=datetime(2024, 7, 15, 14, 0, 0, tzinfo=timezone.utc),
                                duration_seconds=120.0,
                            ),
                            VideoMetadata(
                                source_path=Path("trim.mp4"),
                                start_timestamp=None,
                                duration_seconds=60.0,
                            ),
                        ]
                        result = runner.invoke(main, ["fix-trim", "orig.mp4", "trim.mp4"])

        assert result.exit_code == 0
        mock_write.assert_called_once()
        args = mock_write.call_args[0]
        assert args[0] == Path("trim.mp4")
        assert args[1] == datetime(2024, 7, 15, 14, 0, 5, tzinfo=timezone.utc)

    def test_output_option_copies_then_updates(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("orig.mp4").write_text("original")
            Path("trim.mp4").write_text("trimmed")
            with patch("photowalk.cli.extract_metadata") as mock_meta:
                with patch("photowalk.cli.detect_trim_offset", return_value=5.0):
                    with patch("photowalk.cli.write_video_timestamp", return_value=True) as mock_write:
                        with patch("photowalk.cli.shutil.copy2") as mock_copy:
                            mock_meta.side_effect = [
                                VideoMetadata(
                                    source_path=Path("orig.mp4"),
                                    start_timestamp=datetime(2024, 7, 15, 14, 0, 0, tzinfo=timezone.utc),
                                    duration_seconds=120.0,
                                ),
                                VideoMetadata(
                                    source_path=Path("trim.mp4"),
                                    start_timestamp=None,
                                    duration_seconds=60.0,
                                ),
                            ]
                            result = runner.invoke(
                                main, ["fix-trim", "orig.mp4", "trim.mp4", "-o", "out.mp4"]
                            )

        assert result.exit_code == 0
        mock_copy.assert_called_once_with(Path("trim.mp4"), Path("out.mp4"))
        mock_write.assert_called_once()
        assert mock_write.call_args[0][0] == Path("out.mp4")

    def test_detection_error_exits_with_message(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("orig.mp4").touch()
            Path("trim.mp4").touch()
            with patch("photowalk.cli.extract_metadata") as mock_meta:
                with patch(
                    "photowalk.cli.detect_trim_offset",
                    side_effect=OffsetDetectionError("no audio track"),
                ):
                    mock_meta.return_value = VideoMetadata(
                        source_path=Path("orig.mp4"),
                        start_timestamp=datetime(2024, 7, 15, 14, 0, 0, tzinfo=timezone.utc),
                        duration_seconds=120.0,
                    )
                    result = runner.invoke(main, ["fix-trim", "orig.mp4", "trim.mp4"])

        assert result.exit_code == 1
        assert "no audio track" in result.output

    def test_non_video_file_rejected(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("orig.jpg").touch()
            Path("trim.mp4").touch()
            result = runner.invoke(main, ["fix-trim", "orig.jpg", "trim.mp4"])

        assert result.exit_code == 1
        assert "must be a video file" in result.output

    def test_missing_original_timestamp_rejected(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("orig.mp4").touch()
            Path("trim.mp4").touch()
            with patch("photowalk.cli.extract_metadata") as mock_meta:
                mock_meta.return_value = VideoMetadata(
                    source_path=Path("orig.mp4"),
                    start_timestamp=None,
                    duration_seconds=120.0,
                )
                result = runner.invoke(main, ["fix-trim", "orig.mp4", "trim.mp4"])

        assert result.exit_code == 1
        assert "start timestamp" in result.output
