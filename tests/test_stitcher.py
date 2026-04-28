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


def test_split_video_segment_uses_custom_preset_and_crf():
    from photowalk.stitcher import _split_video_segment  # internal helper, tested directly
    with patch("photowalk.stitcher.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        _split_video_segment(
            Path("in.mp4"), 0.0, 5.0, Path("out.mp4"), 640, 480,
            preset="ultrafast", crf=28,
        )
    cmd = mock_run.call_args[0][0]
    assert "-preset" in cmd
    preset_idx = cmd.index("-preset")
    assert cmd[preset_idx + 1] == "ultrafast"
    assert "-crf" in cmd
    crf_idx = cmd.index("-crf")
    assert cmd[crf_idx + 1] == "28"


def test_compute_draft_resolution_scales_down():
    from photowalk.stitcher import compute_draft_resolution
    assert compute_draft_resolution(1920, 1080) == (1280, 720)


def test_compute_draft_resolution_preserves_small():
    from photowalk.stitcher import compute_draft_resolution
    assert compute_draft_resolution(640, 480) == (640, 480)


def test_compute_draft_resolution_preserves_aspect_ratio():
    # 2560x1600 is 16:10; height is the limiting axis (1600 * scale > 1280 * scale)
    from photowalk.stitcher import compute_draft_resolution
    w, h = compute_draft_resolution(2560, 1600)
    assert h == 720
    assert w == 1152  # 2560 * (720/1600) = 1152 (even)
    # Aspect ratio preserved to within 1 pixel of rounding
    assert abs(w / h - 2560 / 1600) < 0.01


def test_run_concat_uses_custom_preset_and_crf():
    from photowalk.stitcher import run_concat
    with patch("photowalk.stitcher.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        run_concat(Path("list.txt"), Path("out.mp4"), preset="ultrafast", crf=28)
    cmd = mock_run.call_args[0][0]
    preset_idx = cmd.index("-preset")
    assert cmd[preset_idx + 1] == "ultrafast"
    crf_idx = cmd.index("-crf")
    assert cmd[crf_idx + 1] == "28"


def test_stitch_draft_mode_uses_draft_params():
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
            result = stitch(timeline, Path("out.mp4"), 1920, 1080, draft=True, keep_temp=True)

    assert result is True
    mock_clip.assert_called_once()
    _, kwargs = mock_clip.call_args
    assert kwargs["preset"] == "ultrafast"
    assert kwargs["crf"] == 28

    # Check resolution passed to generate_image_clip is reduced
    args = mock_clip.call_args[0]
    assert args[2] == 1280  # frame_width
    assert args[3] == 720   # frame_height
