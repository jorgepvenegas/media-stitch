import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from photowalk.models import PhotoMetadata
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


def test_assets_serve_css_and_js():
    app = create_app(set(), TimelineMap())
    client = TestClient(app)
    css = client.get("/assets/style.css")
    assert css.status_code == 200
    assert "text/css" in css.headers["content-type"]
    js = client.get("/assets/app.js")
    assert js.status_code == 200
    assert "javascript" in js.headers["content-type"]


def test_app_state_holds_metadata_pairs():
    img = Path("/tmp/photo.jpg")
    meta = PhotoMetadata(source_path=img, timestamp=datetime(2024, 1, 1, 12, 0, 0))
    timeline = TimelineMap()
    app = create_app({img}, timeline, metadata_pairs=[(img, meta)])
    assert app.state.metadata_pairs == [(img, meta)]
    assert app.state.image_duration == 3.5


def test_api_files_includes_camera_fields_for_photos(tmp_path):
    img = Path("/tmp/photo.jpg")
    meta = PhotoMetadata(
        source_path=img,
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        camera_model="Canon EOS R6",
        shutter_speed="1/250",
        iso=400,
        focal_length="35mm",
    )
    timeline = TimelineMap()
    file_entry = {
        "path": str(img),
        "type": "photo",
        "timestamp": "2024-01-01T12:00:00",
        "duration_seconds": None,
        "has_timestamp": True,
        "shifted": False,
        "camera_model": "Canon EOS R6",
        "shutter_speed": "1/250",
        "iso": 400,
        "focal_length": "35mm",
    }
    app = create_app(
        {img}, timeline, metadata_pairs=[(img, meta)], file_list=[file_entry]
    )
    client = TestClient(app)
    response = client.get("/api/files")
    files = response.json()["files"]
    assert files[0]["camera_model"] == "Canon EOS R6"
    assert files[0]["shutter_speed"] == "1/250"
    assert files[0]["iso"] == 400
    assert files[0]["focal_length"] == "35mm"
