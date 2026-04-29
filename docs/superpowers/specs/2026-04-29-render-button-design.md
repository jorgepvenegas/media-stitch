# Render Button — Web UI Stitch Trigger

**Date:** 2026-04-29  
**Scope:** Add a "Render" button to the Photo Walk web UI that triggers the video stitcher, shows a confirmation popover with settings, and blocks the UI during stitching with a cancel option.

---

## 1. User Flow

1. User clicks **"Render"** in the sync panel.
2. A **popover modal** appears with:
   - Confirmation message
   - Output path input
   - Resolution input (optional, e.g. `1920x1080`)
   - Draft quality checkbox
   - Image duration input (seconds)
   - Margin input (percentage)
   - "Open output folder when done" checkbox
3. User clicks **"Start Render"** → modal switches to a **progress overlay** with spinner and "Stitching..." text, plus a **Cancel** button.
4. The UI is blocked: the modal backdrop prevents interaction with the rest of the page.
5. The backend runs the stitcher in a background thread.
6. The frontend polls status every 1s.
7. On completion:
   - **Done:** toast "Render complete", open folder if requested, close modal.
   - **Cancelled:** toast "Render cancelled", close modal.
   - **Error:** toast with error message, close modal.

---

## 2. Backend Architecture

### 2.1 New Files

#### `src/photowalk/web/stitch_models.py`

```python
class StitchRequest(BaseModel):
    output: str                    # Absolute or relative output path
    format: str | None = None      # e.g. "1920x1080"
    draft: bool = False
    image_duration: float = 3.5
    margin: float = 15.0
    open_folder: bool = False

class StitchStatus(BaseModel):
    state: Literal["idle", "running", "done", "cancelled", "error"]
    message: str
    output_path: str | None = None
```

#### `src/photowalk/web/stitch_runner.py`

```python
@dataclass
class StitchJob:
    task: asyncio.Task
    cancel_event: threading.Event
    state: str = "running"
    message: str = ""
    output_path: Path | None = None

def start_stitch(
    timeline_map: TimelineMap,
    request: StitchRequest,
) -> StitchJob: ...

def cancel_stitch(job: StitchJob) -> None: ...
```

- `start_stitch` validates the output path (ensures parent directory exists), spawns `stitch()` in `asyncio.to_thread()`, and wraps it in a `StitchJob`.
- `cancel_stitch` sets `job.cancel_event.set()`, which causes running ffmpeg processes to terminate.
- Only **one stitch job at a time** — starting a new job while one is running returns a 409 error.

### 2.2 Modified Files

#### `src/photowalk/stitcher.py`

Add optional cancellation support to the public API:

```python
def stitch(
    timeline_map: TimelineMap,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    image_duration: float = 3.5,
    keep_temp: bool = False,
    draft: bool = False,
    margin: float = 15.0,
    cancel_event: threading.Event | None = None,
) -> bool: ...
```

**Internal changes:**
- `generate_image_clip()`: add `cancel_event` parameter.
- `_split_video_segment()`: add `cancel_event` parameter.
- `run_concat()`: add `cancel_event` parameter.
- Replace `subprocess.run(...)` with `subprocess.Popen(...)` + poll loop:
  ```python
  proc = subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE, text=True)
  while proc.poll() is None:
      if cancel_event and cancel_event.is_set():
          proc.terminate()
          proc.wait(timeout=5)
          return False
      time.sleep(0.5)
  return proc.returncode == 0
  ```
- Before each clip/segment generation, check `cancel_event.is_set()` and return `False` early.
- The existing `finally` block for temp cleanup remains unchanged.

#### `src/photowalk/image_clip.py`

```python
def generate_image_clip(
    image_path: Path,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    duration: float,
    encode_config: FfmpegEncodeConfig | None = None,
    margin: float = 15.0,
    cancel_event: threading.Event | None = None,
) -> bool: ...
```

Same `Popen` + poll pattern as stitcher.

#### `src/photowalk/web/server.py`

- Import `start_stitch`, `cancel_stitch`, `StitchRequest`, `StitchStatus`.
- Store `app.state.timeline_map: TimelineMap` (set during app creation so the stitch endpoint can reuse it).
- Add `app.state.stitch_job: StitchJob | None = None`.
- Add endpoints:
  - `POST /api/stitch` — validates request, starts job if idle.
  - `POST /api/stitch/cancel` — cancels current job.
  - `GET /api/stitch/status` — returns current status.
  - `POST /api/open-folder` — opens the output directory using the OS default file manager.

**`POST /api/stitch` validation:**
- `output` must not be empty.
- Parent directory of `output` must exist (return 400 if not).
- If `format` is provided, must match `WIDTHxHEIGHT` pattern.
- `image_duration` must be > 0.
- `margin` must be ≥ 0.
- Return 409 if a job is already running.

**`POST /api/open-folder`:**
- Body: `{ "path": "/path/to/dir" }`
- Use platform-specific opener:
  - macOS: `subprocess.run(["open", path])`
  - Linux: `subprocess.run(["xdg-open", path])`
  - Windows: `subprocess.run(["explorer", path])`
- Best-effort — failures are logged but not fatal.

---

## 3. Frontend Architecture

### 3.1 Modified Files

#### `src/photowalk/web/assets/index.html`

Add to the sync panel (next to Apply button):
```html
<button id="btn-render" type="button">Render</button>
```

Add new modal after the apply modal:
```html
<div id="render-modal" class="modal" style="display:none;">
  <div class="modal-content">
    <!-- Form view -->
    <div id="render-form">
      <h3>Render Video</h3>
      <p class="render-confirm-text">
        This will generate a stitched video from the current timeline.
        The process may take several minutes.
      </p>
      <div class="render-field">
        <label>Output path</label>
        <input type="text" id="render-output" placeholder="/path/to/output.mp4">
      </div>
      <div class="render-field">
        <label>Resolution (optional)</label>
        <input type="text" id="render-format" placeholder="1920x1080">
      </div>
      <div class="render-field row">
        <label>Draft quality</label>
        <input type="checkbox" id="render-draft">
      </div>
      <div class="render-field">
        <label>Image duration (seconds)</label>
        <input type="number" id="render-image-duration" value="3.5" step="0.1" min="0.1">
      </div>
      <div class="render-field">
        <label>Margin (%)</label>
        <input type="number" id="render-margin" value="15" step="1" min="0">
      </div>
      <div class="render-field row">
        <label>Open output folder when done</label>
        <input type="checkbox" id="render-open-folder">
      </div>
      <div class="modal-actions">
        <button id="btn-render-cancel" type="button">Cancel</button>
        <button id="btn-render-start" type="button">Start Render</button>
      </div>
    </div>
    <!-- Progress view -->
    <div id="render-progress" style="display:none;">
      <div class="render-spinner"></div>
      <p class="render-status">Stitching...</p>
      <button id="btn-render-cancel-run" type="button">Cancel</button>
    </div>
  </div>
</div>
```

#### `src/photowalk/web/assets/style.css`

Add styles for the render modal:
```css
.render-confirm-text { color: #888; font-size: 0.85rem; margin-bottom: 12px; }
.render-field { margin-bottom: 10px; }
.render-field label { display: block; font-size: 0.8rem; color: #888; margin-bottom: 2px; }
.render-field input[type="text"],
.render-field input[type="number"] {
  width: 100%;
  background: #0f0f1a;
  border: 1px solid #333;
  color: #e0e0e0;
  padding: 4px 8px;
  font-family: monospace;
}
.render-field.row { display: flex; align-items: center; gap: 8px; }
.render-field.row label { margin-bottom: 0; }
.render-field.row input[type="checkbox"] { cursor: pointer; }

.render-spinner {
  width: 40px; height: 40px;
  border: 3px solid #333;
  border-top-color: #4a90d9;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 12px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.render-status { text-align: center; color: #e0e0e0; }
#render-progress { text-align: center; padding: 20px; }
```

#### `src/photowalk/web/assets/app.js`

Add render logic:
- Wire `#btn-render` to open `#render-modal`.
- Pre-fill `image_duration` from app state.
- On `#btn-render-start`: collect values, validate (output not empty), POST to `/api/stitch`.
- On success: hide form, show progress, start polling `GET /api/stitch/status` every 1s.
- On `#btn-render-cancel-run`: POST to `/api/stitch/cancel`.
- On status change to `done`:
  - If `open_folder` was checked, POST to `/api/open-folder` with output directory.
  - Show toast, close modal.
- On `cancelled` or `error`: show toast, close modal.
- Modal backdrop already blocks interaction via existing `.modal` CSS.

**Polling cleanup:** clear interval when modal closes or status is terminal.

---

## 4. Data Flow

```
┌─────────────┐    click Render    ┌──────────────┐
│   Browser   │ ─────────────────> │  Render Modal│
│             │                    │  (form view) │
└─────────────┘                    └──────────────┘
       │                                  │
       │  Start Render (POST /api/stitch) │
       │ <────────────────────────────────┘
       │
       ▼
┌─────────────┐    spawn thread     ┌─────────────┐
│  FastAPI    │ ──────────────────> │  stitch()   │
│  /api/stitch│                     │  (thread)   │
└─────────────┘                     └─────────────┘
       │                                  │
       │  poll status (GET /api/stitch/status)
       │ <────────────────────────────────┘
       │
       ▼
┌─────────────┐    done/cancel/error   ┌─────────────┐
│   Browser   │ <──────────────────────│   stitch()  │
│  (progress) │                        │   thread    │
└─────────────┘                        └─────────────┘
```

---

## 5. Error Handling

| Scenario | Behavior |
|----------|----------|
| Output path empty or parent dir missing | Validation error in modal, disable Start button |
| Invalid format string | Validation error in modal (must match `^\d+x\d+$`) |
| Job already running | 409 response, toast "A render is already in progress" |
| ffmpeg not found | `error` status with message "ffmpeg not found" |
| Individual clip fails | `error` status with ffmpeg stderr snippet |
| User cancels | `cancelled` status, temp files cleaned up by stitcher `finally` |
| Open folder fails | Logged on backend, toast still says "Render complete" |

---

## 6. Testing Plan

### 6.1 New Test File: `tests/test_web_stitch.py`

- `test_stitch_start_success` — POST `/api/stitch`, mock `subprocess.Popen` to return quickly, assert status transitions `running` → `done`.
- `test_stitch_start_while_running` — start a job, POST again, assert 409.
- `test_stitch_cancel` — start a job, POST cancel, assert status becomes `cancelled`.
- `test_stitch_validation_bad_format` — POST with format `"abc"`, assert 422.
- `test_stitch_validation_empty_output` — POST with empty output, assert 422.

### 6.2 New Test File: `tests/test_stitcher_cancel.py`

- `test_stitch_cancelled_before_clip` — set cancel event before stitch starts, assert `False` and no subprocess calls.
- `test_stitch_cancelled_during_clip` — mock `Popen` to sleep, set cancel event mid-run, assert process terminated.
- `test_generate_image_clip_cancelled` — same pattern for image clip generation.
- `test_run_concat_cancelled` — same pattern for final concat.

### 6.3 Frontend Tests (manual checklist)

- Click Render → modal opens with image_duration pre-filled.
- Change settings → values preserved.
- Click Cancel → modal closes, no request sent.
- Click Start Render → progress overlay shows.
- Click Cancel during run → status becomes cancelled, modal closes.
- Let run complete → toast appears, folder opens if checkbox checked.

---

## 7. Open Questions / Decisions

1. **Only one concurrent render job** — Simplifies state management. A 409 is returned if the user tries to start another.
2. **Open folder is best-effort** — Uses platform-specific `open`/`xdg-open`/`explorer`. If it fails, the user still sees the output path in the toast.
3. **Polling every 1s** — Simple and sufficient. Server-Sent Events or WebSockets would be overkill for this flow.
4. **No live clip progress** — The stitcher reports only `running`/`done`/`cancelled`/`error`. Per-clip progress is out of scope.
