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

### Sync timestamps

```bash
# Preview changes with dry-run
photowalk sync ~/Photos/2024/ --offset "-8h23m5s" --recursive --dry-run

# Apply offset with confirmation
photowalk sync ~/Photos/2024/ --offset "-8h23m5s" --recursive

# Use a reference timestamp pair
photowalk sync ~/Photos/2024/ --reference "2026-04-27T23:28:01+00:00=2026-04-27T07:05:00" --recursive

# Skip confirmation prompt
photowalk sync ~/Photos/2024/ --offset "+2h" --recursive --yes
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
