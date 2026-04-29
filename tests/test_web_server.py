import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from photowalk.timeline import TimelineMap, TimelineEntry
from photowalk.web.server import create_app


def test_index_returns_html():
    app = create_app(set(), TimelineMap())
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Timeline Preview" in response.text


def test_api_timeline():
    entry = TimelineEntry(
        start_time=datetime(2024, 6, 15, 14, 0, 0),
        duration_seconds=45.0,
        kind="video_segment",
        source_path=Path("/tmp/video.mp4"),
        original_video=Path("/tmp/video.mp4"),
        trim_start=0.0,
        trim_end=45.0,
    )
    timeline = TimelineMap(all_entries=[entry])
    app = create_app({Path("/tmp/video.mp4")}, timeline, image_duration=3.5)
    client = TestClient(app)
    response = client.get("/api/timeline")
    assert response.status_code == 200
    data = response.json()
    assert data["settings"]["image_duration"] == 3.5
    assert len(data["entries"]) == 1
    assert data["entries"][0]["kind"] == "video_segment"
    assert data["entries"][0]["duration_seconds"] == 45.0


def test_api_files(tmp_path):
    img = tmp_path / "photo.jpg"
    img.write_text("fake")
    timeline = TimelineMap()
    app = create_app({img}, timeline)
    client = TestClient(app)
    response = client.get("/api/files")
    assert response.status_code == 200
    data = response.json()
    assert "files" in data


def test_media_serves_allowed_file(tmp_path):
    file_path = tmp_path / "allowed.mp4"
    file_path.write_text("fake video content")
    timeline = TimelineMap()
    app = create_app({file_path}, timeline)
    client = TestClient(app)
    response = client.get(f"/media/{file_path}")
    assert response.status_code == 200
    assert response.text == "fake video content"


def test_media_rejects_path_outside_scan_set(tmp_path):
    file_path = tmp_path / "secret.txt"
    file_path.write_text("secret")
    timeline = TimelineMap()
    app = create_app(set(), timeline)
    client = TestClient(app)
    response = client.get(f"/media/{file_path}")
    assert response.status_code == 404


def test_media_rejects_nonexistent_file(tmp_path):
    file_path = tmp_path / "missing.mp4"
    timeline = TimelineMap()
    app = create_app({file_path}, timeline)
    client = TestClient(app)
    response = client.get(f"/media/{file_path}")
    assert response.status_code == 404
