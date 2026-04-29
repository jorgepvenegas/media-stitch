# Task 1 Fix Report

**Status:** DONE

## What was fixed

### Issue 1: Dead mock setup in tests
- Removed `proc.poll.return_value` from `test_run_ffmpeg_cmd_success` and `test_run_ffmpeg_cmd_failure` — `poll()` is not called by the implementation.
- Changed `proc.wait.side_effect = [None, None]` → `proc.wait.return_value = None` in both tests (single return value is sufficient; two elements was an off-by-one artefact).
- Added `proc.stderr = None` to `test_run_ffmpeg_cmd_failure` so the new stderr-capture branch is exercised safely.

### Issue 2: stderr completely silenced
- Changed `stderr=subprocess.DEVNULL` → `stderr=subprocess.PIPE` in `ffmpeg_config._run_ffmpeg_cmd`.
- Added post-loop warning block: if `proc.returncode != 0` and stderr is non-empty, emit `warnings.warn(f"ffmpeg exited {returncode}: {stderr_text}", stacklevel=2)`.

### Issue 3: Non-idiomatic assertion in missing_ffmpeg test
- Replaced `try/except/assert False` with `pytest.raises(RuntimeError, match="ffmpeg")`.

### Issue 4: Unused import
- Removed `ffmpeg_not_found_error` from the import in `tests/test_ffmpeg_config.py`.

## Test results

```
tests/test_ffmpeg_config.py — 4/4 passed
Full suite — 214/214 passed (0 regressions)
```

## Remaining concerns

None. All changes are minimal and targeted to the review findings.
