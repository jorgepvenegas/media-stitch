# Photo Walk

Extract and synchronize timestamps and camera metadata from photos and videos. Stitch photos and videos into chronological output videos.

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

### Fix trimmed video timestamps

When a video is trimmed in an external editor, the trimmed file loses its original creation time. This command auto-detects the trim offset by comparing audio waveforms via cross-correlation, then writes the corrected timestamp.

```bash
# Preview the detected offset and computed timestamp
photowalk fix-trim original.mp4 trimmed.mp4 --dry-run

# Update the trimmed file in place
photowalk fix-trim original.mp4 trimmed.mp4

# Write to a new file instead
photowalk fix-trim original.mp4 trimmed.mp4 -o fixed.mp4
```

### Stitch photos and videos into a timeline video

Compose a single chronological video from a directory of photos and videos. Images are displayed as white-background clips inserted at their capture timestamp within or between videos.

```bash
# Preview the timeline without generating output
photowalk stitch ~/Photos/2024/ --output final.mp4 --dry-run

# Generate the stitched video (resolution auto-detected from first video)
photowalk stitch ~/Photos/2024/ --output final.mp4

# Force a specific output resolution
photowalk stitch ~/Photos/2024/ --output final.mp4 --format 1920x1080

# Change image display duration (default is 3.5 seconds)
photowalk stitch ~/Photos/2024/ --output final.mp4 --image-duration 5.0

# Render a low-quality draft for faster preview
photowalk stitch ~/Photos/2024/ --output final.mp4 --draft

# Keep temporary clips for debugging
photowalk stitch ~/Photos/2024/ --output final.mp4 --keep-temp
```

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
| `src/photowalk/cli.py` | Click CLI (`info`, `batch`, `sync`, `fix-trim`, `stitch` commands) |
| `src/photowalk/models.py` | `PhotoMetadata` and `VideoMetadata` dataclasses |
| `src/photowalk/photo_extractors.py` | Pillow-based photo EXIF extraction |
| `src/photowalk/extractors.py` | ffprobe subprocess wrapper for videos |
| `src/photowalk/parsers.py` | Parse raw EXIF/ffprobe output into typed models |
| `src/photowalk/offset.py` | Parse `--offset` and `--reference` into `timedelta` |
| `src/photowalk/offset_detector.py` | Audio cross-correlation for trim offset detection |
| `src/photowalk/timeline.py` | Build sorted timeline map from photos and videos |
| `src/photowalk/image_clip.py` | Generate white-background video clips from photos |
| `src/photowalk/stitcher.py` | Split videos and assemble final output via ffmpeg concat |
| `src/photowalk/writers.py` | Write timestamps back via piexif (photos) / ffmpeg (videos) |
