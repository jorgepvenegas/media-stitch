"""Tests for the stitch CLI command."""

import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from photowalk.cli import main
from photowalk.timeline import TimelineEntry, TimelineMap, VideoTimeline


def _make_mock_timeline():
    """Build a minimal TimelineMap with one video_segment entry."""
    entry = TimelineEntry(
        start_time=datetime.datetime(2024, 7, 15, 12, 0, 0),
        duration_seconds=120.0,
        kind="video_segment",
        source_path=Path("video.mp4"),
        trim_start=0.0,
        trim_end=120.0,
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


def _mock_catalog(mock_timeline):
    mock = MagicMock()
    mock.timeline.return_value = mock_timeline
    mock.pairs = [
        (Path("video.mp4"), MagicMock()),
        (Path("photo.jpg"), MagicMock()),
    ]
    return mock


def test_stitch_draft_flag():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("video.mp4").touch()
        Path("photo.jpg").touch()

        mock_timeline = _make_mock_timeline()
        mock_cat = _mock_catalog(mock_timeline)

        with patch("photowalk.cli.MediaCatalog.scan", return_value=mock_cat):
            with patch("photowalk.use_cases.stitch.stitch") as mock_stitch:
                mock_stitch.return_value = True
                result = runner.invoke(main, [
                    "stitch", ".", "--output", "out.mp4", "--draft"
                ])

    assert result.exit_code == 0
    mock_stitch.assert_called_once()
    _, kwargs = mock_stitch.call_args
    assert kwargs["draft"] is True
    # The echo must reflect the reduced draft resolution, not the original 1920x1080
    assert "1280x720" in result.output


def test_stitch_dry_run():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("video.mp4").touch()
        Path("photo.jpg").touch()

        mock_timeline = _make_mock_timeline()
        mock_cat = _mock_catalog(mock_timeline)

        with patch("photowalk.cli.MediaCatalog.scan", return_value=mock_cat):
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
        mock_cat = _mock_catalog(mock_timeline)

        with patch("photowalk.cli.MediaCatalog.scan", return_value=mock_cat):
            result = runner.invoke(main, ["stitch", ".", "--output", "out.mp4", "--format", "bad"])
    assert result.exit_code == 1
    assert "1920x1080" in result.output or "WIDTHxHEIGHT" in result.output


def test_stitch_plan_writes_json():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("video.mp4").touch()
        Path("photo.jpg").touch()

        mock_timeline = _make_mock_timeline()
        mock_cat = _mock_catalog(mock_timeline)

        with patch("photowalk.cli.MediaCatalog.scan", return_value=mock_cat):
            result = runner.invoke(main, [
                "stitch", ".", "--output", "out.mp4", "--plan", "plan.json"
            ])

        assert result.exit_code == 0
        assert Path("plan.json").exists()

        import json
        plan = json.loads(Path("plan.json").read_text())
        assert plan["settings"]["output"] == "out.mp4"
        assert len(plan["timeline"]) == 1
        assert plan["timeline"][0]["kind"] == "video_segment"
        assert "ffmpeg_commands" in plan
        assert "temp_dir" in plan


def test_stitch_plan_no_video_generation():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("video.mp4").touch()

        mock_timeline = _make_mock_timeline()
        mock_cat = _mock_catalog(mock_timeline)

        with patch("photowalk.cli.MediaCatalog.scan", return_value=mock_cat):
            with patch("photowalk.use_cases.stitch.stitch") as mock_stitch:
                result = runner.invoke(main, [
                    "stitch", ".", "--output", "out.mp4", "--plan", "plan.json"
                ])

    assert result.exit_code == 0
    mock_stitch.assert_not_called()
    assert not Path("out.mp4").exists()
