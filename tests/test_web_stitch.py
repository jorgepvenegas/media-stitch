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
