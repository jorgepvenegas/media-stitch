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


def test_preview_with_custom_image_duration():
    """Preview request can override the default image_duration."""
    img = Path("/tmp/a.jpg")
    pairs = [(img, PhotoMetadata(source_path=img, timestamp=datetime(2024, 1, 1, 12, 0, 0)))]
    r = _client_with_pairs(pairs).post("/api/timeline/preview", json={
        "offsets": [],
        "image_duration": 7.5,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["settings"]["image_duration"] == 7.5


def test_preview_fallback_image_duration():
    """Preview without image_duration falls back to the app default."""
    img = Path("/tmp/a.jpg")
    pairs = [(img, PhotoMetadata(source_path=img, timestamp=datetime(2024, 1, 1, 12, 0, 0)))]
    r = _client_with_pairs(pairs).post("/api/timeline/preview", json={
        "offsets": [],
    })
    assert r.status_code == 200
    data = r.json()
    assert data["settings"]["image_duration"] == 3.5


def test_apply_calls_writers_and_refreshes_state(monkeypatch):
    img = Path("/tmp/a.jpg")
    initial = PhotoMetadata(source_path=img, timestamp=datetime(2024, 1, 1, 12, 0, 0))
    refreshed = PhotoMetadata(source_path=img, timestamp=datetime(2024, 1, 1, 13, 0, 0))
    pairs = [(img, initial)]

    timeline = TimelineMap()
    app = create_app({img}, timeline, metadata_pairs=pairs)

    photo_calls: list = []

    def fake_write_photo(path, dt):
        photo_calls.append((str(path), dt))
        return True

    def fake_extract(path):
        return refreshed

    monkeypatch.setattr("photowalk.web.server.write_photo_timestamp", fake_write_photo)
    monkeypatch.setattr("photowalk.web.server.write_video_timestamp", lambda p, d: True)
    monkeypatch.setattr("photowalk.web.server.extract_metadata", fake_extract)

    client = TestClient(app)
    r = client.post(
        "/api/sync/apply",
        json={
            "offsets": [{
                "id": "1",
                "delta_seconds": 3600.0,
                "source": {"kind": "duration", "text": "+1h"},
                "target_paths": [str(img)],
            }]
        },
    )

    assert r.status_code == 200
    body = r.json()
    assert photo_calls == [(str(img), datetime(2024, 1, 1, 13, 0, 0))]
    assert len(body["applied"]) == 1
    assert body["applied"][0]["new_ts"] == "2024-01-01T13:00:00"
    assert body["failed"] == []
    assert body["files"][0]["timestamp"] == "2024-01-01T13:00:00"
    assert "shifted" in body["files"][0]
    if body["files"][0]["type"] == "photo":
        assert "camera_model" in body["files"][0]
    else:
        assert "end_timestamp" in body["files"][0]
    assert app.state.metadata_pairs[0][1].timestamp == datetime(2024, 1, 1, 13, 0, 0)


def test_apply_partial_failure_returns_both_lists(monkeypatch):
    a = Path("/tmp/a.jpg")
    b = Path("/tmp/b.jpg")
    pairs = [
        (a, PhotoMetadata(source_path=a, timestamp=datetime(2024, 1, 1, 12, 0, 0))),
        (b, PhotoMetadata(source_path=b, timestamp=datetime(2024, 1, 1, 13, 0, 0))),
    ]
    app = create_app({a, b}, TimelineMap(), metadata_pairs=pairs)

    def fake_write_photo(path, dt):
        return str(path) != "/tmp/a.jpg"

    def fake_extract(path):
        if str(path) == "/tmp/a.jpg":
            return PhotoMetadata(source_path=a, timestamp=datetime(2024, 1, 1, 12, 0, 0))
        return PhotoMetadata(source_path=b, timestamp=datetime(2024, 1, 1, 14, 0, 0))

    monkeypatch.setattr("photowalk.web.server.write_photo_timestamp", fake_write_photo)
    monkeypatch.setattr("photowalk.web.server.write_video_timestamp", lambda p, d: True)
    monkeypatch.setattr("photowalk.web.server.extract_metadata", fake_extract)

    r = TestClient(app).post(
        "/api/sync/apply",
        json={
            "offsets": [{
                "id": "1",
                "delta_seconds": 3600.0,
                "source": {"kind": "duration", "text": "+1h"},
                "target_paths": ["/tmp/a.jpg", "/tmp/b.jpg"],
            }]
        },
    )

    body = r.json()
    failed_paths = [f["path"] for f in body["failed"]]
    applied_paths = [a_["path"] for a_ in body["applied"]]
    assert failed_paths == ["/tmp/a.jpg"]
    assert applied_paths == ["/tmp/b.jpg"]


def test_get_files_reflects_disk_after_apply(monkeypatch):
    """After /api/sync/apply, GET /api/files must return refreshed state, not stale closure."""
    img = Path("/tmp/a.jpg")
    initial = PhotoMetadata(source_path=img, timestamp=datetime(2024, 1, 1, 12, 0, 0))
    refreshed = PhotoMetadata(source_path=img, timestamp=datetime(2024, 1, 1, 13, 0, 0))
    pairs = [(img, initial)]

    app = create_app(
        {img},
        TimelineMap(),
        metadata_pairs=pairs,
        file_list=[{
            "path": str(img),
            "type": "photo",
            "timestamp": "2024-01-01T12:00:00",
            "duration_seconds": None,
            "has_timestamp": True,
        }],
    )

    monkeypatch.setattr("photowalk.web.server.write_photo_timestamp", lambda p, d: True)
    monkeypatch.setattr("photowalk.web.server.write_video_timestamp", lambda p, d: True)
    monkeypatch.setattr("photowalk.web.server.extract_metadata", lambda p: refreshed)

    client = TestClient(app)
    client.post(
        "/api/sync/apply",
        json={
            "offsets": [{
                "id": "1",
                "delta_seconds": 3600.0,
                "source": {"kind": "duration", "text": "+1h"},
                "target_paths": [str(img)],
            }]
        },
    )

    r = client.get("/api/files")
    files = r.json()["files"]
    assert files[0]["timestamp"] == "2024-01-01T13:00:00"
    assert "shifted" in files[0]
    if files[0]["type"] == "photo":
        assert "camera_model" in files[0]
    else:
        assert "end_timestamp" in files[0]
