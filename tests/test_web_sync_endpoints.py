from pydantic import ValidationError
import pytest

from photowalk.web.sync_models import (
    DurationSource,
    ReferenceSource,
    OffsetEntry,
    ParseRequest,
    PreviewRequest,
    ApplyRequest,
)


def test_duration_source_parses():
    src = DurationSource(kind="duration", text="-8h23m5s")
    assert src.text == "-8h23m5s"


def test_reference_source_parses():
    src = ReferenceSource(
        kind="reference",
        wrong="2026-04-27T23:28:01+00:00",
        correct="2026-04-27T07:05:00",
    )
    assert src.wrong.startswith("2026")


def test_offset_entry_with_duration_source():
    entry = OffsetEntry(
        id="abc",
        delta_seconds=-30185.0,
        source={"kind": "duration", "text": "-8h23m5s"},
        target_paths=["/tmp/a.jpg", "/tmp/b.mp4"],
    )
    assert entry.delta_seconds == -30185.0
    assert len(entry.target_paths) == 2


def test_parse_request_duration():
    req = ParseRequest.model_validate(
        {"kind": "duration", "text": "+2h"}
    )
    assert req.root.kind == "duration"


def test_parse_request_reference():
    req = ParseRequest.model_validate(
        {"kind": "reference", "wrong": "2026-04-27T23:28:01", "correct": "2026-04-27T07:05:00"}
    )
    assert req.root.kind == "reference"


def test_preview_request_accepts_empty_stack():
    req = PreviewRequest(offsets=[])
    assert req.offsets == []


def test_preview_request_rejects_missing_field():
    with pytest.raises(ValidationError):
        PreviewRequest.model_validate({})


def test_apply_request_same_shape_as_preview():
    req = ApplyRequest(offsets=[])
    assert req.offsets == []
