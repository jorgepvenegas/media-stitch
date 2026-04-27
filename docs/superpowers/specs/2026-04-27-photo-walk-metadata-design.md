# Photo Walk — Media Metadata Extraction Tool

**Date:** 2026-04-27  
**Status:** Approved

## Overview

A Python library and CLI tool that extracts timestamp and camera metadata from video and photo files by shelling out to `ffprobe` (part of FFmpeg). No heavy Python media dependencies — ffprobe does all the heavy lifting.

## Goals

- Extract **timestamps** from photos and videos (when was the photo taken, when did the video start/end)
- Extract **camera EXIF** from photos: camera model, shutter speed, ISO, focal length
- Provide both a **Python library** (`import photowalk`) and a **CLI** (`photowalk`)
- Handle missing/corrupt metadata gracefully (never crash)
- Support batch processing of directories

## Non-Goals

- Writing or modifying metadata
- Content-sniffing/magic number detection (v1 uses file extensions)
- Real-time monitoring or watch mode
- Thumbnail/preview generation

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│  CLI / API  │────▶│  extractors  │────▶│   parsers   │────▶│   models     │
│   (click)   │     │  (ffprobe)   │     │  (JSON→obj) │     │ (dataclasses)│
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
```

### Components

| Module | Responsibility |
|--------|---------------|
| `models.py` | Typed dataclasses: `PhotoMetadata`, `VideoMetadata`. Pure data, no logic. |
| `extractors.py` | Runs `ffprobe` subprocess, returns raw JSON dict. No parsing logic. |
| `parsers.py` | Transforms ffprobe JSON into typed model instances. Handles missing fields. |
| `cli.py` | Click-based CLI. Accepts files/directories, routes to extractors, formats output. |

### Design Principles

- **Shell out, don't link**: ffprobe is the only external tool. No Pillow, no exiftool bindings.
- **Fail soft**: A file with missing metadata produces a model full of `None`s, not an exception.
- **Single source of truth**: One ffprobe invocation per file. Parse the same JSON for all fields.

## Data Models

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class PhotoMetadata:
    source_path: Path
    media_type: str = "photo"
    timestamp: Optional[datetime] = None          # when photo was taken
    camera_model: Optional[str] = None
    shutter_speed: Optional[str] = None           # e.g. "1/250"
    iso: Optional[int] = None
    focal_length: Optional[str] = None            # e.g. "35mm"


@dataclass(frozen=True)
class VideoMetadata:
    source_path: Path
    media_type: str = "video"
    start_timestamp: Optional[datetime] = None    # when recording began
    end_timestamp: Optional[datetime] = None      # start + duration
    duration_seconds: Optional[float] = None
```

Both models expose a `to_dict()` method for JSON serialization.

## ffprobe Strategy

### Invocation
```bash
ffprobe -v quiet -print_format json -show_format -show_streams <file>
```

### Photo Fields (from `format.tags`)
| Our Field | ffprobe Source | Notes |
|-----------|---------------|-------|
| `timestamp` | `creation_time`, `date` | Prefer `creation_time`. Parse ISO-8601. Naive if no tz. |
| `camera_model` | `model`, `Make` + `Model` | Concatenate Make/Model if separate. |
| `shutter_speed` | `ShutterSpeedValue`, `ExposureTime` | Prefer `ExposureTime` (human-readable). |
| `iso` | `ISOSpeedRatings`, `ISO` | Parse as int. |
| `focal_length` | `FocalLength` | Keep as string (includes "mm"). |

### Video Fields (from `format.tags` and `streams[0]`)
| Our Field | ffprobe Source | Notes |
|-----------|---------------|-------|
| `start_timestamp` | `format.tags.creation_time` | Parse ISO-8601. |
| `duration_seconds` | `format.duration` or `streams[0].duration` | Prefer `format.duration`. Float. |
| `end_timestamp` | computed | `start_timestamp + duration` if both present. |

### Graceful Degradation
- Any tag missing → corresponding field is `None`
- `creation_time` present but unparseable → `None` (log warning)
- `duration` missing → `duration_seconds: None`, `end_timestamp: None`

## Media Type Detection

Simple extension-based mapping:

```python
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".heic", ".heif", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv", ".flv"}
```

Unknown extensions are skipped with a warning. No content sniffing in v1.

## CLI Design

### Commands

```bash
# Single file
photowalk info path/to/photo.jpg
photowalk info path/to/video.mp4

# Batch directory
photowalk batch ~/Photos/2024/ --output json
photowalk batch ~/Photos/2024/ --output table --recursive
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--output, -o` | `table` | `json`, `table`, `csv` |
| `--recursive, -r` | `False` | Scan directories recursively |
| `--include-photos` | `True` | Include photo files in batch |
| `--include-videos` | `True` | Include video files in batch |

### Output Formats

**JSON:** Array of objects, one per file, with a `type` field (`"photo"` or `"video"`). Machine-readable.

```json
[
  {
    "source_path": "/Users/jorge/Photos/2024/img_001.jpg",
    "media_type": "photo",
    "timestamp": "2024-07-15T14:32:10",
    "camera_model": "Canon EOS R6",
    "shutter_speed": "1/250",
    "iso": 400,
    "focal_length": "35mm"
  }
]
```

**Table:** Human-readable aligned columns. Files with errors show `"N/A"`.

**CSV:** One header row, one row per file. All fields flattened.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| ffprobe not in PATH | Exit with clear error: `"ffprobe not found. Install FFmpeg: https://ffmpeg.org"` |
| ffprobe returns non-zero | Capture stderr, log warning, return model with all fields `None` |
| File not found | Log warning, skip |
| Empty or unparseable tags | Field = `None`, continue processing other fields |
| Mixed batch with errors | Continue processing remaining files; exit code 0 if any succeed |

## Project Layout

```
photo-walk/
├── pyproject.toml
├── README.md
├── uv.lock
├── src/
│   └── photowalk/
│       ├── __init__.py
│       ├── models.py
│       ├── extractors.py
│       ├── parsers.py
│       ├── cli.py
│       └── constants.py          # extension lists
├── tests/
│   ├── test_extractors.py        # mock subprocess
│   ├── test_parsers.py           # fixture JSON → model
│   ├── test_cli.py               # invoke Click runner
│   └── fixtures/
│       └── ffprobe_photo.json
│       └── ffprobe_video.json
└── docs/superpowers/specs/
    └── 2026-04-27-photo-walk-metadata-design.md
```

## Dependencies

```toml
[project]
dependencies = ["click>=8.0"]

[project.scripts]
photowalk = "photowalk.cli:main"

[project.optional-dependencies]
dev = ["pytest", "pytest-cov"]
```

Runtime: Python 3.10+, click, ffprobe (user-installed).  
Dev: pytest, pytest-cov.

## Testing Strategy

1. **Unit — parsers:** Feed known ffprobe JSON fixtures (checked into `tests/fixtures/`), assert correct `PhotoMetadata` / `VideoMetadata` output. Test missing-field cases.
2. **Unit — extractors:** Mock `subprocess.run` to verify correct ffprobe command-line construction. No ffprobe binary required.
3. **Unit — CLI:** Use Click's `CliRunner` to test command parsing and output formatting.
4. **Integration (optional):** If real sample media files are present, verify end-to-end. Marked with `@pytest.mark.integration` and skipped by default.

## Open Questions / Future Work

- **Timezone handling:** v1 parses timestamps as naive or UTC. Future: infer timezone from GPS if present.
- **Content sniffing:** v1 uses extensions. Future: inspect file headers for robustness.
- **Parallel processing:** Batch mode is sequential. Future: `asyncio` or `concurrent.futures` for large directories.
- **Additional fields:** GPS coordinates, aperture, lens model — add on demand.
