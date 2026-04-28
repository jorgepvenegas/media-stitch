# Design: `--draft` Flag for `photowalk stitch`

## Goal
Let users generate a low-quality draft stitched video quickly, without changing the timing or duration of any segment.

## Changes

### 1. CLI (`src/photowalk/cli.py`)
- Add `--draft` boolean flag to the `stitch` command.
- Pass the flag through to `stitch()`.

### 2. Stitcher (`src/photowalk/stitcher.py`)
- `stitch()` gains a `draft: bool = False` parameter.
- When `draft=True`:
  - **Resolution:** scale the requested resolution proportionally so the largest dimension fits within 1280×720. Compute `scale = min(1280 / requested_w, 720 / requested_h, 1.0)`. Then `draft_w = int(requested_w * scale)`, `draft_h = int(requested_h * scale)`. This preserves aspect ratio and never upscales.
  - **Video encoding:** pass `preset="ultrafast"`, `crf=28` to `_split_video_segment()` and `run_concat()`.
  - **Audio encoding:** unchanged (AAC 128k).
- `_split_video_segment()` gains `preset` and `crf` parameters with defaults matching current behavior (`"fast"`, `23`).
- `run_concat()` gains `preset` and `crf` parameters with same defaults.

### 3. Image Clip (`src/photowalk/image_clip.py`)
- `generate_image_clip()` gains `preset` and `crf` parameters with defaults `"fast"` and `23`.
- When `draft=True` from the caller, it receives `preset="ultrafast"`, `crf=28`.
- Resolution is already passed in, so the reduced draft resolution from `stitch()` naturally applies.

## Timing Preservation
- Image clip duration is still driven by `image_duration`.
- Video segment trims (`-ss`, `-t`) are unchanged.
- Concat list order is unchanged.
- Only encoder speed/quality settings and resolution change.

## Testing
- Add `test_stitch_draft_mode` in `tests/test_cli_stitch.py`:
  - Invoke with `--draft`.
  - Assert `stitch()` is called with `draft=True`.
- Add `test_stitch_draft_resolution_cap` to verify that a 1920×1080 request becomes 1280×720 in draft mode.
- Add unit tests in `tests/test_stitcher.py` for `_compute_draft_resolution` helper.

## Backwards Compatibility
- Default behavior is unchanged (`draft=False`).
