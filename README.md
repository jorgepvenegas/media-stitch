# Photo Walk

Extract and synchronize timestamps and camera metadata from photos and videos.

## Requirements

- Python 3.10+
- [FFmpeg](https://ffmpeg.org) (provides `ffprobe` for video metadata)
- `uv` for Python package management

## Installation

```bash
# Install FFmpeg first
# macOS: brew install ffmpeg
# Ubuntu: sudo apt install ffmpeg

# Clone and install
uv pip install -e .
```

## Usage

### Single file info

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

### Sync timestamps

Adjust timestamps by an offset. Supports both duration strings and reference timestamp pairs.

```bash
# Preview changes with dry-run (recommended first step)
photowalk sync ~/Photos/2024/ --offset "-8h23m5s" --recursive --dry-run

# Apply offset with confirmation prompt
photowalk sync ~/Photos/2024/ --offset "-8h23m5s" --recursive

# Use a reference timestamp pair (computes delta automatically)
photowalk sync ~/Photos/2024/ --reference "2026-04-27T23:28:01+00:00=2026-04-27T07:05:00" --recursive

# Skip confirmation prompt
photowalk sync ~/Photos/2024/ --offset "+2h" --recursive --yes
```

#### Offset formats

- **Duration string:** `[-][Nh][Nm][Ns]` — e.g. `-8h23m5s`, `+2h`, `-30m`
- **Reference pair:** `wrong=correct` — e.g. `2026-04-27T23:28:01+00:00=2026-04-27T07:05:00`

## Library Usage

```python
from pathlib import Path
from photowalk.api import extract_metadata

meta = extract_metadata(Path("photo.jpg"))
print(meta.timestamp)        # datetime when photo was taken
print(meta.camera_model)     # e.g. "Canon EOS R6"
print(meta.shutter_speed)    # e.g. "1/250"
print(meta.iso)              # e.g. 400
print(meta.focal_length)     # e.g. "35mm"
```

## Development

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov
```

## Architecture

| Module | Purpose |
|--------|---------|
| `src/photowalk/api.py` | High-level `extract_metadata()` API |
| `src/photowalk/cli.py` | Click CLI (`info`, `batch`, `sync` commands) |
| `src/photowalk/models.py` | `PhotoMetadata` and `VideoMetadata` dataclasses |
| `src/photowalk/photo_extractors.py` | Pillow-based photo EXIF extraction |
| `src/photowalk/extractors.py` | ffprobe subprocess wrapper for videos |
| `src/photowalk/parsers.py` | Parse raw EXIF/ffprobe output into typed models |
| `src/photowalk/offset.py` | Parse `--offset` and `--reference` into `timedelta` |
| `src/photowalk/writers.py` | Write timestamps back via piexif (photos) / ffmpeg (videos) |
