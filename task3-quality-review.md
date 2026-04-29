# Task 3 Quality Review

**Commits reviewed:** `7670f2f` → `16103ba`  
**Files changed:** `src/photowalk/stitcher.py`, `tests/test_stitcher.py`

---

## Strengths

### Correct cancellation architecture
`cancel_event` propagates top-down through a clean call chain:

```
stitch() → _split_video_segment() / generate_image_clip() → _run_ffmpeg_cmd()
```

Each layer guards with an early `cancel_event.is_set()` check before doing any work. `_run_ffmpeg_cmd` (in `ffmpeg_config.py`) additionally handles mid-execution cancellation via `proc.terminate()` / `proc.kill()`. The dual-layer design is correct: the pre-check avoids spawning a process at all when already cancelled; the poll loop handles the in-flight case.

### Clean subprocess consolidation
`subprocess.run` is fully removed from `stitcher.py` (no `subprocess` import remains). Error handling (`FileNotFoundError → RuntimeError`) is now consolidated in `_run_ffmpeg_cmd`, which is the right place since it owns the subprocess lifecycle.

### Backward-compatible signatures
`cancel_event=None` is the default in all three call sites (`stitch`, `run_concat`, `_split_video_segment`), so all existing callers are unaffected.

### Tests verify behaviour, not just mocks
- `test_stitch_video_segment` still inspects `call_args_list[0][0][0]` to assert the split command contains `libx264`, `scale=`, and `pad=` — confirming command construction is correct even after the mock target changed.
- `test_split_video_segment_uses_custom_encode_config` and `test_run_concat_uses_custom_encode_config` inspect the cmd list for `ultrafast` / crf `28` — verifying encode config propagation.
- The four new cancellation tests are direct and unambiguous: each asserts `result is False` and `mock.assert_not_called()` where applicable.

### All tests pass
220 tests pass, 0 failures.

---

## Issues

### Minor — `test_stitch_cancelled_during_clip` does not exercise the inter-entry loop guard

The loop in `stitch()` has a guard at the top of each iteration:

```python
for entry in timeline_map.all_entries:
    if cancel_event is not None and cancel_event.is_set():   # ← this path
        return False
    ...
```

`test_stitch_cancelled_during_clip` uses a single-entry timeline, so the clip returns `False` and `stitch` exits via `if not ok: return False` — not via the loop guard. The loop guard (cancellation *between* two entries) is not tested.

This is low priority because:
- The single-entry test still confirms stitch propagates a failed clip correctly.
- The guard itself is a one-liner with no logic to get wrong.

A two-entry test where the first clip sets the event and the second should never run would cover it completely.

### Observation — `_run_ffmpeg_cmd` is a private-prefixed symbol shared across modules

`stitcher.py` and `image_clip.py` both import `_run_ffmpeg_cmd` (underscore prefix). This is consistent usage within the same package and not a problem in practice. It does mean callers in tests patch `photowalk.stitcher._run_ffmpeg_cmd` rather than `photowalk.ffmpeg_config._run_ffmpeg_cmd`, which is correct (patch where it's used, not where it's defined).

---

## Assessment

**Approved.**

The implementation is correct, minimal, and well-tested. The cancellation path is properly layered. The refactor from `subprocess.run` to `_run_ffmpeg_cmd` removes duplicated error-handling code. The only gap is a missing two-entry test for the inter-entry loop guard, which is minor and does not affect correctness.
