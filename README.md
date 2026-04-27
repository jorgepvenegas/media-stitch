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
