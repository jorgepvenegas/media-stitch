from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

from photowalk.stitcher import build_concat_list, run_concat, stitch
from photowalk.timeline import TimelineEntry, TimelineMap, VideoTimeline


def test_build_concat_list():
    entries = [
        TimelineEntry(
            start_time=datetime(2024, 7, 15, 12, 0, 0),
            duration_seconds=30.0,
            kind="video_segment",
            source_path=Path("video.mp4"),
            clip_path=Path("seg1.mp4"),
        ),
        TimelineEntry(
            start_time=datetime(2024, 7, 15, 12, 0, 30),
            duration_seconds=3.5,
            kind="image",
            source_path=Path("photo.jpg"),
            clip_path=Path("img.mp4"),
        ),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        list_path = Path(tmp) / "list.txt"
        build_concat_list(entries, list_path)

        content = list_path.read_text()
        assert "seg1.mp4" in content
        assert "img.mp4" in content


def test_build_concat_list_uses_source_path_when_no_clip_path():
    entries = [
        TimelineEntry(
            start_time=datetime(2024, 7, 15, 12, 0, 0),
            duration_seconds=10.0,
            kind="video_segment",
            source_path=Path("video.mp4"),
            clip_path=None,
        ),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        list_path = Path(tmp) / "list.txt"
        build_concat_list(entries, list_path)

        content = list_path.read_text()
        assert "video.mp4" in content


def test_build_concat_list_repeats_last_file():
    """ffmpeg concat demuxer requires the last file entry to appear twice."""
    entries = [
        TimelineEntry(
            start_time=datetime(2024, 7, 15, 12, 0, 0),
            duration_seconds=5.0,
            kind="video_segment",
            source_path=Path("only.mp4"),
            clip_path=Path("only.mp4"),
        ),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        list_path = Path(tmp) / "list.txt"
        build_concat_list(entries, list_path)

        content = list_path.read_text()
        # "only.mp4" should appear twice (once with duration, once as trailing file)
        assert content.count("only.mp4") == 2


def test_run_concat_command():
    with patch("photowalk.stitcher.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = run_concat(Path("list.txt"), Path("out.mp4"))

    assert result is True
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    assert "concat" in cmd
    assert "list.txt" in cmd


def test_run_concat_returns_false_on_failure():
    with patch("photowalk.stitcher.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        result = run_concat(Path("list.txt"), Path("out.mp4"))

    assert result is False


def test_run_concat_raises_on_missing_ffmpeg():
    with patch("photowalk.stitcher.subprocess.run", side_effect=FileNotFoundError):
        try:
            run_concat(Path("list.txt"), Path("out.mp4"))
            assert False, "Expected RuntimeError"
        except RuntimeError as e:
            assert "ffmpeg" in str(e).lower()


def test_stitch_success():
    entry = TimelineEntry(
        start_time=datetime(2024, 7, 15, 12, 0, 0),
        duration_seconds=3.5,
        kind="image",
        source_path=Path("photo.jpg"),
    )
    timeline = TimelineMap(
        standalone_images=[entry],
        all_entries=[entry],
    )

    with patch("photowalk.stitcher.generate_image_clip", return_value=True) as mock_clip:
        with patch("photowalk.stitcher.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = stitch(timeline, Path("out.mp4"), 1920, 1080, keep_temp=True)

    assert result is True
    mock_clip.assert_called_once()


def test_stitch_returns_false_when_image_clip_fails():
    entry = TimelineEntry(
        start_time=datetime(2024, 7, 15, 12, 0, 0),
        duration_seconds=3.5,
        kind="image",
        source_path=Path("photo.jpg"),
    )
    timeline = TimelineMap(
        standalone_images=[entry],
        all_entries=[entry],
    )

    with patch("photowalk.stitcher.generate_image_clip", return_value=False):
        result = stitch(timeline, Path("out.mp4"), 1920, 1080, keep_temp=True)

    assert result is False


def test_stitch_video_segment():
    entry = TimelineEntry(
        start_time=datetime(2024, 7, 15, 12, 0, 0),
        duration_seconds=10.0,
        kind="video_segment",
        source_path=Path("video.mp4"),
        trim_start=0.0,
        trim_end=10.0,
    )
    timeline = TimelineMap(
        all_entries=[entry],
    )

    with patch("photowalk.stitcher.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = stitch(timeline, Path("out.mp4"), 1920, 1080, keep_temp=True)

    assert result is True
    # subprocess.run called at least twice: once for split, once for concat
    assert mock_run.call_count >= 2
