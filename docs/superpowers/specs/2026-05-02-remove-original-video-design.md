# Remove `original_video` Dead Code — Spec

## Status
Approved

## Overview

Remove the `original_video` field from the codebase. It was always set to the same value as `source_path` in `TimelineEntry`, making it redundant. All UI references to it showed empty/dead sections.

## Changes

### `src/photowalk/timeline.py`
- Delete `original_video: Optional[Path] = None` from `TimelineEntry` dataclass
- Delete `original_video=video_path` assignments in `_make_video_segments()`

### `src/photowalk/session.py`
- Remove `original_video` key from `get_timeline()` serialization

### `src/photowalk/use_cases/sync.py`
- Remove `original_video` key from `_serialize_timeline_entry()`

### `src/photowalk/stitcher.py`
- Remove `original_video` from `to_dict()` output on `VideoSegmentOutput`

### `src/photowalk/web/assets/app.js`
- In `renderDetails()`, remove the `<div class="sub-header source">Source video</div>` block and the `isSegmentClick` / `source === 'timeline'` conditional guarding it

### Tests
- `tests/test_timeline.py` — remove `original_video` from fixtures and assertions
- `tests/test_stitcher.py` — remove `original_video` from fixtures and assertions
- `tests/test_cli_stitch.py` — remove `original_video` from fixtures
- `tests/test_web_server.py` — remove `original_video` from fixtures
