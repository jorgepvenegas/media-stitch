from pathlib import Path
from unittest.mock import patch, MagicMock

from photowalk.image_clip import compute_scaled_dimensions, generate_image_clip


def test_scale_landscape_to_landscape():
    # 4:3 image into 16:9 frame — should fit by height
    w, h = compute_scaled_dimensions(4000, 3000, 1920, 1080)
    assert w == 1440
    assert h == 1080


def test_scale_portrait_to_landscape():
    # 3:4 image into 16:9 frame — should fit by height
    w, h = compute_scaled_dimensions(3000, 4000, 1920, 1080)
    assert w == 810
    assert h == 1080


def test_scale_landscape_to_portrait():
    # 16:9 image into 9:16 frame — should fit by width
    w, h = compute_scaled_dimensions(1920, 1080, 1080, 1920)
    assert w == 1080
    assert h == 607


def test_generate_image_clip_ffmpeg_command():
    with patch("photowalk.image_clip.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_img.size = (4000, 3000)
        mock_open.return_value.__enter__.return_value = mock_img

        with patch("photowalk.image_clip.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = generate_image_clip(
                Path("photo.jpg"), Path("clip.mp4"), 1920, 1080, duration=3.5
            )

    assert result is True
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    assert "-loop" in cmd
    assert "photo.jpg" in cmd
    assert "1920x1080" in cmd[cmd.index("-vf") + 1]


def test_generate_image_clip_returns_false_on_nonzero_returncode():
    with patch("photowalk.image_clip.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_img.size = (1920, 1080)
        mock_open.return_value.__enter__.return_value = mock_img

        with patch("photowalk.image_clip.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = generate_image_clip(
                Path("photo.jpg"), Path("clip.mp4"), 1920, 1080
            )

    assert result is False


def test_generate_image_clip_returns_false_on_image_open_error():
    with patch("photowalk.image_clip.Image.open", side_effect=Exception("cannot open")):
        result = generate_image_clip(Path("bad.jpg"), Path("clip.mp4"), 1920, 1080)

    assert result is False


def test_generate_image_clip_uses_custom_encode_config():
    from photowalk.ffmpeg_config import FfmpegEncodeConfig

    with patch("photowalk.image_clip.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_img.size = (1920, 1080)
        mock_open.return_value.__enter__.return_value = mock_img

        with patch("photowalk.image_clip.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = generate_image_clip(
                Path("photo.jpg"), Path("clip.mp4"), 1920, 1080,
                encode_config=FfmpegEncodeConfig.draft(),
            )

    assert result is True
    cmd = mock_run.call_args[0][0]
    preset_idx = cmd.index("-preset")
    assert cmd[preset_idx + 1] == "ultrafast"
    crf_idx = cmd.index("-crf")
    assert cmd[crf_idx + 1] == "28"


def test_generate_image_clip_raises_runtime_error_when_ffmpeg_missing():
    with patch("photowalk.image_clip.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_img.size = (1920, 1080)
        mock_open.return_value.__enter__.return_value = mock_img

        with patch(
            "photowalk.image_clip.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            try:
                generate_image_clip(Path("photo.jpg"), Path("clip.mp4"), 1920, 1080)
                assert False, "Expected RuntimeError"
            except RuntimeError as e:
                assert "ffmpeg" in str(e).lower()
