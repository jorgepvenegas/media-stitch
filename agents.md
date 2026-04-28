# Photo Walk — Agent Context

## Project Overview

A Python CLI tool and library for extracting and synchronizing timestamps and camera metadata from photos and videos.

- **Photos:** EXIF extraction via Pillow, timestamp writing via piexif
- **Videos:** Metadata extraction and writing via ffmpeg/ffprobe
- **CLI:** Click-based with `info`, `batch`, `sync`, and `fix-trim` commands

## Tech Stack

- Python 3.10+
- `uv` for package management
- `click` for CLI
- `Pillow` for photo EXIF reading
- `piexif` for photo EXIF writing
- `pytest` for testing

## Project Structure

```
src/photowalk/
├── __init__.py          # Public API exports
├── api.py               # High-level extract_metadata(path) → PhotoMetadata|VideoMetadata
├── cli.py               # Click CLI commands: info, batch, sync
├── models.py            # PhotoMetadata, VideoMetadata dataclasses with to_dict()
├── constants.py         # PHOTO_EXTENSIONS, VIDEO_EXTENSIONS sets
├── photo_extractors.py  # Pillow-based EXIF reading
├── extractors.py        # ffprobe subprocess wrapper
├── parsers.py           # Parse raw EXIF/ffprobe JSON into typed models
├── offset.py            # Parse --offset and --reference into timedelta
├── offset_detector.py   # Audio cross-correlation for trim offset detection
└── writers.py           # Write timestamps: piexif (photos), ffmpeg (videos)

tests/
├── test_api.py
├── test_cli.py
├── test_cli_fix_trim.py
├── test_cli_sync.py
├── test_models.py
├── test_constants.py
├── test_photo_extractors.py
├── test_extractors.py
├── test_parsers.py
├── test_offset.py
├── test_offset_detector.py
├── test_writers.py
└── fixtures/            # Sample ffprobe JSON for parser tests
```

## Key Patterns

### Adding a new CLI command

1. Add the command function decorated with `@main.command()` in `cli.py`
2. Use `click.argument()` and `click.option()` for args/flags
3. Use `click.Path(exists=True, path_type=Path)` for file paths
4. Add tests in `tests/test_cli*.py` using Click's `CliRunner`
5. Mock subprocess/IO operations — don't shell out in tests

### Working with media files

- **Read:** Use `extract_metadata(path)` from `api.py`
- **Write photos:** Use `write_photo_timestamp(path, datetime)` from `writers.py`
- **Write videos:** Use `write_video_timestamp(path, datetime)` from `writers.py`
- **Detect trim offset:** Use `detect_trim_offset(original, trimmed)` from `offset_detector.py`

### Error handling

- Missing/ffprobe failures → return model with `None` fields (never crash)
- Writing failures → return `False`, log warning, continue processing batch
- Invalid CLI args → `click.echo(click.style(..., fg="red"), err=True)` + `raise click.Exit(1)`

### Testing

- Mock `subprocess.run` for ffprobe/ffmpeg tests
- Mock `photowalk.api.extract_photo_exif` for CLI tests that touch photos
- Use `CliRunner().isolated_filesystem()` for file-based CLI tests
- Use Click's `input=` parameter to simulate user prompts

## Common Commands

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_offset.py -v

# Install package in dev mode
uv pip install -e .

# Add dependency
uv add <package>

# Add dev dependency
uv add --dev <package>

# Run CLI
uv run photowalk info photo.jpg
uv run photowalk batch ~/Photos/ --recursive
uv run photowalk sync ~/Photos/ --offset "-2h" --dry-run
uv run photowalk fix-trim original.mp4 trimmed.mp4 --dry-run
```

## Design Decisions

- **Photos use Pillow, not ffprobe:** Pillow gives better EXIF coverage for camera settings (shutter speed, ISO, focal length) that ffprobe often misses.
- **Extension-based type detection:** Simple and fast. Content sniffing could be added later if needed.
- **piexif for photo writing:** Pure Python, no external binary needed. Does not support all formats (HEIC is limited).
- **ffmpeg temp file + atomic swap for videos:** Preserves original until write succeeds.
