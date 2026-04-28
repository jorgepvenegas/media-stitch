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


def test_build_concat_list_no_duration_or_trailing_duplicate():
    """Pre-rendered clips have embedded duration; the list should be one
    `file` line per entry, no `duration` directives, no trailing duplicate."""
    entries = [
        TimelineEntry(
            start_time=datetime(2024, 7, 15, 12, 0, 0),
            duration_seconds=5.0,
            kind="video_segment",
            source_path=Path("a.mp4"),
            clip_path=Path("a.mp4"),
        ),
        TimelineEntry(
            start_time=datetime(2024, 7, 15, 12, 0, 5),
            duration_seconds=3.5,
            kind="image",
            source_path=Path("b.jpg"),
            clip_path=Path("b.mp4"),
        ),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        list_path = Path(tmp) / "list.txt"
        build_concat_list(entries, list_path)

        content = list_path.read_text()
        assert "duration" not in content
        assert content.count("a.mp4") == 1
        assert content.count("b.mp4") == 1


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

    # Verify the split command re-encodes (not -c copy) with scale filter
    split_cmd = mock_run.call_args_list[0][0][0]
    assert "libx264" in split_cmd
    assert "scale=" in split_cmd[split_cmd.index("-vf") + 1]
    assert "pad=" in split_cmd[split_cmd.index("-vf") + 1]


def test_compute_draft_resolution_scales_down():
    from photowalk.stitcher import _compute_draft_resolution
    assert _compute_draft_resolution(1920, 1080) == (1280, 720)


def test_compute_draft_resolution_preserves_small():
    from photowalk.stitcher import _compute_draft_resolution
    assert _compute_draft_resolution(640, 480) == (640, 480)


def test_compute_draft_resolution_preserves_aspect_ratio():
    from photowalk.stitcher import _compute_draft_resolution
    w, h = _compute_draft_resolution(1920, 1080)
    assert w == 1280
    assert h == 720
