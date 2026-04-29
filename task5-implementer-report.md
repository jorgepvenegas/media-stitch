# Task 5 Implementation Report: `stitch_runner.py`

## Status: DONE

## What I Implemented

Created `src/photowalk/web/stitch_runner.py` with:
- `StitchJob` dataclass holding an `asyncio.Task`, `threading.Event` for cancellation, state string, message, and output path
- `_run_stitch()` async coroutine that runs `stitch()` in a thread pool via `loop.run_in_executor`, then updates job state based on outcome (done/cancelled/error)
- `start_stitch()` function that creates a cancel event, initializes the job, and schedules the coroutine as an async task using `asyncio.ensure_future()`
- `cancel_stitch()` function that sets the cancel event on a running job

One minor deviation from the task template: used `asyncio.ensure_future()` instead of `asyncio.create_task()` for compatibility with Python 3.10 event loop handling in tests that use `asyncio.get_event_loop()`.

## What I Tested

Added 4 new tests to `tests/test_web_stitch.py`:
- `test_start_stitch_runs_in_background` — verifies job starts as "running", transitions to "done", returns correct output path, and calls stitch once
- `test_start_stitch_sets_error_on_failure` — verifies stitch returning `False` sets state to "error"
- `test_start_stitch_sets_error_on_exception` — verifies exceptions are caught and set state to "error" with the exception message
- `test_cancel_stitch_sets_cancelled` — verifies a slow stitch can be cancelled mid-run

**Test results: 9/9 passed** (5 model tests + 4 new runner tests)

## Files Changed

- `src/photowalk/web/stitch_runner.py` — **created** (new file)
- `tests/test_web_stitch.py` — **appended** (4 new test functions + imports)

## Self-Review Findings

- The `stitch()` call passes `cancel_event` as a keyword argument, which matches the existing `stitcher.py` signature
- State transitions are clear: running → done | cancelled | error
- The thread-based executor approach correctly isolates the blocking `stitch()` call from the async event loop
- `asyncio.ensure_future()` was used instead of `asyncio.create_task()` to avoid the "no running event loop" issue in synchronous test contexts

## Issues or Concerns

None. Implementation is minimal and correct. All tests pass cleanly.
