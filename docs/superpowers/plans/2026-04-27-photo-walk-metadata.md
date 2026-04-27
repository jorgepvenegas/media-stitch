# Photo Walk Metadata Extraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python library and CLI that extracts timestamps and camera metadata from photos and videos using ffprobe.

**Architecture:** Pure Python with click for CLI, ffprobe via subprocess for media parsing. Typed dataclasses separate raw ffprobe JSON from normalized output. Extension-based media type detection.

**Tech Stack:** Python 3.10+, uv, click, pytest

---

### Task 1: Initialize uv Project

**Files:**
- Create: `pyproject.toml`
- Create: `src/photowalk/__init__.py`
- Create: `tests/__init__.py`
- Modify: `.gitignore`

- [ ] **Step 1: Initialize project with uv**

Run:
```bash
uv init --package --name photowalk --python 3.10 .
```

- [ ] **Step 2: Add runtime and dev dependencies**

Run:
```bash
uv add click
uv add --dev pytest pytest-cov
```

- [ ] **Step 3: Create package init files**

Write `src/photowalk/__init__.py`:
```python
"""Photo Walk — Media metadata extraction using ffprobe."""

__version__ = "0.1.0"
```

Write `tests/__init__.py`:
```python
"""Tests for photowalk."""
```

- [ ] **Step 4: Add .gitignore**

Write `.gitignore`:
```gitignore
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/
.pytest_cache/
.coverage
htmlcov/
.venv/
uv.lock
```

- [ ] **Step 5: Verify project structure**

Run:
```bash
ls -la src/photowalk/ && ls -la tests/ && cat pyproject.toml
```

Expected: `pyproject.toml` exists, `src/photowalk/__init__.py` exists.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "chore: initialize uv project"
```

---

### Task 2: Constants Module

**Files:**
- Create: `src/photowalk/constants.py`
- Test: `tests/test_constants.py`

- [ ] **Step 1: Write failing test**

Write `tests/test_constants.py`:
```python
from photowalk.constants import PHOTO_EXTENSIONS, VIDEO_EXTENSIONS


def test_photo_extensions_is_set():
    assert isinstance(PHOTO_EXTENSIONS, set)
    assert ".jpg" in PHOTO_EXTENSIONS
    assert ".jpeg" in PHOTO_EXTENSIONS


def test_video_extensions_is_set():
    assert isinstance(VIDEO_EXTENSIONS, set)
    assert ".mp4" in VIDEO_EXTENSIONS
    assert ".mov" in VIDEO_EXTENSIONS
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/test_constants.py -v
```

Expected: `ModuleNotFoundError: No module named 'photowalk.constants'`

- [ ] **Step 3: Write minimal implementation**

Write `src/photowalk/constants.py`:
```python
"""File extension constants for media type detection."""

PHOTO_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tiff",
    ".tif",
    ".heic",
    ".heif",
    ".webp",
    ".bmp",
}

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".m4v",
    ".wmv",
    ".flv",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
uv run pytest tests/test_constants.py -v
```

Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_constants.py src/photowalk/constants.py && git commit -m "feat: add media extension constants"
```

---

### Task 3: Data Models

**Files:**
- Create: `src/photowalk/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing test**

Write `tests/test_models.py`:
```python
from datetime import datetime
from pathlib import Path

from photowalk.models import PhotoMetadata, VideoMetadata


def test_photo_metadata_defaults():
    p = PhotoMetadata(source_path=Path("/tmp/test.jpg"))
    assert p.source_path == Path("/tmp/test.jpg")
    assert p.media_type == "photo"
    assert p.timestamp is None
    assert p.camera_model is None
    assert p.shutter_speed is None
    assert p.iso is None
    assert p.focal_length is None


def test_photo_metadata_with_values():
    ts = datetime(2024, 7, 15, 14, 32, 10)
    p = PhotoMetadata(
        source_path=Path("/tmp/test.jpg"),
        timestamp=ts,
        camera_model="Canon EOS R6",
        shutter_speed="1/250",
        iso=400,
        focal_length="35mm",
    )
    assert p.timestamp == ts
    assert p.camera_model == "Canon EOS R6"


def test_photo_metadata_to_dict():
    ts = datetime(2024, 7, 15, 14, 32, 10)
    p = PhotoMetadata(
        source_path=Path("/tmp/test.jpg"),
        timestamp=ts,
        camera_model="Canon EOS R6",
        iso=400,
    )
    d = p.to_dict()
    assert d["source_path"] == "/tmp/test.jpg"
    assert d["media_type"] == "photo"
    assert d["timestamp"] == "2024-07-15T14:32:10"
    assert d["camera_model"] == "Canon EOS R6"
    assert d["iso"] == 400
    assert d["shutter_speed"] is None


def test_video_metadata_defaults():
    v = VideoMetadata(source_path=Path("/tmp/test.mp4"))
    assert v.source_path == Path("/tmp/test.mp4")
    assert v.media_type == "video"
    assert v.start_timestamp is None
    assert v.end_timestamp is None
    assert v.duration_seconds is None


def test_video_metadata_with_values():
    start = datetime(2024, 7, 15, 14, 0, 0)
    end = datetime(2024, 7, 15, 14, 5, 30)
    v = VideoMetadata(
        source_path=Path("/tmp/test.mp4"),
        start_timestamp=start,
        end_timestamp=end,
        duration_seconds=330.0,
    )
    assert v.start_timestamp == start
    assert v.duration_seconds == 330.0


def test_video_metadata_to_dict():
    start = datetime(2024, 7, 15, 14, 0, 0)
    v = VideoMetadata(
        source_path=Path("/tmp/test.mp4"),
        start_timestamp=start,
        duration_seconds=120.5,
    )
    d = v.to_dict()
    assert d["source_path"] == "/tmp/test.mp4"
    assert d["media_type"] == "video"
    assert d["start_timestamp"] == "2024-07-15T14:00:00"
    assert d["duration_seconds"] == 120.5
    assert d["end_timestamp"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'photowalk.models'`

- [ ] **Step 3: Write minimal implementation**

Write `src/photowalk/models.py`:
```python
"""Typed data models for photo and video metadata."""

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


def _serialize(value):
    """Serialize model values for JSON output."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


@dataclass(frozen=True)
class PhotoMetadata:
    source_path: Path
    media_type: str = "photo"
    timestamp: Optional[datetime] = None
    camera_model: Optional[str] = None
    shutter_speed: Optional[str] = None
    iso: Optional[int] = None
    focal_length: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: _serialize(v) for k, v in asdict(self).items()}


@dataclass(frozen=True)
class VideoMetadata:
    source_path: Path
    media_type: str = "video"
    start_timestamp: Optional[datetime] = None
    end_timestamp: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    def to_dict(self) -> dict:
        return {k: _serialize(v) for k, v in asdict(self).items()}
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
uv run pytest tests/test_models.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_models.py src/photowalk/models.py && git commit -m "feat: add PhotoMetadata and VideoMetadata models"
```

---

### Task 4: Extractors (ffprobe Subprocess)

**Files:**
- Create: `src/photowalk/extractors.py`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: Write failing test**

Write `tests/test_extractors.py`:
```python
from pathlib import Path
from unittest.mock import patch, MagicMock

from photowalk.extractors import run_ffprobe, ffprobe_not_found_error


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


def test_ffprobe_not_found_error():
    assert "ffprobe" in ffprobe_not_found_error()
    assert "FFmpeg" in ffprobe_not_found_error()
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/test_extractors.py -v
```

Expected: `ModuleNotFoundError: No module named 'photowalk.extractors'`

- [ ] **Step 3: Write minimal implementation**

Write `src/photowalk/extractors.py`:
```python
"""Low-level ffprobe subprocess wrappers."""

import json
import subprocess
from pathlib import Path
from typing import Optional


def ffprobe_not_found_error() -> str:
    return "ffprobe not found in PATH. Install FFmpeg: https://ffmpeg.org"


def run_ffprobe(path: Path) -> Optional[dict]:
    """Run ffprobe on a file and return parsed JSON, or None on failure."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        raise RuntimeError(ffprobe_not_found_error())

    if result.returncode != 0:
        return None

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
uv run pytest tests/test_extractors.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_extractors.py src/photowalk/extractors.py && git commit -m "feat: add ffprobe extractors"
```

---

### Task 5: Parsers (ffprobe JSON to Models)

**Files:**
- Create: `src/photowalk/parsers.py`
- Create: `tests/fixtures/ffprobe_photo.json`
- Create: `tests/fixtures/ffprobe_video.json`
- Test: `tests/test_parsers.py`

- [ ] **Step 1: Write fixture files**

Write `tests/fixtures/ffprobe_photo.json`:
```json
{
  "format": {
    "filename": "/tmp/photo.jpg",
    "tags": {
      "creation_time": "2024-07-15T14:32:10.000000Z",
      "Make": "Canon",
      "Model": "EOS R6",
      "ExposureTime": "1/250",
      "ISOSpeedRatings": "400",
      "FocalLength": "35mm"
    }
  },
  "streams": []
}
```

Write `tests/fixtures/ffprobe_video.json`:
```json
{
  "format": {
    "filename": "/tmp/video.mp4",
    "duration": "330.500000",
    "tags": {
      "creation_time": "2024-07-15T14:00:00.000000Z"
    }
  },
  "streams": [
    {
      "codec_type": "video",
      "duration": "330.500000"
    }
  ]
}
```

- [ ] **Step 2: Write failing test**

Write `tests/test_parsers.py`:
```python
import json
from datetime import datetime, timezone
from pathlib import Path

from photowalk.parsers import parse_photo, parse_video
from photowalk.models import PhotoMetadata, VideoMetadata

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    with open(FIXTURES / name) as f:
        return json.load(f)


def test_parse_photo_full():
    data = load_fixture("ffprobe_photo.json")
    result = parse_photo(Path("/tmp/photo.jpg"), data)

    assert isinstance(result, PhotoMetadata)
    assert result.source_path == Path("/tmp/photo.jpg")
    assert result.timestamp == datetime(2024, 7, 15, 14, 32, 10, tzinfo=timezone.utc)
    assert result.camera_model == "Canon EOS R6"
    assert result.shutter_speed == "1/250"
    assert result.iso == 400
    assert result.focal_length == "35mm"


def test_parse_photo_minimal():
    data = {"format": {"tags": {}}}
    result = parse_photo(Path("/tmp/photo.jpg"), data)

    assert isinstance(result, PhotoMetadata)
    assert result.timestamp is None
    assert result.camera_model is None


def test_parse_photo_missing_tags():
    data = {"format": {}}
    result = parse_photo(Path("/tmp/photo.jpg"), data)

    assert isinstance(result, PhotoMetadata)
    assert result.timestamp is None


def test_parse_video_full():
    data = load_fixture("ffprobe_video.json")
    result = parse_video(Path("/tmp/video.mp4"), data)

    assert isinstance(result, VideoMetadata)
    assert result.source_path == Path("/tmp/video.mp4")
    assert result.start_timestamp == datetime(2024, 7, 15, 14, 0, 0, tzinfo=timezone.utc)
    assert result.duration_seconds == 330.5
    assert result.end_timestamp == datetime(2024, 7, 15, 14, 5, 30, 500000, tzinfo=timezone.utc)


def test_parse_video_no_duration():
    data = {
        "format": {
            "tags": {"creation_time": "2024-07-15T14:00:00.000000Z"}
        }
    }
    result = parse_video(Path("/tmp/video.mp4"), data)

    assert result.start_timestamp == datetime(2024, 7, 15, 14, 0, 0, tzinfo=timezone.utc)
    assert result.duration_seconds is None
    assert result.end_timestamp is None


def test_parse_video_empty():
    data = {}
    result = parse_video(Path("/tmp/video.mp4"), data)

    assert isinstance(result, VideoMetadata)
    assert result.start_timestamp is None
    assert result.duration_seconds is None
```

- [ ] **Step 3: Run test to verify it fails**

Run:
```bash
uv run pytest tests/test_parsers.py -v
```

Expected: `ModuleNotFoundError: No module named 'photowalk.parsers'`

- [ ] **Step 4: Write minimal implementation**

Write `src/photowalk/parsers.py`:
```python
"""Parse ffprobe JSON output into typed metadata models."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from photowalk.models import PhotoMetadata, VideoMetadata


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp string into a datetime."""
    if not value:
        return None
    # Handle trailing 'Z' by replacing with +00:00
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _get_tag(data: dict, *keys: str) -> Optional[str]:
    """Walk into ffprobe format.tags and return the first matching key."""
    tags = data.get("format", {}).get("tags") or {}
    for key in keys:
        if key in tags:
            return tags[key]
    return None


def parse_photo(path: Path, data: dict) -> PhotoMetadata:
    """Parse ffprobe JSON into PhotoMetadata."""
    tags = data.get("format", {}).get("tags") or {}

    timestamp = _parse_timestamp(_get_tag(data, "creation_time", "date"))

    make = tags.get("Make", "")
    model = tags.get("Model", "")
    camera_model = None
    if make or model:
        camera_model = " ".join(part for part in [make, model] if part).strip() or None

    shutter_speed = _get_tag(data, "ExposureTime", "ShutterSpeedValue")

    iso_raw = _get_tag(data, "ISOSpeedRatings", "ISO")
    iso = None
    if iso_raw:
        try:
            iso = int(iso_raw)
        except ValueError:
            iso = None

    focal_length = _get_tag(data, "FocalLength")

    return PhotoMetadata(
        source_path=path,
        timestamp=timestamp,
        camera_model=camera_model,
        shutter_speed=shutter_speed,
        iso=iso,
        focal_length=focal_length,
    )


def parse_video(path: Path, data: dict) -> VideoMetadata:
    """Parse ffprobe JSON into VideoMetadata."""
    fmt = data.get("format", {})
    tags = fmt.get("tags") or {}

    start_timestamp = _parse_timestamp(tags.get("creation_time"))

    duration = None
    duration_raw = fmt.get("duration")
    if duration_raw is None:
        # Fall back to first stream duration
        streams = data.get("streams", [])
        if streams:
            duration_raw = streams[0].get("duration")
    if duration_raw is not None:
        try:
            duration = float(duration_raw)
        except ValueError:
            duration = None

    end_timestamp = None
    if start_timestamp is not None and duration is not None:
        end_timestamp = start_timestamp.replace(tzinfo=timezone.utc) + __import__("datetime").timedelta(seconds=duration)
        if start_timestamp.tzinfo:
            end_timestamp = start_timestamp + __import__("datetime").timedelta(seconds=duration)

    return VideoMetadata(
        source_path=path,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        duration_seconds=duration,
    )
```

Wait — the timedelta import inside the function is ugly. Let me fix that to use proper imports at the top. Let me rewrite this more cleanly.

Actually, let me write it properly:

```python
"""Parse ffprobe JSON output into typed metadata models."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from photowalk.models import PhotoMetadata, VideoMetadata


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp string into a datetime."""
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _get_tag(data: dict, *keys: str) -> Optional[str]:
    """Walk into ffprobe format.tags and return the first matching key."""
    tags = data.get("format", {}).get("tags") or {}
    for key in keys:
        if key in tags:
            return tags[key]
    return None


def parse_photo(path: Path, data: dict) -> PhotoMetadata:
    """Parse ffprobe JSON into PhotoMetadata."""
    tags = data.get("format", {}).get("tags") or {}

    timestamp = _parse_timestamp(_get_tag(data, "creation_time", "date"))

    make = tags.get("Make", "")
    model = tags.get("Model", "")
    camera_model = None
    if make or model:
        camera_model = " ".join(part for part in [make, model] if part).strip() or None

    shutter_speed = _get_tag(data, "ExposureTime", "ShutterSpeedValue")

    iso_raw = _get_tag(data, "ISOSpeedRatings", "ISO")
    iso = None
    if iso_raw:
        try:
            iso = int(iso_raw)
        except ValueError:
            iso = None

    focal_length = _get_tag(data, "FocalLength")

    return PhotoMetadata(
        source_path=path,
        timestamp=timestamp,
        camera_model=camera_model,
        shutter_speed=shutter_speed,
        iso=iso,
        focal_length=focal_length,
    )


def parse_video(path: Path, data: dict) -> VideoMetadata:
    """Parse ffprobe JSON into VideoMetadata."""
    fmt = data.get("format", {})
    tags = fmt.get("tags") or {}

    start_timestamp = _parse_timestamp(tags.get("creation_time"))

    duration = None
    duration_raw = fmt.get("duration")
    if duration_raw is None:
        streams = data.get("streams", [])
        if streams:
            duration_raw = streams[0].get("duration")
    if duration_raw is not None:
        try:
            duration = float(duration_raw)
        except ValueError:
            duration = None

    end_timestamp = None
    if start_timestamp is not None and duration is not None:
        end_timestamp = start_timestamp + timedelta(seconds=duration)

    return VideoMetadata(
        source_path=path,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        duration_seconds=duration,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run:
```bash
uv run pytest tests/test_parsers.py -v
```

Expected: 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_parsers.py tests/fixtures/ src/photowalk/parsers.py && git commit -m "feat: add ffprobe JSON parsers for photo and video metadata"
```

---

### Task 6: High-Level API

**Files:**
- Create: `src/photowalk/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing test**

Write `tests/test_api.py`:
```python
from pathlib import Path
from unittest.mock import patch, MagicMock

from photowalk.api import extract_metadata
from photowalk.models import PhotoMetadata, VideoMetadata


def test_extract_metadata_photo():
    mock_ffprobe = {
        "format": {
            "tags": {
                "creation_time": "2024-07-15T14:32:10.000000Z",
                "Model": "EOS R6",
            }
        }
    }

    with patch("photowalk.api.run_ffprobe", return_value=mock_ffprobe):
        result = extract_metadata(Path("/tmp/photo.jpg"))

    assert isinstance(result, PhotoMetadata)
    assert result.camera_model == "EOS R6"


def test_extract_metadata_video():
    mock_ffprobe = {
        "format": {
            "duration": "120.0",
            "tags": {"creation_time": "2024-07-15T14:00:00.000000Z"}
        }
    }

    with patch("photowalk.api.run_ffprobe", return_value=mock_ffprobe):
        result = extract_metadata(Path("/tmp/video.mp4"))

    assert isinstance(result, VideoMetadata)
    assert result.duration_seconds == 120.0


def test_extract_metadata_unknown_extension():
    result = extract_metadata(Path("/tmp/file.txt"))
    assert result is None


def test_extract_metadata_ffprobe_failure():
    with patch("photowalk.api.run_ffprobe", return_value=None):
        result = extract_metadata(Path("/tmp/photo.jpg"))

    assert isinstance(result, PhotoMetadata)
    assert result.timestamp is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/test_api.py -v
```

Expected: `ModuleNotFoundError: No module named 'photowalk.api'`

- [ ] **Step 3: Write minimal implementation**

Write `src/photowalk/api.py`:
```python
"""High-level API: given a file path, return the appropriate metadata model."""

from pathlib import Path
from typing import Optional, Union

from photowalk.constants import PHOTO_EXTENSIONS, VIDEO_EXTENSIONS
from photowalk.extractors import run_ffprobe
from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.parsers import parse_photo, parse_video


MetadataResult = Union[PhotoMetadata, VideoMetadata, None]


def extract_metadata(path: Path) -> MetadataResult:
    """Extract metadata from a single file path.

    Returns None for unsupported file types.
    Returns a metadata model with all fields None if ffprobe fails.
    """
    ext = path.suffix.lower()

    if ext in PHOTO_EXTENSIONS:
        data = run_ffprobe(path)
        if data is None:
            return PhotoMetadata(source_path=path)
        return parse_photo(path, data)

    if ext in VIDEO_EXTENSIONS:
        data = run_ffprobe(path)
        if data is None:
            return VideoMetadata(source_path=path)
        return parse_video(path, data)

    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
uv run pytest tests/test_api.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_api.py src/photowalk/api.py && git commit -m "feat: add high-level extract_metadata API"
```

---

### Task 7: CLI

**Files:**
- Create: `src/photowalk/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

Write `tests/test_cli.py`:
```python
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from photowalk.cli import main


def test_info_photo():
    mock_result = {
        "format": {
            "tags": {
                "creation_time": "2024-07-15T14:32:10.000000Z",
                "Model": "EOS R6",
                "ExposureTime": "1/250",
                "ISOSpeedRatings": "400",
                "FocalLength": "35mm",
            }
        }
    }

    runner = CliRunner()
    with patch("photowalk.cli.run_ffprobe", return_value=mock_result):
        result = runner.invoke(main, ["info", "/tmp/photo.jpg"])

    assert result.exit_code == 0
    assert "EOS R6" in result.output
    assert "1/250" in result.output


def test_info_video():
    mock_result = {
        "format": {
            "duration": "120.0",
            "tags": {"creation_time": "2024-07-15T14:00:00.000000Z"}
        }
    }

    runner = CliRunner()
    with patch("photowalk.cli.run_ffprobe", return_value=mock_result):
        result = runner.invoke(main, ["info", "/tmp/video.mp4"])

    assert result.exit_code == 0
    assert "14:00:00" in result.output


def test_info_unsupported():
    runner = CliRunner()
    result = runner.invoke(main, ["info", "/tmp/file.txt"])

    assert result.exit_code == 0
    assert "Unsupported" in result.output or "No metadata" in result.output


def test_batch_json():
    mock_photo = {
        "format": {
            "tags": {
                "creation_time": "2024-07-15T14:32:10.000000Z",
                "Model": "EOS R6",
            }
        }
    }

    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        Path("photo.jpg").touch()
        with patch("photowalk.cli.run_ffprobe", return_value=mock_photo):
            result = runner.invoke(main, ["batch", ".", "--output", "json"])

    assert result.exit_code == 0
    assert '"media_type": "photo"' in result.output
    assert "EOS R6" in result.output


def test_batch_empty():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["batch", "."])

    assert result.exit_code == 0
    assert "No media files found" in result.output or result.output.strip() == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/test_cli.py -v
```

Expected: `ModuleNotFoundError: No module named 'photowalk.cli'`

- [ ] **Step 3: Write minimal implementation**

Write `src/photowalk/cli.py`:
```python
"""Click CLI for photowalk."""

import json
from pathlib import Path

import click

from photowalk.api import extract_metadata
from photowalk.constants import PHOTO_EXTENSIONS, VIDEO_EXTENSIONS
from photowalk.extractors import ffprobe_not_found_error, run_ffprobe
from photowalk.models import PhotoMetadata, VideoMetadata


def _collect_files(paths: list[Path], recursive: bool) -> list[Path]:
    """Collect media files from a list of paths."""
    files = []
    for path in paths:
        if path.is_file():
            if path.suffix.lower() in PHOTO_EXTENSIONS | VIDEO_EXTENSIONS:
                files.append(path)
        elif path.is_dir():
            pattern = "**/*" if recursive else "*"
            for child in path.glob(pattern):
                if child.is_file() and child.suffix.lower() in PHOTO_EXTENSIONS | VIDEO_EXTENSIONS:
                    files.append(child)
    return files


def _format_table(results: list[PhotoMetadata | VideoMetadata]) -> str:
    lines = []
    lines.append(f"{'File':<40} {'Type':<8} {'Timestamp':<25} {'Details'}")
    lines.append("-" * 100)
    for r in results:
        name = str(r.source_path)[:39]
        if isinstance(r, PhotoMetadata):
            ts = r.timestamp.isoformat() if r.timestamp else "N/A"
            details = f"{r.camera_model or 'N/A'} | ISO {r.iso or 'N/A'} | {r.focal_length or 'N/A'}"
            lines.append(f"{name:<40} {'photo':<8} {ts:<25} {details}")
        else:
            start = r.start_timestamp.isoformat() if r.start_timestamp else "N/A"
            end = r.end_timestamp.isoformat() if r.end_timestamp else "N/A"
            dur = f"{r.duration_seconds:.1f}s" if r.duration_seconds else "N/A"
            lines.append(f"{name:<40} {'video':<8} {start:<25} end={end} dur={dur}")
    return "\n".join(lines)


def _format_csv(results: list[PhotoMetadata | VideoMetadata]) -> str:
    lines = ["source_path,media_type,timestamp,camera_model,shutter_speed,iso,focal_length,start_timestamp,end_timestamp,duration_seconds"]
    for r in results:
        d = r.to_dict()
        lines.append(
            f'"{d["source_path"]}",{d["media_type"]},'
            f'"{d.get("timestamp") or ""}","{d.get("camera_model") or ""}",'
            f'"{d.get("shutter_speed") or ""}",{d.get("iso") or ""},'
            f'"{d.get("focal_length") or ""}","{d.get("start_timestamp") or ""}",'
            f'"{d.get("end_timestamp") or ""}",{d.get("duration_seconds") or ""}'
        )
    return "\n".join(lines)


@click.group()
@click.version_option(version="0.1.0")
def main():
    """Extract metadata from photos and videos using ffprobe."""
    pass


@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def info(path: Path):
    """Show metadata for a single file."""
    try:
        result = extract_metadata(path)
    except RuntimeError as e:
        click.echo(click.style(str(e), fg="red"), err=True)
        raise click.Exit(1)

    if result is None:
        click.echo("Unsupported file type.")
        return

    click.echo(json.dumps(result.to_dict(), indent=2))


@main.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Choice(["json", "table", "csv"]), default="table")
@click.option("--recursive", "-r", is_flag=True)
@click.option("--include-photos/--no-include-photos", default=True)
@click.option("--include-videos/--no-include-videos", default=True)
def batch(paths, output, recursive, include_photos, include_videos):
    """Process multiple files or directories."""
    try:
        files = _collect_files(list(paths), recursive)
    except RuntimeError as e:
        click.echo(click.style(str(e), fg="red"), err=True)
        raise click.Exit(1)

    if not include_photos:
        files = [f for f in files if f.suffix.lower() not in PHOTO_EXTENSIONS]
    if not include_videos:
        files = [f for f in files if f.suffix.lower() not in VIDEO_EXTENSIONS]

    if not files:
        click.echo("No media files found.")
        return

    results = []
    for f in files:
        result = extract_metadata(f)
        if result is not None:
            results.append(result)

    if output == "json":
        click.echo(json.dumps([r.to_dict() for r in results], indent=2))
    elif output == "csv":
        click.echo(_format_csv(results))
    else:
        click.echo(_format_table(results))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
uv run pytest tests/test_cli.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli.py src/photowalk/cli.py && git commit -m "feat: add CLI with info and batch commands"
```

---

### Task 8: Package Entry Point & README

**Files:**
- Modify: `pyproject.toml`
- Create: `README.md`

- [ ] **Step 1: Add CLI entry point**

Modify `pyproject.toml` — add this under `[project.scripts]`:
```toml
[project.scripts]
photowalk = "photowalk.cli:main"
```

If `[project.scripts]` doesn't exist, add it. The existing `pyproject.toml` from `uv init --package` should already have a `[project]` section.

- [ ] **Step 2: Verify entry point works**

Run:
```bash
uv run photowalk --help
```

Expected: Shows CLI help with `info` and `batch` commands.

- [ ] **Step 3: Write README**

Write `README.md`:
```markdown
# Photo Walk

Extract timestamps and camera metadata from photos and videos using ffprobe.

## Requirements

- Python 3.10+
- [FFmpeg](https://ffmpeg.org) (provides `ffprobe`)

## Installation

```bash
# Install FFmpeg first
# macOS: brew install ffmpeg
# Ubuntu: sudo apt install ffmpeg

# Clone and install
uv pip install -e .
```

## Usage

### Single file

```bash
photowalk info photo.jpg
photowalk info video.mp4
```

### Batch processing

```bash
# Table output (default)
photowalk batch ~/Photos/2024/ --recursive

# JSON output
photowalk batch ~/Photos/2024/ --output json --recursive

# CSV output
photowalk batch ~/Photos/2024/ --output csv --recursive

# Photos only
photowalk batch ~/Photos/2024/ --no-include-videos
```

## Library Usage

```python
from pathlib import Path
from photowalk.api import extract_metadata

meta = extract_metadata(Path("photo.jpg"))
print(meta.timestamp)
print(meta.camera_model)
```

## Development

```bash
uv run pytest
```
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml README.md && git commit -m "chore: add CLI entry point and README"
```

---

### Task 9: Final Integration & Verification

**Files:**
- Modify: `src/photowalk/__init__.py`

- [ ] **Step 1: Update package init to expose public API**

Write `src/photowalk/__init__.py`:
```python
"""Photo Walk — Media metadata extraction using ffprobe."""

__version__ = "0.1.0"

from photowalk.api import extract_metadata
from photowalk.models import PhotoMetadata, VideoMetadata

__all__ = ["extract_metadata", "PhotoMetadata", "VideoMetadata"]
```

- [ ] **Step 2: Run full test suite**

Run:
```bash
uv run pytest -v --tb=short
```

Expected: All tests PASS (20+ tests)

- [ ] **Step 3: Verify CLI end-to-end**

Run:
```bash
uv run photowalk --help
uv run photowalk info --help
uv run photowalk batch --help
```

Expected: All three commands show help text.

- [ ] **Step 4: Run type check (if mypy available)**

Run:
```bash
uv add --dev mypy && uv run mypy src/photowalk
```

Optional — skip if mypy is not installed. If added, fix any type errors.

- [ ] **Step 5: Final commit**

```bash
git add -A && git commit -m "feat: complete photo-walk metadata extraction tool"
```

---

## Self-Review

### Spec Coverage Check

| Spec Section | Plan Task |
|--------------|-----------|
| Architecture (models, extractors, parsers, cli) | Tasks 2-7 |
| Data Models (PhotoMetadata, VideoMetadata) | Task 3 |
| ffprobe Strategy (invocation, fields, degradation) | Tasks 4-5 |
| Media Type Detection (extensions) | Task 2, 6 |
| CLI Design (info, batch, flags, output formats) | Task 7 |
| Error Handling (ffprobe missing, failure, unknown ext) | Tasks 4, 6, 7 |
| Dependencies (click, pytest) | Task 1 |
| Testing Strategy (unit, mock, fixtures) | All tasks |

**Gap:** None identified. All spec requirements map to plan tasks.

### Placeholder Scan

- No "TBD", "TODO", or "implement later" found.
- No vague "add error handling" — specific error cases handled in extractors and CLI.
- All test code is complete with assertions.
- All implementation code is complete.

### Type Consistency Check

- `PhotoMetadata` and `VideoMetadata` fields match spec exactly.
- `extract_metadata` returns `MetadataResult` (union type) consistently.
- `run_ffprobe` returns `Optional[dict]` consistently.
- `parse_photo` / `parse_video` signatures use `Path` and `dict` consistently.
- CLI commands use `click.Path(path_type=Path)` consistently.

No type inconsistencies found.
