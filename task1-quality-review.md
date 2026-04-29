# Task 1 Quality Review — `_run_ffmpeg_cmd`

## Scope

- `src/photowalk/ffmpeg_config.py` — added `_run_ffmpeg_cmd`
- `tests/test_ffmpeg_config.py` — new test file (4 tests)
- All 214 project tests pass after the change.

---

## Strengths

- **Right file, right responsibility.** The helper lives in `ffmpeg_config.py` alongside the encode-config dataclass and the `ffmpeg_not_found_error` message, which is a natural home for shared ffmpeg plumbing.
- **Cancellation logic is correct.** The `Popen` + polling loop with `wait(timeout=0.5)` is the only sensible way to support cancellation; `subprocess.run` cannot be interrupted. The terminate → wait(5) → kill fallback is a proper escalating shutdown sequence.
- **FileNotFoundError → RuntimeError translation is clean** and reuses the existing `ffmpeg_not_found_error()` message.
- **File is still small.** The module grew from 22 to 55 lines — well within reasonable bounds.
- **Tests cover the main paths** (success, nonzero exit, cancellation, missing binary).

---

## Issues

### Important — Dead mock setup in tests misleads future readers

Both `test_run_ffmpeg_cmd_success` and `test_run_ffmpeg_cmd_failure` set up mock state that the implementation never uses:

```python
# set in tests, but _run_ffmpeg_cmd never calls proc.poll()
proc.poll.return_value = 0

# provides 2 values, but wait() returning normally causes an immediate break —
# the second element is never consumed
proc.wait.side_effect = [None, None]
```

The `poll()` mock in particular suggests the tests were originally written for a different implementation (a `poll()`-based loop) and were not cleaned up when the code settled on `wait(timeout=...)`. Stale mock config is misleading to any future reader and can mask real behavioral gaps.

**Fix:** Remove `proc.poll.return_value` entirely from both tests. Reduce `side_effect` to a single-element list (or drop it and use a plain `return_value`).

```python
# test_run_ffmpeg_cmd_success
proc = MagicMock()
proc.wait.return_value = None   # succeeds on first poll
proc.returncode = 0

# test_run_ffmpeg_cmd_failure
proc = MagicMock()
proc.wait.return_value = None
proc.returncode = 1
```

### Important — stderr is silenced; failures produce no diagnostic output

Every other subprocess caller in the project captures stderr:

```python
# writers.py, stitcher.py, image_clip.py, offset_detector.py
result = subprocess.run(cmd, capture_output=True, text=True, check=False)
```

`_run_ffmpeg_cmd` uses `stderr=subprocess.DEVNULL`, so if ffmpeg exits nonzero the caller only learns `False` — no message, no log line. Combined with the fact that the AGENTS.md pattern says *"Writing failures → return False, log warning"*, the missing warning is a real gap: callers that use this helper will silently swallow ffmpeg error output.

**Fix:** Capture stderr and emit a `warnings.warn` (or a logger call) when `returncode != 0`.  
The simplest approach that stays close to the existing style:

```python
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
...
# after the loop
if proc.returncode != 0:
    stderr_text = proc.stderr.read().decode(errors="replace").strip()
    if stderr_text:
        import warnings
        warnings.warn(f"ffmpeg exited {proc.returncode}: {stderr_text}", stacklevel=2)
return proc.returncode == 0
```

### Minor — `test_run_ffmpeg_cmd_missing_ffmpeg` uses `assert False` anti-pattern

```python
try:
    _run_ffmpeg_cmd(["ffmpeg", "-version"])
    assert False, "Expected RuntimeError"   # ← non-idiomatic
except RuntimeError as e:
    assert "ffmpeg" in str(e).lower()
```

The idiomatic pytest form is:

```python
with pytest.raises(RuntimeError, match="ffmpeg"):
    _run_ffmpeg_cmd(["ffmpeg", "-version"])
```

### Minor — Unused import in test file

`ffmpeg_not_found_error` is imported at the top of `test_ffmpeg_config.py` but never called directly in any test. The exception message is checked indirectly via `str(e).lower()`. Remove the import or add a direct test for the helper.

### Minor — `kill()` fallback path is untested

The code path where `proc.terminate()` is called but `proc.wait(timeout=5)` still raises `TimeoutExpired` (triggering `proc.kill()`) has no test. This is a secondary edge case but it is the only branch in the cancellation flow that isn't exercised.

---

## Assessment

**Needs Changes**

The implementation logic is sound, but two important issues should be addressed before this is considered complete: the dead mock setup in the tests actively misleads readers about how the code works, and the total suppression of stderr output diverges from every other subprocess call in the project and leaves callers with no diagnostic signal on failure.

The minor issues (anti-pattern assertion, unused import, missing kill-path test) should also be cleaned up but are low risk.
