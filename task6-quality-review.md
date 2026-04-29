# Task 6 Quality Review

## What Was Reviewed

- `src/photowalk/web/server.py` — 4 new endpoints: POST `/api/stitch`, POST `/api/stitch/cancel`, GET `/api/stitch/status`, POST `/api/open-folder`
- `src/photowalk/web/stitch_runner.py` — Refactored from `asyncio.Task` + `run_in_executor` to `threading.Thread` + `asyncio.Future`
- `tests/test_web_stitch.py` — 7 new endpoint tests added alongside existing unit tests

All 236 tests pass (`uv run pytest`).

---

## Strengths

- **Responsibilities are cleanly separated.** `stitch_models.py` owns data shapes, `stitch_runner.py` owns background execution, `server.py` owns HTTP routing. The `stitch_fn` injection pattern is a correct solution to the mock-boundary problem.
- **The `stitch_runner` refactor is well-justified.** Replacing `run_in_executor` with an explicit `threading.Thread` + `asyncio.Future` makes the background execution model transparent and testable synchronously. The docstring explains the design clearly.
- **The conflict (409) and validation (422/400) guard-rails in `/api/stitch` are correct.**
- **Endpoint tests cover the key paths:** idle status, validation failure, job start, conflict, cancel, and open-folder.
- **All unit tests for `stitch_runner` verify observable state** (`job.state`, `job.message`, `cancel_event`) rather than mock internals — good signal-to-noise ratio.

---

## Issues

### Important

**1. `open_folder` field in `StitchRequest` is dead code**

`StitchRequest` declares `open_folder: bool = False`, but this flag is never read by `start_stitch` or anywhere in `server.py`. The separate `/api/open-folder` endpoint handles folder opening. The field implies a "auto-open after render" behavior that does not exist, creating a misleading contract for API consumers.

```python
# stitch_models.py
class StitchRequest(BaseModel):
    ...
    open_folder: bool = False  # never read by server or stitch_runner
```

Fix: Either remove the field, or wire it up so that `/api/stitch` calls `/api/open-folder` (or its internal logic) when `ok` and `open_folder=True`.

---

### Minor

**2. `import sys` inside endpoint body**

```python
@app.post("/api/open-folder")
async def api_open_folder(body: dict):
    import sys   # ← should be at module level
```

`sys` is a stdlib module. Importing it inside the function works but obscures the dependency and is inconsistent with the rest of the file. Move it to the top of `server.py`.

---

**3. `MagicMock` is imported but never used in the test file**

```python
from unittest.mock import patch, MagicMock  # MagicMock is unused
```

Remove `MagicMock` from the import.

---

**4. Test-file imports are split across the middle of the file**

`asyncio`, `threading`, `datetime`, `Path`, `patch`, `MagicMock`, `TimelineMap`, `TimelineEntry`, `StitchJob`, `start_stitch`, `cancel_stitch` are all imported at line 38–46, between the model tests and the runner tests. All imports should be at the top of the file per PEP 8 and general readability.

---

**5. `test_api_stitch_cancel` assertion includes an impossible state**

```python
assert r.json()["state"] in ("cancelled", "running")
```

The cancel endpoint always returns a hardcoded `StitchStatus(state="cancelled", ...)` when a running job is detected — it can never return `"running"`. Including `"running"` in the assertion looks like leftover uncertainty from development. The assertion should simply be:

```python
assert r.json()["state"] == "cancelled"
```

---

**6. `asyncio.get_event_loop()` fallback is deprecated in Python 3.10 and broken in Python 3.12+**

In `stitch_runner.py`:

```python
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.get_event_loop()  # ← deprecated since 3.10, RuntimeError in 3.12+
```

The project declares `requires-python = ">=3.10"`, which allows Python 3.12+. On 3.12, calling `asyncio.get_event_loop()` in the main thread without a running loop raises `RuntimeError` if no current event loop is set, breaking the unit-test path for `start_stitch`. The `test_start_stitch_*` tests currently pass only because the venv is 3.10.

Fix for the sync/test path: use `asyncio.new_event_loop()` as a fallback and set it, or restructure tests to always run inside an event loop (e.g. use `pytest-asyncio` or an explicit `asyncio.run()`).

```python
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
```

---

## Assessment

**Needs Changes**

The implementation is functionally correct and well-structured. The critical design decisions (thread isolation, Future-based awaitable, mock-boundary injection) are sound. However, the dead `open_folder` field (Important) creates a false API contract that should be resolved before shipping, and the `asyncio.get_event_loop()` fallback (Minor but forward-looking) will silently break if the venv is ever upgraded to Python 3.12+. The remaining issues are low-risk housekeeping.
