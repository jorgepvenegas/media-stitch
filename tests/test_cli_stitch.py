"""Tests for the stitch CLI command."""

import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from photowalk.cli import main
from photowalk.timeline import TimelineEntry, TimelineMap, VideoTimeline


def _make_mock_timeline():
    """Build a minimal TimelineMap with one video entry."""
    entry = TimelineEntry(
        start_time=datetime.datetime(2024, 7, 15, 12, 0, 0),
        duration_seconds=120.0,
        kind="video",
        source_path=Path("video.mp4"),
    )
    vt = VideoTimeline(
        video_path=Path("video.mp4"),
        video_start=datetime.datetime(2024, 7, 15, 12, 0, 0),
        video_end=datetime.datetime(2024, 7, 15, 12, 2, 0),
    )
    return TimelineMap(
        video_timelines=[vt],
        standalone_images=[],
        all_entries=[entry],
    )


def test_stitch_dry_run():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("video.mp4").touch()
        Path("photo.jpg").touch()

        mock_timeline = _make_mock_timeline()

        with patch("photowalk.cli.build_timeline", return_value=mock_timeline):
            result = runner.invoke(main, ["stitch", ".", "--output", "out.mp4", "--dry-run"])

    assert result.exit_code == 0
    assert "Timeline" in result.output or "out.mp4" in result.output or "video.mp4" in result.output


def test_stitch_no_files():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["stitch", ".", "--output", "out.mp4"])
    assert result.exit_code == 0
    assert "No media files found" in result.output


def test_stitch_invalid_format():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("video.mp4").touch()

        mock_timeline = _make_mock_timeline()

        with patch("photowalk.cli.build_timeline", return_value=mock_timeline):
            result = runner.invoke(main, ["stitch", ".", "--output", "out.mp4", "--format", "bad"])
    assert result.exit_code == 1
    assert "1920x1080" in result.output or "WIDTHxHEIGHT" in result.output
