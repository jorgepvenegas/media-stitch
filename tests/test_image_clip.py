import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

from photowalk.image_clip import compute_scaled_dimensions, generate_image_clip


def test_scale_landscape_to_landscape():
    # 4:3 image into 16:9 frame — 70% of frame (15% margin each side)
    # available = 1344x756, scale = min(1344/4000, 756/3000) = 0.252
    w, h = compute_scaled_dimensions(4000, 3000, 1920, 1080)
    assert w == 1008
    assert h == 756


def test_scale_portrait_to_landscape():
    # 3:4 image into 16:9 frame — 70% of frame (15% margin each side)
    # available = 1344x756, scale = min(1344/3000, 756/4000) = 0.189
    w, h = compute_scaled_dimensions(3000, 4000, 1920, 1080)
    assert w == 567
    assert h == 756


def test_scale_landscape_to_portrait():
    # 16:9 image into 9:16 frame — 70% of frame (15% margin each side)
    # available = 756x1344, scale = min(756/1920, 1344/1080) = 0.39375
    w, h = compute_scaled_dimensions(1920, 1080, 1080, 1920)
    assert w == 756
    assert h == 425


def test_scale_portrait_to_portrait():
    # 3:4 image into 9:16 frame — 70% of frame (15% margin each side)
    # available = 756x1344, scale = min(756/3000, 1344/4000) = 0.252
    w, h = compute_scaled_dimensions(3000, 4000, 1080, 1920)
    assert w == 756
    assert h == 1008


def test_scale_with_custom_margin():
    # 4:3 image into 16:9 frame with 10% margin (80% fill)
    # available = 1536x864, scale = min(1536/4000, 864/3000) = 0.288
    w, h = compute_scaled_dimensions(4000, 3000, 1920, 1080, margin=10.0)
    assert w == 1152
    assert h == 863  # 3000 * 0.288 = 864, but float precision gives 863


def test_scale_with_zero_margin():
    # 4:3 image into 16:9 frame with 0% margin (100% fill)
    # available = 1920x1080, scale = min(1920/4000, 1080/3000) = 0.36
    w, h = compute_scaled_dimensions(4000, 3000, 1920, 1080, margin=0.0)
    assert w == 1440
    assert h == 1080


def test_generate_image_clip_ffmpeg_command():
    with patch("photowalk.image_clip.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_img.size = (4000, 3000)
        mock_open.return_value.__enter__.return_value = mock_img

        with patch("photowalk.image_clip._run_ffmpeg_cmd") as mock_run:
            mock_run.return_value = True
            result = generate_image_clip(
                Path("photo.jpg"), Path("clip.mp4"), 1920, 1080, duration=3.5
            )

    assert result is True
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    assert "-loop" in cmd
    assert "photo.jpg" in cmd
    filter_str = cmd[cmd.index("-vf") + 1]
    assert "1920x1080" in filter_str
    assert "(main_w-overlay_w)/2" in filter_str
    assert "(main_h-overlay_h)/2" in filter_str


def test_generate_image_clip_returns_false_on_nonzero_returncode():
    with patch("photowalk.image_clip.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_img.size = (1920, 1080)
        mock_open.return_value.__enter__.return_value = mock_img

        with patch("photowalk.image_clip._run_ffmpeg_cmd") as mock_run:
            mock_run.return_value = False
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

        with patch("photowalk.image_clip._run_ffmpeg_cmd") as mock_run:
            mock_run.return_value = True
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
            "photowalk.image_clip._run_ffmpeg_cmd",
            side_effect=RuntimeError("ffmpeg not found"),
        ):
            try:
                generate_image_clip(Path("photo.jpg"), Path("clip.mp4"), 1920, 1080)
                assert False, "Expected RuntimeError"
            except RuntimeError as e:
                assert "ffmpeg" in str(e).lower()


def test_generate_image_clip_cancelled_before_run():
    with patch("photowalk.image_clip.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_img.size = (1920, 1080)
        mock_open.return_value.__enter__.return_value = mock_img

        with patch("photowalk.image_clip._run_ffmpeg_cmd") as mock_run:
            mock_run.return_value = True
            cancel_event = threading.Event()
            cancel_event.set()

            result = generate_image_clip(
                Path("photo.jpg"), Path("clip.mp4"), 1920, 1080,
                cancel_event=cancel_event,
            )

    assert result is False
    mock_run.assert_not_called()


def test_generate_image_clip_passes_cancel_event():
    with patch("photowalk.image_clip.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_img.size = (1920, 1080)
        mock_open.return_value.__enter__.return_value = mock_img

        with patch("photowalk.image_clip._run_ffmpeg_cmd") as mock_run:
            mock_run.return_value = True
            cancel_event = threading.Event()

            result = generate_image_clip(
                Path("photo.jpg"), Path("clip.mp4"), 1920, 1080,
                cancel_event=cancel_event,
            )

    assert result is True
    mock_run.assert_called_once()
    _, kwargs = mock_run.call_args
    assert kwargs["cancel_event"] is cancel_event
