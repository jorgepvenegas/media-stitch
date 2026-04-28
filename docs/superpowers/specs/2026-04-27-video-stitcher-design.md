# Video Stitcher Design — 2026-04-27

## Overview

A new `photowalk stitch` command that composes a single output video from a directory of photos and videos, sorted by timestamp. Images are displayed as white-background clips inserted into the timeline at their capture time. Videos are split at image insertion points and stitched back together.

## Goals

- Produce a single chronological video from mixed photos and videos
- Images appear at their filmed-at timestamp within or between videos
- Each image displays for 3.5 seconds on a white background (simple border, centered, aspect-ratio-preserving)
- Output resolution derived from first video or user-specified via `--format`
- Debuggable via optional JSON timeline map and `--keep-temp`

## Architecture

Three-phase pipeline, orchestrated by a new `stitch` CLI command.

### Phase 1: Discover & Map

Scan input directory (recursively), extract metadata from all photos and videos using existing `api.py` extractors. Build a sorted timeline.

For each video, identify images whose timestamp falls within `[video_start, video_end]`. These are "inline" images. Images outside all video ranges are "standalone" and appear between videos at their capture time.

Output: a `TimelineMap` containing `VideoTimeline` objects and a global sorted list of all entries.

### Phase 2: Generate Clips

For every image (inline + standalone):
1. Compute scaled dimensions to fit within output frame while preserving aspect ratio
2. Generate a 3.5-second video with white background and centered scaled image using ffmpeg

Output: each `TimelineEntry` of kind `image` gets its `clip_path` populated.

### Phase 3: Assemble

For each video with inline images:
- Split the original video at image timestamps using ffmpeg `trim`
- Produce ordered list: `[video_seg_1, image_clip_1, video_seg_2, image_clip_2, ...]`

Build a master concat list from all `VideoTimeline.segments` and standalone image entries, sorted globally by start time.

Run ffmpeg concat demuxer to produce the final output video.

## Data Model

```python
@dataclass
class TimelineEntry:
    start_time: datetime
    duration_seconds: float
    kind: Literal["video", "image", "video_segment"]
    source_path: Path
    clip_path: Optional[Path] = None
    original_video: Optional[Path] = None
    trim_start: Optional[float] = None
    trim_end: Optional[float] = None

@dataclass
class VideoTimeline:
    video_path: Path
    video_start: datetime
    video_end: datetime
    segments: List[TimelineEntry]
```

## CLI Interface

```bash
photowalk stitch <input_dir> --output <path> [--format <WxH>] [--image-duration <seconds>] [--keep-temp] [--dry-run]
```

| Flag | Description | Default |
|------|-------------|---------|
| `--output`, `-o` | Output file path (required) | — |
| `--format` | Target resolution, e.g. `1920x1080` | First video's resolution |
| `--image-duration` | Seconds each image is shown | 3.5 |
| `--keep-temp` | Preserve generated clips/segments | False |
| `--dry-run` | Build timeline, print plan, no output | False |

## Modules

| Module | Responsibility |
|--------|---------------|
| `timeline.py` | Scan directory, extract timestamps, build `TimelineMap`, associate images with videos |
| `image_clip.py` | Generate 3.5s white-background clips from photos using ffmpeg |
| `stitcher.py` | Split videos, build concat list, run final ffmpeg concat |
| `cli.py` | Add `stitch` command, wire modules together |

## Error Handling

- Missing ffmpeg → clear error message before any work begins
- No videos or images found → warning and exit with message
- Image without extractable timestamp → skip with warning, continue
- Video without extractable timestamps → skip with warning, continue
- ffmpeg failure during clip generation → stop, clean up temp files (unless `--keep-temp`)
- Resolution mismatch between videos and no `--format` → use first video, scale others

## Testing Strategy

- Mock `subprocess.run` for all ffmpeg calls
- Use `CliRunner` for CLI tests
- Test timeline building with synthetic metadata (no real media needed)
- Test image scaling math with known input/output dimensions
- Test concat list generation against expected file ordering

## Open Questions / Decisions

1. **Audio:** Videos retain original audio. Image clips are silent. ffmpeg concat demuxer handles this naturally.
2. **Color space:** ffmpeg default color space for generated clips (white = `#FFFFFF`).
3. **Temp directory:** Use `tempfile.TemporaryDirectory`, cleaned on success unless `--keep-temp`.
4. **Standalone images before first video:** Treated as image clips at their timestamp, appearing before the first video segment.

## Implementation Order

1. `timeline.py` + tests
2. `image_clip.py` + tests
3. `stitcher.py` + tests
4. CLI integration in `cli.py` + `test_cli_stitch.py`
5. End-to-end test with mock ffmpeg
