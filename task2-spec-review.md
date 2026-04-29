# Task 2 Spec Review — Wire `cancel_event` into `image_clip.py`

**Verdict: ✅ Spec compliant**

---

## Checklist

### `src/photowalk/image_clip.py`

| Requirement | Status | Detail |
|---|---|---|
| `import threading` added | ✅ | Line 3 |
| `_run_ffmpeg_cmd` added to ffmpeg_config import | ✅ | Lines 8–13 |
| `cancel_event: threading.Event \| None = None` param added | ✅ | Signature of `generate_image_clip` |
| Early return `if cancel_event is not None and cancel_event.is_set(): return False` | ✅ | First statement in function body, before `Image.open` |
| `subprocess.run` replaced with `return _run_ffmpeg_cmd(cmd, cancel_event=cancel_event)` | ✅ | Last line of function |

### `tests/test_image_clip.py`

| Requirement | Status | Detail |
|---|---|---|
| `test_generate_image_clip_cancelled_before_run` exists | ✅ | Sets `cancel_event`, calls `cancel_event.set()`, asserts `result is False` and `mock_run.assert_not_called()` |
| `test_generate_image_clip_passes_cancel_event` exists | ✅ | Calls with unset `cancel_event`, asserts `mock_run.assert_called_once()` and `kwargs["cancel_event"] is cancel_event` |
| Pre-existing tests updated from `subprocess.run` to `_run_ffmpeg_cmd` | ✅ | All 4 pre-existing `generate_image_clip` tests patch `photowalk.image_clip._run_ffmpeg_cmd` |

### Test run

All 13 tests in `tests/test_image_clip.py` pass (confirmed with `uv run pytest tests/test_image_clip.py -v`).

---

## Notes

- The early-return guard fires **before** `Image.open`, which is the correct place — a cancelled job should do zero work. The test correctly accounts for this (Image.open mock is set up but will not be called).
- `cancel_event` is threaded all the way through to `_run_ffmpeg_cmd(cmd, cancel_event=cancel_event)`, so mid-execution cancellation is also delegated to the lower-level helper — consistent with how the rest of the codebase uses `_run_ffmpeg_cmd`.
- No unintended additions or removals detected.
