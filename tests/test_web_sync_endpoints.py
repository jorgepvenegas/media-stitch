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


from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from photowalk.models import PhotoMetadata
from photowalk.timeline import TimelineMap
from photowalk.web.server import create_app


def _client():
    return TestClient(create_app(set(), TimelineMap()))


def test_parse_duration_ok():
    r = _client().post(
        "/api/offset/parse",
        json={"kind": "duration", "text": "+2h"},
    )
    assert r.status_code == 200
    assert r.json()["delta_seconds"] == 7200.0


def test_parse_duration_negative():
    r = _client().post(
        "/api/offset/parse",
        json={"kind": "duration", "text": "-30m"},
    )
    assert r.status_code == 200
    assert r.json()["delta_seconds"] == -1800.0


def test_parse_duration_invalid_returns_error():
    r = _client().post(
        "/api/offset/parse",
        json={"kind": "duration", "text": "not-a-duration"},
    )
    assert r.status_code == 200
    assert "error" in r.json()


def test_parse_reference_ok():
    r = _client().post(
        "/api/offset/parse",
        json={
            "kind": "reference",
            "wrong": "2026-04-27T23:28:01+00:00",
            "correct": "2026-04-27T07:05:00+00:00",
        },
    )
    assert r.status_code == 200
    assert r.json()["delta_seconds"] == -58981.0


def test_parse_reference_zero_delta_is_error():
    r = _client().post(
        "/api/offset/parse",
        json={
            "kind": "reference",
            "wrong": "2026-04-27T07:05:00+00:00",
            "correct": "2026-04-27T07:05:00+00:00",
        },
    )
    assert r.status_code == 200
    assert "error" in r.json()


def test_parse_reference_invalid_timestamp_returns_error():
    r = _client().post(
        "/api/offset/parse",
        json={
            "kind": "reference",
            "wrong": "garbage",
            "correct": "2026-04-27T07:05:00",
        },
    )
    assert r.status_code == 200
    assert "error" in r.json()


def _client_with_pairs(pairs):
    timeline = TimelineMap()
    app = create_app(
        {p for p, _ in pairs},
        timeline,
        metadata_pairs=pairs,
    )
    return TestClient(app)


def test_preview_empty_stack_returns_unshifted():
    img = Path("/tmp/a.jpg")
    pairs = [(img, PhotoMetadata(source_path=img, timestamp=datetime(2024, 1, 1, 12, 0, 0)))]
    r = _client_with_pairs(pairs).post("/api/timeline/preview", json={"offsets": []})
    assert r.status_code == 200
    body = r.json()
    assert body["files"][0]["shifted"] is False
    assert body["files"][0]["timestamp"] == "2024-01-01T12:00:00"


def test_preview_with_offset_shifts_file():
    img = Path("/tmp/a.jpg")
    pairs = [(img, PhotoMetadata(source_path=img, timestamp=datetime(2024, 1, 1, 12, 0, 0)))]
    r = _client_with_pairs(pairs).post(
        "/api/timeline/preview",
        json={
            "offsets": [{
                "id": "1",
                "delta_seconds": 3600.0,
                "source": {"kind": "duration", "text": "+1h"},
                "target_paths": ["/tmp/a.jpg"],
            }]
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["files"][0]["shifted"] is True
    assert body["files"][0]["timestamp"] == "2024-01-01T13:00:00"


def test_preview_multi_entry_composes():
    img = Path("/tmp/a.jpg")
    pairs = [(img, PhotoMetadata(source_path=img, timestamp=datetime(2024, 1, 1, 12, 0, 0)))]
    r = _client_with_pairs(pairs).post(
        "/api/timeline/preview",
        json={
            "offsets": [
                {
                    "id": "1",
                    "delta_seconds": 3600.0,
                    "source": {"kind": "duration", "text": "+1h"},
                    "target_paths": ["/tmp/a.jpg"],
                },
                {
                    "id": "2",
                    "delta_seconds": -1800.0,
                    "source": {"kind": "duration", "text": "-30m"},
                    "target_paths": ["/tmp/a.jpg"],
                },
            ]
        },
    )
    assert r.json()["files"][0]["timestamp"] == "2024-01-01T12:30:00"
