import pytest
from pydantic import ValidationError

from photowalk.web.stitch_models import StitchRequest, StitchStatus


def test_stitch_request_valid():
    req = StitchRequest(output="/tmp/out.mp4")
    assert req.output == "/tmp/out.mp4"
    assert req.draft is False
    assert req.image_duration == 3.5


def test_stitch_request_format_ok():
    req = StitchRequest(output="/tmp/out.mp4", format="1920x1080")
    assert req.format == "1920x1080"


def test_stitch_request_format_invalid():
    with pytest.raises(ValidationError):
        StitchRequest(output="/tmp/out.mp4", format="abc")


def test_stitch_request_format_partial():
    with pytest.raises(ValidationError):
        StitchRequest(output="/tmp/out.mp4", format="1920x")


def test_stitch_status_serialization():
    status = StitchStatus(state="running", message="Stitching...")
    d = status.model_dump()
    assert d["state"] == "running"
    assert d["message"] == "Stitching..."


import asyncio
import threading
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from photowalk.timeline import TimelineMap, TimelineEntry
from photowalk.web.stitch_models import StitchRequest
from photowalk.web.stitch_runner import StitchJob, start_stitch, cancel_stitch


def _make_timeline():
    entry = TimelineEntry(
        start_time=datetime(2024, 7, 15, 12, 0, 0),
        duration_seconds=3.5,
        kind="image",
        source_path=Path("/tmp/photo.jpg"),
    )
    return TimelineMap(standalone_images=[entry], all_entries=[entry])


def test_start_stitch_runs_in_background():
    timeline = _make_timeline()
    req = StitchRequest(output="/tmp/out.mp4")

    with patch("photowalk.web.stitch_runner.stitch", return_value=True) as mock_stitch:
        job = start_stitch(timeline, req)
        assert job.state == "running"
        # Wait for async task to complete
        asyncio.get_event_loop().run_until_complete(job.task)

    assert job.state == "done"
    assert job.message == "Render complete"
    assert str(job.output_path) == "/tmp/out.mp4"
    mock_stitch.assert_called_once()


def test_start_stitch_sets_error_on_failure():
    timeline = _make_timeline()
    req = StitchRequest(output="/tmp/out.mp4")

    with patch("photowalk.web.stitch_runner.stitch", return_value=False):
        job = start_stitch(timeline, req)
        asyncio.get_event_loop().run_until_complete(job.task)

    assert job.state == "error"
    assert "failed" in job.message.lower()


def test_start_stitch_sets_error_on_exception():
    timeline = _make_timeline()
    req = StitchRequest(output="/tmp/out.mp4")

    with patch("photowalk.web.stitch_runner.stitch", side_effect=RuntimeError("boom")):
        job = start_stitch(timeline, req)
        asyncio.get_event_loop().run_until_complete(job.task)

    assert job.state == "error"
    assert "boom" in job.message


def test_cancel_stitch_sets_cancelled():
    timeline = _make_timeline()
    req = StitchRequest(output="/tmp/out.mp4")

    def slow_stitch(*args, **kwargs):
        import time
        for _ in range(20):
            if kwargs.get("cancel_event") and kwargs["cancel_event"].is_set():
                return False
            time.sleep(0.05)
        return True

    with patch("photowalk.web.stitch_runner.stitch", side_effect=slow_stitch):
        job = start_stitch(timeline, req)
        import time
        time.sleep(0.1)
        cancel_stitch(job)
        asyncio.get_event_loop().run_until_complete(job.task)

    assert job.state == "cancelled"
    assert job.cancel_event.is_set()
