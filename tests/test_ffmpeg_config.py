import subprocess
import threading
from unittest.mock import patch, MagicMock

import pytest

from photowalk.ffmpeg_config import _run_ffmpeg_cmd


def test_run_ffmpeg_cmd_success():
    with patch("photowalk.ffmpeg_config.subprocess.Popen") as mock_popen:
        proc = MagicMock()
        proc.wait.return_value = None
        proc.returncode = 0
        mock_popen.return_value = proc

        result = _run_ffmpeg_cmd(["ffmpeg", "-version"])
        assert result is True


def test_run_ffmpeg_cmd_failure():
    with patch("photowalk.ffmpeg_config.subprocess.Popen") as mock_popen:
        proc = MagicMock()
        proc.wait.return_value = None
        proc.returncode = 1
        proc.stderr = None
        mock_popen.return_value = proc

        result = _run_ffmpeg_cmd(["ffmpeg", "-version"])
        assert result is False


def test_run_ffmpeg_cmd_cancelled():
    with patch("photowalk.ffmpeg_config.subprocess.Popen") as mock_popen:
        proc = MagicMock()
        # Simulate a slow process: first wait times out, then we cancel
        proc.wait.side_effect = [
            subprocess.TimeoutExpired(cmd=["ffmpeg"], timeout=0.5),  # first wait times out
            None,  # second wait (post-terminate) succeeds
        ]
        proc.poll.return_value = None  # still running after first timeout
        proc.terminate.return_value = None
        mock_popen.return_value = proc

        cancel_event = threading.Event()
        cancel_event.set()

        result = _run_ffmpeg_cmd(["ffmpeg", "-version"], cancel_event=cancel_event)
        assert result is False
        proc.terminate.assert_called_once()


def test_run_ffmpeg_cmd_missing_ffmpeg():
    with patch("photowalk.ffmpeg_config.subprocess.Popen", side_effect=FileNotFoundError):
        with pytest.raises(RuntimeError, match="ffmpeg"):
            _run_ffmpeg_cmd(["ffmpeg", "-version"])
