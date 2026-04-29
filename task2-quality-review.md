# Task 2 Quality Review

**Scope:** Wire `cancel_event: threading.Event | None` through `generate_image_clip()` in `image_clip.py`, replacing `subprocess.run` with `_run_ffmpeg_cmd`.

---

## Strengths

- **Clean delegation.** `_run_ffmpeg_cmd` in `ffmpeg_config.py` is the single place that owns process lifecycle, cancellation polling (`proc.wait(timeout=0.5)` loop), termination, and kill-on-timeout. `generate_image_clip` correctly delegates without re-implementing any of that.
- **Correct early-exit guard.** The `cancel_event.is_set()` check before `Image.open` prevents unnecessary disk I/O when cancellation is already requested at the call site.
- **Cancellation passed correctly.** `_run_ffmpeg_cmd(cmd, cancel_event=cancel_event)` uses a keyword argument, which matches the function signature and avoids positional ambiguity.
- **All 13 tests pass.** The 4 updated tests correctly patch `_run_ffmpeg_cmd` instead of `subprocess.run`. The 2 new tests cover the two distinct cancellation paths: pre-run guard and in-flight forwarding.
- **Minimal diff.** The change is tightly scoped — no unrelated modifications, no new files.

---

## Issues

### Fixed

**Minor — unused import (`ffmpeg_not_found_error`).**  
After the refactor, `image_clip.py` no longer calls `ffmpeg_not_found_error()` directly (that responsibility moved into `_run_ffmpeg_cmd`), but the name was still present in the import list. This was dead code that would fail a linter check and mislead a reader into thinking the module still handles `FileNotFoundError` locally.

_Resolution:_ Removed `ffmpeg_not_found_error` from the import in `image_clip.py`. All 13 tests continue to pass.

### Not Fixed (observations only)

**Minor — importing a private helper across modules.**  
`_run_ffmpeg_cmd` uses the single-underscore convention signalling "internal to this module." Importing it into `image_clip.py` (and potentially `stitcher.py` in the future) blurs that boundary. This is a pre-existing design decision in `ffmpeg_config.py` and outside the scope of this task, but worth noting if `_run_ffmpeg_cmd` is meant to be a shared utility — dropping the underscore prefix or re-exporting it explicitly would make the intent clearer.

**Minor — unnecessary mocks in `test_generate_image_clip_cancelled_before_run`.**  
Because `cancel_event.is_set()` returns `True` before `Image.open` is reached, both the `Image.open` patch and the `_run_ffmpeg_cmd` patch are set up but never invoked. The test is correct (it asserts `mock_run.assert_not_called()`), but the `Image.open` mock adds noise. Not worth changing on its own.

---

## Assessment

**Approved.**

The implementation is correct and coherent. The one real defect (unused import) has been fixed. The new tests verify the two meaningful cancellation behaviours. The overall change is small, readable, and consistent with the existing `_run_ffmpeg_cmd` pattern in the codebase.
