"""Integration tests: sync apply followed by stitch must use updated timeline."""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from photowalk.catalog import MediaCatalog
from photowalk.models import PhotoMetadata
from photowalk.timeline import TimelineMap
from photowalk.web.server import create_app


def test_apply_rebuilds_timeline_map_for_stitch(monkeypatch):
    """After applying offsets, the session's timeline_map must reflect the new
    timestamps so that a subsequent stitch uses the updated order."""
    a = Path("/tmp/a.jpg")
    b = Path("/tmp/b.jpg")
    initial_a = PhotoMetadata(source_path=a, timestamp=datetime(2024, 1, 1, 12, 0, 0))
    initial_b = PhotoMetadata(source_path=b, timestamp=datetime(2024, 1, 1, 13, 0, 0))
    refreshed_a = PhotoMetadata(source_path=a, timestamp=datetime(2024, 1, 1, 14, 0, 0))

    pairs = [(a, initial_a), (b, initial_b)]
    app = create_app({a, b}, TimelineMap(), catalog=MediaCatalog(pairs))

    monkeypatch.setattr("photowalk.web.server.write_photo_timestamp", lambda p, d: True)
    monkeypatch.setattr("photowalk.web.server.write_video_timestamp", lambda p, d: True)
    monkeypatch.setattr(
        "photowalk.catalog.extract_metadata",
        lambda p: refreshed_a if p == a else initial_b,
    )

    client = TestClient(app)
    client.post(
        "/api/sync/apply",
        json={
            "offsets": [
                {
                    "id": "1",
                    "delta_seconds": 7200.0,
                    "source": {"kind": "duration", "text": "+2h"},
                    "target_paths": [str(a)],
                }
            ]
        },
    )

    # After apply, the order should be b (13:00) then a (14:00).
    entries = app.state.session.timeline_map.all_entries
    assert len(entries) == 2
    assert entries[0].source_path == b
    assert entries[1].source_path == a


def test_stitch_receives_updated_timeline_after_apply(monkeypatch):
    """The stitch job must receive a TimelineMap whose entries reflect applied
    offsets, not the original startup state."""
    a = Path("/tmp/a.jpg")
    b = Path("/tmp/b.jpg")
    initial_a = PhotoMetadata(source_path=a, timestamp=datetime(2024, 1, 1, 12, 0, 0))
    initial_b = PhotoMetadata(source_path=b, timestamp=datetime(2024, 1, 1, 13, 0, 0))
    refreshed_a = PhotoMetadata(source_path=a, timestamp=datetime(2024, 1, 1, 14, 0, 0))

    pairs = [(a, initial_a), (b, initial_b)]
    app = create_app({a, b}, TimelineMap(), catalog=MediaCatalog(pairs))

    monkeypatch.setattr("photowalk.web.server.write_photo_timestamp", lambda p, d: True)
    monkeypatch.setattr("photowalk.web.server.write_video_timestamp", lambda p, d: True)
    monkeypatch.setattr(
        "photowalk.catalog.extract_metadata",
        lambda p: refreshed_a if p == a else initial_b,
    )

    client = TestClient(app)
    client.post(
        "/api/sync/apply",
        json={
            "offsets": [
                {
                    "id": "1",
                    "delta_seconds": 7200.0,
                    "source": {"kind": "duration", "text": "+2h"},
                    "target_paths": [str(a)],
                }
            ]
        },
    )

    with patch("photowalk.web.server.stitch") as mock_stitch:
        mock_stitch.return_value = True
        r = client.post("/api/stitch", json={"output": "/tmp/out.mp4"})
        assert r.status_code == 200

        # The stitch thread may still be starting; give it a moment.
        import time
        time.sleep(0.15)

        mock_stitch.assert_called_once()
        timeline_arg = mock_stitch.call_args[0][0]
        entries = timeline_arg.all_entries
        assert len(entries) == 2
        assert entries[0].source_path == b
        assert entries[1].source_path == a
