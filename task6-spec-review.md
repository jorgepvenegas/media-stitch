# Task 6 Spec Review — Stitch Endpoints

**Verdict: ✅ Spec compliant**

All requirements are met and all 236 tests pass (16/16 in `test_web_stitch.py`).

---

## Requirement Checklist

### Imports (`server.py` lines 1, 18–19)

| Requirement | Status | Location |
|---|---|---|
| `import subprocess` | ✅ | `server.py:1` |
| `StitchRequest`, `StitchStatus` | ✅ | `server.py:18` (from `stitch_models`) |
| `start_stitch`, `cancel_stitch`, `StitchJob` | ✅ | `server.py:19` (from `stitch_runner`) |

### App state (`server.py` lines 81–82)

| Requirement | Status | Location |
|---|---|---|
| `app.state.timeline_map = timeline` | ✅ | `server.py:81` |
| `app.state.stitch_job: StitchJob \| None = None` | ✅ | `server.py:82` |

### Endpoint 1 — POST /api/stitch (`server.py` lines 167–180)

- ✅ Validates empty output → raises 422
- ✅ Validates output parent directory exists → raises 400
- ✅ Checks for conflict: `job.state == "running"` → raises 409
- ✅ Calls `start_stitch(app.state.timeline_map, req, stitch_fn=stitch)`
- ✅ Returns `StitchStatus(state="running", ...)` immediately

Note: passing `stitch_fn=stitch` (the server-level import) is intentional — it lets tests use `patch("photowalk.web.server.stitch")` to intercept the callable without needing to patch the runner module.

### Endpoint 2 — POST /api/stitch/cancel (`server.py` lines 182–192)

- ✅ If job is running: calls `cancel_stitch(job)`, returns `state="cancelled"` with output path
- ✅ If no job / not running: returns `state="idle"`

### Endpoint 3 — GET /api/stitch/status (`server.py` lines 194–203)

- ✅ Returns `state="idle"` when `stitch_job is None`
- ✅ Otherwise reflects `job.state`, `job.message`, `job.output_path`

### Endpoint 4 — POST /api/open-folder (`server.py` lines 205–219)

- ✅ 400 if path does not exist
- ✅ macOS: `open`, Windows: `explorer`, Linux: `xdg-open`
- ✅ Exception swallowed (best-effort), always returns `{"ok": True}`

### stitch_runner.py modifications

- ✅ Uses `threading.Thread` + `asyncio.Future` instead of `run_in_executor`
- ✅ Accepts optional `stitch_fn` parameter for test mocking
- ✅ `cancel_event` set → `job.state = "cancelled"`; `ok=True` → `"done"`; `ok=False` → `"error"`; exception → `"error"` with message

### Tests (`tests/test_web_stitch.py`)

16 tests total, all passing:

| # | Test | Kind |
|---|---|---|
| 1 | `test_stitch_request_valid` | model |
| 2 | `test_stitch_request_format_ok` | model |
| 3 | `test_stitch_request_format_invalid` | model |
| 4 | `test_stitch_request_format_partial` | model |
| 5 | `test_stitch_status_serialization` | model |
| 6 | `test_start_stitch_runs_in_background` | runner |
| 7 | `test_start_stitch_sets_error_on_failure` | runner |
| 8 | `test_start_stitch_sets_error_on_exception` | runner |
| 9 | `test_cancel_stitch_sets_cancelled` | runner |
| 10 | `test_api_stitch_validation_empty_output` | **endpoint** |
| 11 | `test_api_stitch_validation_bad_format` | **endpoint** |
| 12 | `test_api_stitch_starts_job` | **endpoint** |
| 13 | `test_api_stitch_conflict_when_running` | **endpoint** |
| 14 | `test_api_stitch_status_idle` | **endpoint** |
| 15 | `test_api_stitch_cancel` | **endpoint** |
| 16 | `test_api_open_folder` | **endpoint** |

**7 endpoint tests** (rows 10–16) as required.

---

## Observations (Non-blocking)

1. **Cancel response is optimistic.** `POST /api/stitch/cancel` returns `state="cancelled"` immediately after setting the cancel event, even though the background thread may still be running. This is reasonable for a best-effort UI signal, and `test_api_stitch_cancel` correctly allows `state in ("cancelled", "running")`. However the actual `job.state` field won't flip to `"cancelled"` until the thread observes the event. If a client polls `/api/stitch/status` immediately after cancel, it may briefly see `"running"`. This is acceptable given the spec's intent.

2. **`asyncio.ensure_future` in sync contexts.** `start_stitch` uses `asyncio.ensure_future(_start_thread())` which piggybacks on whatever event loop is current. This works correctly under FastAPI's ASGI runner and under `asyncio.get_event_loop().run_until_complete(job.task)` in tests (Python 3.10). No issues observed.

3. **`body: dict` type hint on `/api/open-folder`.** FastAPI accepts `dict` as a request body type and parses it from JSON, which works fine here. An explicit Pydantic model would be stricter but is not required by the spec.

---

## Final Test Run

```
236 passed in 1.08s   (full suite)
16 passed in 0.31s    (test_web_stitch.py only)
```
