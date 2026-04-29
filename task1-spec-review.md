# Task 1 Spec Review — `_run_ffmpeg_cmd` in `ffmpeg_config.py`

**Verdict: ✅ Spec compliant**

All 4 tests pass (`uv run pytest tests/test_ffmpeg_config.py -v`).

---

## Implementation check (`src/photowalk/ffmpeg_config.py`)

| Requirement | Actual | Status |
|---|---|---|
| `_run_ffmpeg_cmd(cmd, cancel_event=None)` signature | `def _run_ffmpeg_cmd(cmd: list[str], cancel_event: threading.Event \| None = None) -> bool` | ✅ |
| `subprocess.Popen` with stdout/stderr suppressed | `stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL` | ✅ |
| Raise `RuntimeError` on `FileNotFoundError` using `ffmpeg_not_found_error()` | `except FileNotFoundError: raise RuntimeError(ffmpeg_not_found_error())` | ✅ |
| Poll with `proc.wait(timeout=0.5)` in a loop | `while True: try: proc.wait(timeout=0.5); break` | ✅ |
| On `TimeoutExpired`: check `cancel_event`, if set → terminate → `wait(5)` → kill → return False | Implemented exactly in that order, with inner try/except around `wait(5)` for the kill fallback | ✅ |
| Return `proc.returncode == 0` | `return proc.returncode == 0` | ✅ |

---

## Test check (`tests/test_ffmpeg_config.py`)

| Requirement | Actual | Status |
|---|---|---|
| `test_run_ffmpeg_cmd_success` — mock Popen, assert returns True | Uses `patch("photowalk.ffmpeg_config.subprocess.Popen")`, `returncode=0`, asserts `result is True` | ✅ |
| `test_run_ffmpeg_cmd_failure` — mock Popen with returncode=1, assert returns False | `returncode=1`, asserts `result is False` | ✅ |
| `test_run_ffmpeg_cmd_cancelled` — mock Popen, set cancel_event, assert returns False and terminate called | Uses real `subprocess.TimeoutExpired`, sets event before call, asserts `result is False` and `proc.terminate.assert_called_once()` | ✅ |
| `test_run_ffmpeg_cmd_missing_ffmpeg` — mock Popen raising FileNotFoundError, assert RuntimeError | `side_effect=FileNotFoundError`, catches `RuntimeError`, asserts `"ffmpeg" in str(e).lower()` | ✅ |

---

## Notes

- The implementer's fix noted in their report (using real `subprocess.TimeoutExpired` instead of a fake exception class) is correct and necessary — `side_effect` on a mock must raise actual `BaseException` subclasses, and `subprocess.TimeoutExpired` is the right one here.
- The `test_run_ffmpeg_cmd_missing_ffmpeg` test uses a manual `try/except` instead of `pytest.raises`. This is functionally equivalent and produces a clear failure message via the `assert False, "Expected RuntimeError"` line.
- The cancel test only exercises the happy cancellation path (terminate → `wait(5)` succeeds). The kill fallback path (when `wait(5)` itself times out) is untested but not required by the spec, and the code is correct.
- No extra undocumented features were added beyond `build_scale_pad_filter` and `FfmpegEncodeConfig`, which were pre-existing.
