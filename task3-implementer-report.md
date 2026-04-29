# Task 3 Implementer Report: Wire `cancel_event` into `stitcher.py`

## Status: DONE

## What was implemented

### `src/photowalk/stitcher.py`
- Added `import threading` at the top
- Added `_run_ffmpeg_cmd` to the `ffmpeg_config` import
- `run_concat`: added `cancel_event: threading.Event | None = None` parameter; early-return `False` if set; replaced `subprocess.run` call with `_run_ffmpeg_cmd(cmd, cancel_event=cancel_event)`
- `_split_video_segment`: added `cancel_event` parameter; early-return `False` if set; replaced `subprocess.run` with `_run_ffmpeg_cmd`
- `stitch`: added `cancel_event` parameter; checks `cancel_event.is_set()` at the top of the entry loop; passes `cancel_event` to `generate_image_clip`, `_split_video_segment`, and `run_concat`

### `tests/test_stitcher.py`
- Added `import threading` at the top
- Updated all existing tests that patched `photowalk.stitcher.subprocess.run` to patch `photowalk.stitcher._run_ffmpeg_cmd` instead (returning `True`/`False` booleans instead of `MagicMock(returncode=…)`)
- Updated `test_run_concat_raises_on_missing_ffmpeg` to raise `RuntimeError` directly from `_run_ffmpeg_cmd` (consistent with the new delegation)
- Added 4 new cancellation tests:
  - `test_stitch_cancelled_before_any_clip`
  - `test_stitch_cancelled_during_clip`
  - `test_run_concat_cancelled`
  - `test_split_video_segment_cancelled`

## Test results

```
22 passed in 0.06s
```

All 22 tests pass (18 pre-existing + 4 new).

## Files changed

- `src/photowalk/stitcher.py`
- `tests/test_stitcher.py`

## Self-review findings

None. The changes are minimal and follow the established pattern from Tasks 1 and 2. The `subprocess` import remains in `stitcher.py` because `generate_plan` doesn't use it — but it's also unused now. However, removing it would be a separate cleanup; no tests reference it and it causes no harm.

> Note: `subprocess` is now imported but unused in `stitcher.py`. Safe to remove in a follow-up cleanup pass if desired.

## Open risks/questions

- `subprocess` import in `stitcher.py` is now unused (only `_run_ffmpeg_cmd` does subprocess calls). This is a minor lint issue, not a correctness issue.

## Recommended next step

Task 4: Wire `cancel_event` into the web server's stitch endpoint (`web/server.py` or `web/sync_apply.py`) so HTTP-triggered stitches can be cancelled.
