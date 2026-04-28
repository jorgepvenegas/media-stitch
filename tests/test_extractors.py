from pathlib import Path
from unittest.mock import patch, MagicMock

from photowalk.extractors import run_ffprobe
from photowalk.ffmpeg_config import ffmpeg_not_found_error


def test_run_ffprobe_success():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"format": {"filename": "test.jpg"}}'
    mock_result.stderr = ""

    with patch("photowalk.extractors.subprocess.run", return_value=mock_result) as mock_run:
        result = run_ffprobe(Path("/tmp/test.jpg"))

    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0][0] == "ffprobe"
    assert "-print_format" in call_args[0][0]
    assert "json" in call_args[0][0]
    assert "-show_format" in call_args[0][0]
    assert "-show_streams" in call_args[0][0]
    assert result == {"format": {"filename": "test.jpg"}}


def test_run_ffprobe_failure():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "Error reading file"

    with patch("photowalk.extractors.subprocess.run", return_value=mock_result):
        result = run_ffprobe(Path("/tmp/bad.jpg"))

    assert result is None


def test_run_ffprobe_file_not_found():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "No such file or directory"

    with patch("photowalk.extractors.subprocess.run", return_value=mock_result):
        result = run_ffprobe(Path("/tmp/missing.jpg"))

    assert result is None


def test_ffmpeg_not_found_error():
    assert "ffmpeg" in ffmpeg_not_found_error()
    assert "FFmpeg" in ffmpeg_not_found_error()
