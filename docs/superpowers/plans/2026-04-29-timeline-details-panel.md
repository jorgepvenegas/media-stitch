# Timeline Details Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 300px right-hand details panel to the web timeline UI that shows the metadata of the file most recently clicked in the sidebar or timeline, including timestamps (with original→shifted view when a sync preview is pending), per-segment trim info for `video_segment` clicks, and EXIF for photos.

**Architecture:** Server consolidates the two existing per-file serializers into one shared helper and extends it with the additional photo (camera_model, shutter_speed, iso, focal_length) and video (end_timestamp) fields. The client adds a single new column in `#bottom`, a `renderDetails(source, entry)` function called from existing sidebar / timeline click paths, and a snapshot of unshifted file data so it can render `original → shifted` while a preview is active.

**Tech Stack:** FastAPI, Pydantic models (already present), pytest + fastapi.testclient (server tests), vanilla DOM JS (no client test infra; manual browser verification at the end).

---

## File Structure

**New files:**
- `src/photowalk/web/file_entry.py` — single source of truth for converting a `(Path, PhotoMetadata | VideoMetadata)` pair into the dict shape returned by `/api/files`, the `apply` response, and the preview response. Optional `shifted: bool` parameter.

**Modified files:**
- `src/photowalk/web/server.py` — replace `_metadata_to_file_entry` with import from new module.
- `src/photowalk/web/sync_preview.py` — replace `_serialize_file` with import from new module.
- `src/photowalk/web/assets/index.html` — add `#details-panel` markup inside `#bottom`.
- `src/photowalk/web/assets/style.css` — add styles for the panel and its rows.
- `src/photowalk/web/assets/app.js` — snapshot original files, add `renderDetails`, wire into selection handlers, reset on Clear.
- `tests/test_web_server.py` — extend `/api/files` test with new fields.
- `tests/test_web_sync_preview.py` — extend preview-files test with new fields.
- `tests/test_web_sync_endpoints.py` — extend apply-response test with new fields.

---

## Task 1: Lift shared file-entry helper

**Files:**
- Create: `src/photowalk/web/file_entry.py`
- Test: `tests/test_web_file_entry.py`

The two existing serializers (`_metadata_to_file_entry` in `server.py` and `_serialize_file` in `sync_preview.py`) are nearly identical. This task moves the logic into one place behind a single public function so later tasks have one place to add new fields. Behavior is unchanged.

- [ ] **Step 1: Write failing tests for the new module**

Create `tests/test_web_file_entry.py`:

```python
from datetime import datetime
from pathlib import Path

from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.web.file_entry import metadata_to_file_entry


def test_photo_entry_basic_fields():
    meta = PhotoMetadata(
        source_path=Path("/a.jpg"),
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
    )
    entry = metadata_to_file_entry(Path("/a.jpg"), meta)
    assert entry["path"] == "/a.jpg"
    assert entry["type"] == "photo"
    assert entry["timestamp"] == "2024-01-01T12:00:00"
    assert entry["duration_seconds"] is None
    assert entry["has_timestamp"] is True
    assert entry["shifted"] is False


def test_video_entry_basic_fields():
    meta = VideoMetadata(
        source_path=Path("/v.mp4"),
        start_timestamp=datetime(2024, 1, 1, 12, 0, 0),
        end_timestamp=datetime(2024, 1, 1, 12, 1, 0),
        duration_seconds=60.0,
    )
    entry = metadata_to_file_entry(Path("/v.mp4"), meta)
    assert entry["type"] == "video"
    assert entry["timestamp"] == "2024-01-01T12:00:00"
    assert entry["duration_seconds"] == 60.0
    assert entry["has_timestamp"] is True
    assert entry["shifted"] is False


def test_photo_with_no_timestamp_marks_has_timestamp_false():
    meta = PhotoMetadata(source_path=Path("/a.jpg"))
    entry = metadata_to_file_entry(Path("/a.jpg"), meta)
    assert entry["timestamp"] is None
    assert entry["has_timestamp"] is False


def test_shifted_flag_passes_through():
    meta = PhotoMetadata(
        source_path=Path("/a.jpg"),
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
    )
    entry = metadata_to_file_entry(Path("/a.jpg"), meta, shifted=True)
    assert entry["shifted"] is True
```

- [ ] **Step 2: Run the tests; verify they fail**

```bash
uv run pytest tests/test_web_file_entry.py -v
```

Expected: ImportError or ModuleNotFoundError for `photowalk.web.file_entry`.

- [ ] **Step 3: Implement the module**

Create `src/photowalk/web/file_entry.py`:

```python
"""Shared serializer for the per-file dict shape returned by web endpoints.

Single source of truth for /api/files, the preview response, and the
apply response.  Earlier the same shape was duplicated across server.py
and sync_preview.py; keep new fields in one place.
"""

from pathlib import Path

from photowalk.models import PhotoMetadata, VideoMetadata


def metadata_to_file_entry(
    path: Path,
    meta: "PhotoMetadata | VideoMetadata",
    *,
    shifted: bool = False,
) -> dict:
    if isinstance(meta, PhotoMetadata):
        return {
            "path": str(path),
            "type": "photo",
            "timestamp": meta.timestamp.isoformat() if meta.timestamp else None,
            "duration_seconds": None,
            "has_timestamp": meta.timestamp is not None,
            "shifted": shifted,
        }
    return {
        "path": str(path),
        "type": "video",
        "timestamp": (
            meta.start_timestamp.isoformat() if meta.start_timestamp else None
        ),
        "duration_seconds": meta.duration_seconds,
        "has_timestamp": meta.start_timestamp is not None,
        "shifted": shifted,
    }
```

- [ ] **Step 4: Run the tests; verify they pass**

```bash
uv run pytest tests/test_web_file_entry.py -v
```

Expected: 4 passing tests.

- [ ] **Step 5: Replace `_metadata_to_file_entry` in `server.py`**

In `src/photowalk/web/server.py`, delete the local `_metadata_to_file_entry` function and replace its two call sites with the shared helper:

```python
# Top of file, with the other imports:
from photowalk.web.file_entry import metadata_to_file_entry
```

Replace the two call sites (one in `create_app` populating `app.state.file_list`, one in `build_app_from_path`) with `metadata_to_file_entry(_path, _meta)` / `metadata_to_file_entry(f, meta)` respectively. Note: the existing server code never set `shifted`; the helper defaults it to False, preserving behavior.

- [ ] **Step 6: Replace `_serialize_file` in `sync_preview.py`**

In `src/photowalk/web/sync_preview.py`, delete `_serialize_file` and import the shared helper:

```python
# Top of file, with the other imports:
from photowalk.web.file_entry import metadata_to_file_entry
```

Update `build_preview` to use it:

```python
files = [
    metadata_to_file_entry(p, m, shifted=str(p) in shifted_paths)
    for p, m in sorted(shifted_pairs, key=lambda pm: str(pm[0]))
]
```

- [ ] **Step 7: Run the full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all previously-passing tests still pass; 4 new tests in `test_web_file_entry.py` pass. No regressions.

- [ ] **Step 8: Commit**

```bash
git add src/photowalk/web/file_entry.py src/photowalk/web/server.py src/photowalk/web/sync_preview.py tests/test_web_file_entry.py
git commit -m "refactor(web): consolidate per-file serializer into file_entry module"
```

---

## Task 2: Add new metadata fields to file-entry helper

Extend the helper with the EXIF fields for photos and `end_timestamp` for videos. Server endpoints automatically pick them up because all three (`/api/files`, preview, apply) go through the same helper now.

**Files:**
- Modify: `src/photowalk/web/file_entry.py`
- Test: `tests/test_web_file_entry.py`

- [ ] **Step 1: Add failing tests for the new fields**

Append to `tests/test_web_file_entry.py`:

```python
def test_photo_entry_includes_camera_fields():
    meta = PhotoMetadata(
        source_path=Path("/a.jpg"),
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        camera_model="Canon EOS R6",
        shutter_speed="1/250",
        iso=400,
        focal_length="35mm",
    )
    entry = metadata_to_file_entry(Path("/a.jpg"), meta)
    assert entry["camera_model"] == "Canon EOS R6"
    assert entry["shutter_speed"] == "1/250"
    assert entry["iso"] == 400
    assert entry["focal_length"] == "35mm"


def test_photo_entry_camera_fields_default_to_none():
    meta = PhotoMetadata(source_path=Path("/a.jpg"))
    entry = metadata_to_file_entry(Path("/a.jpg"), meta)
    assert entry["camera_model"] is None
    assert entry["shutter_speed"] is None
    assert entry["iso"] is None
    assert entry["focal_length"] is None


def test_video_entry_includes_end_timestamp():
    meta = VideoMetadata(
        source_path=Path("/v.mp4"),
        start_timestamp=datetime(2024, 1, 1, 12, 0, 0),
        end_timestamp=datetime(2024, 1, 1, 12, 1, 0),
        duration_seconds=60.0,
    )
    entry = metadata_to_file_entry(Path("/v.mp4"), meta)
    assert entry["end_timestamp"] == "2024-01-01T12:01:00"


def test_video_entry_end_timestamp_none_when_missing():
    meta = VideoMetadata(source_path=Path("/v.mp4"))
    entry = metadata_to_file_entry(Path("/v.mp4"), meta)
    assert entry["end_timestamp"] is None
```

- [ ] **Step 2: Run the new tests; verify they fail**

```bash
uv run pytest tests/test_web_file_entry.py -v -k "camera or end_timestamp"
```

Expected: 4 failures with KeyError on the missing keys.

- [ ] **Step 3: Add the fields to the helper**

Update `src/photowalk/web/file_entry.py`:

```python
def metadata_to_file_entry(
    path: Path,
    meta: "PhotoMetadata | VideoMetadata",
    *,
    shifted: bool = False,
) -> dict:
    if isinstance(meta, PhotoMetadata):
        return {
            "path": str(path),
            "type": "photo",
            "timestamp": meta.timestamp.isoformat() if meta.timestamp else None,
            "duration_seconds": None,
            "has_timestamp": meta.timestamp is not None,
            "shifted": shifted,
            "camera_model": meta.camera_model,
            "shutter_speed": meta.shutter_speed,
            "iso": meta.iso,
            "focal_length": meta.focal_length,
        }
    return {
        "path": str(path),
        "type": "video",
        "timestamp": (
            meta.start_timestamp.isoformat() if meta.start_timestamp else None
        ),
        "duration_seconds": meta.duration_seconds,
        "has_timestamp": meta.start_timestamp is not None,
        "shifted": shifted,
        "end_timestamp": (
            meta.end_timestamp.isoformat() if meta.end_timestamp else None
        ),
    }
```

- [ ] **Step 4: Run all tests in file**

```bash
uv run pytest tests/test_web_file_entry.py -v
```

Expected: 8 passing tests.

- [ ] **Step 5: Add an endpoint-level assertion in `test_web_server.py`**

Append to `tests/test_web_server.py`:

```python
def test_api_files_includes_camera_fields_for_photos(tmp_path):
    img = Path("/tmp/photo.jpg")
    meta = PhotoMetadata(
        source_path=img,
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        camera_model="Canon EOS R6",
        shutter_speed="1/250",
        iso=400,
        focal_length="35mm",
    )
    timeline = TimelineMap()
    file_entry = {
        "path": str(img),
        "type": "photo",
        "timestamp": "2024-01-01T12:00:00",
        "duration_seconds": None,
        "has_timestamp": True,
        "shifted": False,
        "camera_model": "Canon EOS R6",
        "shutter_speed": "1/250",
        "iso": 400,
        "focal_length": "35mm",
    }
    app = create_app(
        {img}, timeline, metadata_pairs=[(img, meta)], file_list=[file_entry]
    )
    client = TestClient(app)
    response = client.get("/api/files")
    files = response.json()["files"]
    assert files[0]["camera_model"] == "Canon EOS R6"
    assert files[0]["shutter_speed"] == "1/250"
    assert files[0]["iso"] == 400
    assert files[0]["focal_length"] == "35mm"
```

Note: this test passes a pre-built `file_list` so it doesn't depend on real EXIF extraction — it's verifying the response shape only. The first task already changed server.py to use the shared helper, so the production code path produces exactly this shape.

- [ ] **Step 6: Run server tests; verify pass**

```bash
uv run pytest tests/test_web_server.py -v
```

Expected: all pass, including the new test.

- [ ] **Step 7: Add an assertion in `test_web_sync_preview.py`**

In `tests/test_web_sync_preview.py`, find one of the existing `build_preview` tests that returns photo data and assert the new field is present. If no such test exists, append a new minimal one. Example addition:

```python
def test_build_preview_files_include_camera_fields():
    photo = PhotoMetadata(
        source_path=Path("/a.jpg"),
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        camera_model="Canon EOS R6",
        iso=400,
    )
    pairs = [(Path("/a.jpg"), photo)]
    result = build_preview(pairs, [], image_duration=3.5)
    assert result["files"][0]["camera_model"] == "Canon EOS R6"
    assert result["files"][0]["iso"] == 400
```

(Adjust imports at the top of the file if `PhotoMetadata` isn't already imported.)

- [ ] **Step 8: Run preview tests; verify pass**

```bash
uv run pytest tests/test_web_sync_preview.py -v
```

Expected: all pass.

- [ ] **Step 9: Add an assertion in `test_web_sync_endpoints.py`**

Find the existing apply-response test (around `tests/test_web_sync_endpoints.py:337`) — it asserts on `files[0]["timestamp"]`. Add an assertion immediately after it:

```python
assert "camera_model" in files[0]
assert "end_timestamp" in files[0] or files[0]["type"] == "photo"
```

The conditional handles the case where the test fixture's first file is a photo (which has `camera_model` but no `end_timestamp`) vs. a video (vice versa). If the existing test already pins file order, simplify accordingly.

- [ ] **Step 10: Run endpoint tests; verify pass**

```bash
uv run pytest tests/test_web_sync_endpoints.py -v
```

Expected: all pass.

- [ ] **Step 11: Full test sweep**

```bash
uv run pytest tests/ -v
```

Expected: all green.

- [ ] **Step 12: Commit**

```bash
git add src/photowalk/web/file_entry.py tests/test_web_file_entry.py tests/test_web_server.py tests/test_web_sync_preview.py tests/test_web_sync_endpoints.py
git commit -m "feat(web): expose camera EXIF and video end timestamp via /api/files"
```

---

## Task 3: HTML + CSS scaffolding for the details panel

Add the column markup with the empty state and the styles. Nothing dynamic yet.

**Files:**
- Modify: `src/photowalk/web/assets/index.html`
- Modify: `src/photowalk/web/assets/style.css`

- [ ] **Step 1: Add the panel markup**

In `src/photowalk/web/assets/index.html`, inside the `#bottom` div (after the `#timeline` div, before the closing `</div>` of `#bottom`):

```html
<div id="details-panel">
  <h3>Details</h3>
  <div id="details-panel-body">
    <div id="details-empty">Select a file to see data</div>
  </div>
</div>
```

The new structure inside `#bottom` should be:

```html
<div id="bottom">
  <div id="sidebar">…</div>
  <div id="timeline">…</div>
  <div id="details-panel">…</div>
</div>
```

- [ ] **Step 2: Add the styles**

Append to `src/photowalk/web/assets/style.css`:

```css
/* Details panel */
#details-panel {
  width: 300px;
  background: #16213e;
  border-left: 1px solid #333;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
#details-panel h3 {
  padding: 12px 16px;
  font-size: 0.9rem;
  border-bottom: 1px solid #333;
}
#details-panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}
#details-empty {
  color: #666;
  font-style: italic;
  text-align: center;
  padding-top: 40px;
}
.details-section {
  margin-bottom: 16px;
}
.details-section h4 {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #888;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.details-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.85rem;
  padding: 2px 0;
  gap: 8px;
}
.details-row .label {
  color: #888;
  flex-shrink: 0;
}
.details-row .value {
  color: #e0e0e0;
  text-align: right;
  word-break: break-word;
}
.details-row.path .value {
  font-family: monospace;
  font-size: 0.75rem;
  text-align: left;
  width: 100%;
}
.details-row.path {
  flex-direction: column;
  gap: 2px;
}
.details-shift .original {
  color: #888;
  text-decoration: line-through;
  margin-right: 4px;
}
.details-shift .arrow {
  color: #d9a04a;
  margin: 0 4px;
}
.details-shift .shifted {
  color: #e0e0e0;
  font-weight: 600;
}
```

- [ ] **Step 3: Manually verify the panel appears**

Run:

```bash
uv run photowalk web tests/fixtures
```

(or any folder with media — the fixtures folder may have nothing renderable, in which case use a real folder you have on disk.) Open `http://localhost:8080`. Confirm:
- A 300px column appears on the right of the timeline.
- It has the "Details" header.
- The body says "Select a file to see data" centered.
- Layout doesn't break on smaller windows (the timeline column shrinks; sidebar and details column stay fixed).

Stop the server (Ctrl+C).

- [ ] **Step 4: Commit**

```bash
git add src/photowalk/web/assets/index.html src/photowalk/web/assets/style.css
git commit -m "feat(web): scaffold details panel column with empty state"
```

---

## Task 4: Snapshot original files and add `renderDetails` skeleton

Wire the panel up to the existing `selectFile` flow. This task implements the **File** section and the empty-state reset; later tasks add Timestamps, Segment, Camera, and the shifted view.

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Snapshot original file payload at load and after apply**

The existing app already has `originalTimestamps: path → ISO string`, which is too narrow for the panel (we also need original `end_timestamp`, etc.). Replace it with a richer snapshot.

In `app.js`, change the state declarations near the top (currently around line 8):

```javascript
let originalFilesByPath = {};       // path -> full file record at app load (or after apply)
```

Remove the `originalTimestamps` declaration. Update the initial-load block (currently around line 19) to populate the new map:

```javascript
allFiles = filesData.files;
originalFilesByPath = {};
allFiles.forEach(f => { originalFilesByPath[f.path] = f; });
```

In `confirmApply` (currently around line 442), replace the equivalent block:

```javascript
allFiles = res.files;
lastPreviewFiles = res.files;
originalFilesByPath = {};
allFiles.forEach(f => { originalFilesByPath[f.path] = f; });
```

In `openApplyModal` (currently around line 413), replace the lookup:

```javascript
const oldRec = originalFilesByPath[f.path];
const oldTs = (oldRec && oldRec.timestamp) || '(none)';
row.textContent = `${f.path.split('/').pop()}  ${oldTs}  →  ${f.timestamp}`;
```

- [ ] **Step 2: Add the `renderDetails` function (skeleton + File section)**

Add this function inside the IIFE in `app.js`, near the other render functions:

```javascript
function renderDetails(source, entry) {
  const body = document.getElementById('details-panel-body');
  body.innerHTML = '';

  // Resolve the file path from either a sidebar file record or a timeline entry.
  const path = entry.path || entry.source_path;
  const file = originalFilesByPath[path];
  if (!file) {
    body.innerHTML = '<div id="details-empty">Select a file to see data</div>';
    return;
  }

  const filename = path.split('/').pop();

  const fileSection = document.createElement('div');
  fileSection.className = 'details-section';
  fileSection.innerHTML = `
    <h4>File</h4>
    <div class="details-row"><span class="label">Name</span><span class="value"><strong>${escapeHtml(filename)}</strong></span></div>
    <div class="details-row"><span class="label">Type</span><span class="value">${escapeHtml(file.type)}</span></div>
    <div class="details-row path"><span class="label">Path</span><span class="value">${escapeHtml(path)}</span></div>
  `;
  body.appendChild(fileSection);
}

function clearDetails() {
  const body = document.getElementById('details-panel-body');
  body.innerHTML = '<div id="details-empty">Select a file to see data</div>';
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}
```

- [ ] **Step 3: Hook the function into selectFile call sites**

In `app.js`, find the sidebar block click (currently line 83):

```javascript
block.addEventListener('click', () => selectFile(f.path, f.type, el));
```

Change to:

```javascript
block.addEventListener('click', () => {
  selectFile(f.path, f.type, el);
  renderDetails('sidebar', f);
});
```

Find the timeline rect click (currently line 224):

```javascript
rect.addEventListener('click', () => selectFile(entry.source_path, rect.dataset.kind, rect));
```

Change to:

```javascript
rect.addEventListener('click', () => {
  selectFile(entry.source_path, rect.dataset.kind, rect);
  renderDetails('timeline', entry);
});
```

- [ ] **Step 4: Wire the Clear-selection button to also reset the panel**

In `bindSyncPanel`, find the existing handler (currently line 120):

```javascript
document.getElementById('btn-clear-selection').addEventListener('click', () => {
  selection.clear();
  renderSidebar(allFiles);
  updateButtons();
});
```

Add `clearDetails()` at the end of the body. (The semantics: "Clear" today only clears checkbox selection. Per the spec, it should also clear the visible-detail target. If you want to keep them separate, skip this and add an explicit close button in a follow-up — but the spec calls for piggy-backing on Clear.)

```javascript
document.getElementById('btn-clear-selection').addEventListener('click', () => {
  selection.clear();
  renderSidebar(allFiles);
  updateButtons();
  clearDetails();
});
```

- [ ] **Step 5: Manual verification — File section appears**

```bash
uv run photowalk web /path/to/some/photos
```

In the browser:
- Click a file in the sidebar — File section appears with Name (bold), Type, Path (monospace, wraps).
- Click a bar in the timeline — same File section appears.
- Click "Clear" in the sync panel — panel returns to "Select a file to see data".
- Verify no JavaScript console errors.

Stop the server.

- [ ] **Step 6: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat(web): render details-panel File section on file selection"
```

---

## Task 5: Render Timestamps section (no segment, no shift)

Add the always-on Timestamps section using values from the original file record.

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Extend `renderDetails` with the Timestamps section**

Inside `renderDetails`, after appending `fileSection`, add:

```javascript
const tsSection = document.createElement('div');
tsSection.className = 'details-section';

const dash = '<span class="value" style="color:#666;">—</span>';
let rows = '';

if (file.type === 'photo') {
  const captured = file.timestamp
    ? `<span class="value">${escapeHtml(formatDateTime(file.timestamp))}</span>`
    : dash;
  rows += `<div class="details-row"><span class="label">Captured</span>${captured}</div>`;
} else {
  // video
  const start = file.timestamp
    ? `<span class="value">${escapeHtml(formatDateTime(file.timestamp))}</span>`
    : dash;
  const end = file.end_timestamp
    ? `<span class="value">${escapeHtml(formatDateTime(file.end_timestamp))}</span>`
    : dash;
  const dur = file.duration_seconds != null
    ? `<span class="value">${file.duration_seconds.toFixed(2)}s</span>`
    : dash;
  rows += `<div class="details-row"><span class="label">Start</span>${start}</div>`;
  rows += `<div class="details-row"><span class="label">End</span>${end}</div>`;
  rows += `<div class="details-row"><span class="label">Duration</span>${dur}</div>`;
}

tsSection.innerHTML = `<h4>Timestamps</h4>${rows}`;
body.appendChild(tsSection);
```

- [ ] **Step 2: Add the `formatDateTime` helper**

Inside the IIFE, alongside `escapeHtml`:

```javascript
function formatDateTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}
```

- [ ] **Step 3: Manual verification**

```bash
uv run photowalk web /path/to/some/media
```

- Click a photo: Timestamps section shows "Captured" with the local-formatted date.
- Click a video: Timestamps section shows Start, End, Duration (e.g. `4.23s`).
- Click a file with no timestamp (if any): the row shows `—` instead.
- Stop the server.

- [ ] **Step 4: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat(web): render Timestamps section in details panel"
```

---

## Task 6: Render "This segment" + "Source video" blocks for video_segment clicks

When the user clicks a `video_segment` bar on the timeline, prepend a "This segment" block to the Timestamps section and label the existing video timestamps as "Source video".

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Branch on source + entry kind**

Replace the Timestamps-section block from Task 5 with this version, which conditionally adds the segment sub-block:

```javascript
const tsSection = document.createElement('div');
tsSection.className = 'details-section';

const dash = '<span class="value" style="color:#666;">—</span>';
const isSegmentClick = source === 'timeline' && entry.kind === 'video_segment';

let html = '<h4>Timestamps</h4>';

if (isSegmentClick) {
  const segStart = entry.start_time
    ? `<span class="value">${escapeHtml(formatDateTime(entry.start_time))}</span>`
    : dash;
  const segDur = entry.duration_seconds != null
    ? `<span class="value">${entry.duration_seconds.toFixed(2)}s</span>`
    : dash;
  const trimStart = entry.trim_start != null
    ? `<span class="value">${entry.trim_start.toFixed(2)}s</span>`
    : dash;
  const trimEnd = entry.trim_end != null
    ? `<span class="value">${entry.trim_end.toFixed(2)}s</span>`
    : dash;

  html += '<div style="font-size:0.75rem;color:#888;margin-bottom:4px;">This segment</div>';
  html += `<div class="details-row"><span class="label">Start on timeline</span>${segStart}</div>`;
  html += `<div class="details-row"><span class="label">Trim start</span>${trimStart}</div>`;
  html += `<div class="details-row"><span class="label">Trim end</span>${trimEnd}</div>`;
  html += `<div class="details-row"><span class="label">Segment duration</span>${segDur}</div>`;
  html += '<div style="font-size:0.75rem;color:#888;margin:8px 0 4px;">Source video</div>';
}

if (file.type === 'photo') {
  const captured = file.timestamp
    ? `<span class="value">${escapeHtml(formatDateTime(file.timestamp))}</span>`
    : dash;
  html += `<div class="details-row"><span class="label">Captured</span>${captured}</div>`;
} else {
  const start = file.timestamp
    ? `<span class="value">${escapeHtml(formatDateTime(file.timestamp))}</span>`
    : dash;
  const end = file.end_timestamp
    ? `<span class="value">${escapeHtml(formatDateTime(file.end_timestamp))}</span>`
    : dash;
  const dur = file.duration_seconds != null
    ? `<span class="value">${file.duration_seconds.toFixed(2)}s</span>`
    : dash;
  html += `<div class="details-row"><span class="label">Start</span>${start}</div>`;
  html += `<div class="details-row"><span class="label">End</span>${end}</div>`;
  html += `<div class="details-row"><span class="label">Duration</span>${dur}</div>`;
}

tsSection.innerHTML = html;
body.appendChild(tsSection);
```

- [ ] **Step 2: Manual verification**

```bash
uv run photowalk web /path/to/folder/with/long/video/and/photo/in/middle
```

You need a folder where one video has at least one photo timestamp falling within the video's time range — that produces `video_segment` entries on the timeline.

- Click the segment bar — both "This segment" (with timeline start, trim start, trim end, segment duration) and "Source video" (with start/end/duration of the full file) blocks appear.
- Click the same source video from the **sidebar** instead — only the source-video timestamps appear (no "This segment" block).
- Click a photo bar from the timeline — no segment block; "Captured" only.
- Stop the server.

- [ ] **Step 3: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat(web): show per-segment timestamps when clicking video_segment bar"
```

---

## Task 7: Render `original → shifted` view when a sync preview is active

When the user has clicked "Update timeline" on the sync queue (`previewIsCurrent === true`) and the file is marked `shifted` in `lastPreviewFiles`, render every timestamp as `original → shifted` and add a "Pending sync" badge in the section header.

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Add a shifted lookup helper**

Add inside the IIFE:

```javascript
function getShiftedFile(path) {
  if (!previewIsCurrent) return null;
  return lastPreviewFiles.find(f => f.path === path && f.shifted) || null;
}
```

- [ ] **Step 2: Render `original → shifted` for timestamps**

Replace the Timestamps block from Task 6 with the version below — it consults `getShiftedFile` and uses helper `tsCell` to render either a plain value or `original → shifted`:

```javascript
const shiftedFile = getShiftedFile(path);
const isShifted = shiftedFile !== null;

function tsCell(originalIso, shiftedIso) {
  if (!originalIso && !shiftedIso) return dash;
  if (!isShifted || !shiftedIso || originalIso === shiftedIso) {
    return `<span class="value">${escapeHtml(formatDateTime(shiftedIso || originalIso))}</span>`;
  }
  return `
    <span class="value details-shift">
      <span class="original">${escapeHtml(formatDateTime(originalIso))}</span>
      <span class="arrow">→</span>
      <span class="shifted">${escapeHtml(formatDateTime(shiftedIso))}</span>
    </span>
  `;
}

const tsSection = document.createElement('div');
tsSection.className = 'details-section';

const isSegmentClick = source === 'timeline' && entry.kind === 'video_segment';
const badge = isShifted
  ? '<span class="shifted-badge">Pending sync</span>'
  : '';

let html = `<h4>Timestamps ${badge}</h4>`;

if (isSegmentClick) {
  // Segment-block values come from the timeline entry, which is already
  // shifted by the preview (the timeline payload is regenerated on
  // "Update timeline").  Show segment values as plain (no arrow) — the
  // arrow form only applies to source-file timestamps.
  const segStart = entry.start_time
    ? `<span class="value">${escapeHtml(formatDateTime(entry.start_time))}</span>`
    : dash;
  const segDur = entry.duration_seconds != null
    ? `<span class="value">${entry.duration_seconds.toFixed(2)}s</span>`
    : dash;
  const trimStart = entry.trim_start != null
    ? `<span class="value">${entry.trim_start.toFixed(2)}s</span>`
    : dash;
  const trimEnd = entry.trim_end != null
    ? `<span class="value">${entry.trim_end.toFixed(2)}s</span>`
    : dash;

  html += '<div style="font-size:0.75rem;color:#888;margin-bottom:4px;">This segment</div>';
  html += `<div class="details-row"><span class="label">Start on timeline</span>${segStart}</div>`;
  html += `<div class="details-row"><span class="label">Trim start</span>${trimStart}</div>`;
  html += `<div class="details-row"><span class="label">Trim end</span>${trimEnd}</div>`;
  html += `<div class="details-row"><span class="label">Segment duration</span>${segDur}</div>`;
  html += '<div style="font-size:0.75rem;color:#888;margin:8px 0 4px;">Source video</div>';
}

if (file.type === 'photo') {
  const shiftedTs = shiftedFile ? shiftedFile.timestamp : null;
  html += `<div class="details-row"><span class="label">Captured</span>${tsCell(file.timestamp, shiftedTs)}</div>`;
} else {
  const shiftedStart = shiftedFile ? shiftedFile.timestamp : null;
  const shiftedEnd = shiftedFile ? shiftedFile.end_timestamp : null;
  const dur = file.duration_seconds != null
    ? `<span class="value">${file.duration_seconds.toFixed(2)}s</span>`
    : dash;
  html += `<div class="details-row"><span class="label">Start</span>${tsCell(file.timestamp, shiftedStart)}</div>`;
  html += `<div class="details-row"><span class="label">End</span>${tsCell(file.end_timestamp, shiftedEnd)}</div>`;
  html += `<div class="details-row"><span class="label">Duration</span>${dur}</div>`;
}

tsSection.innerHTML = html;
body.appendChild(tsSection);
```

- [ ] **Step 3: Manual verification**

```bash
uv run photowalk web /path/to/some/media
```

- Click a file — Timestamps shows the original value (no badge, no arrow).
- Select that file with the checkbox in the sidebar.
- Enter a duration like `+1h`, click "Add to queue", click "Update timeline".
- Click that file again — Timestamps section header now shows a "Pending sync" badge, and each timestamp renders as `<original strikethrough> → <new bold>`.
- Click "Apply" → confirm. After apply, click the file: badge gone, only the new value shown (since `previewIsCurrent` is reset to false and `originalFilesByPath` is replaced with the new on-disk values).
- Click "Clear queue" instead of apply: badge gone, only the original value shown again.
- Stop the server.

- [ ] **Step 4: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat(web): show original → shifted timestamps when sync preview pending"
```

---

## Task 8: Render Camera section (photos only)

The final content section. Show camera_model, shutter_speed, ISO, focal_length. Omit the entire section if all four are null.

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Append the Camera section to `renderDetails`**

After appending `tsSection` in `renderDetails`:

```javascript
if (file.type === 'photo') {
  const fields = [
    ['Camera', file.camera_model],
    ['Shutter', file.shutter_speed],
    ['ISO', file.iso != null ? String(file.iso) : null],
    ['Focal length', file.focal_length],
  ];
  const hasAny = fields.some(([, v]) => v != null && v !== '');
  if (hasAny) {
    const camSection = document.createElement('div');
    camSection.className = 'details-section';
    let camHtml = '<h4>Camera</h4>';
    for (const [label, value] of fields) {
      const cell = (value != null && value !== '')
        ? `<span class="value">${escapeHtml(value)}</span>`
        : '<span class="value" style="color:#666;">—</span>';
      camHtml += `<div class="details-row"><span class="label">${escapeHtml(label)}</span>${cell}</div>`;
    }
    camSection.innerHTML = camHtml;
    body.appendChild(camSection);
  }
}
```

- [ ] **Step 2: Manual verification**

```bash
uv run photowalk web /path/to/photos/with/EXIF
```

- Click a photo with EXIF: Camera section shows Camera, Shutter, ISO, Focal length.
- Click a photo without EXIF (or one missing some fields): missing rows show `—`; if everything is null, the whole section is omitted.
- Click a video: no Camera section.
- Stop the server.

- [ ] **Step 3: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat(web): show Camera section in details panel for photos with EXIF"
```

---

## Task 9: Final manual verification + docs

End-to-end smoke pass against the spec, plus a README / agents.md note.

**Files:**
- Modify: `README.md`
- Modify: `agents.md`

- [ ] **Step 1: Run the full server test suite**

```bash
uv run pytest tests/ -v
```

Expected: all green.

- [ ] **Step 2: End-to-end browser smoke test**

```bash
uv run photowalk web /path/to/folder/with/photos/and/videos
```

Walk through every numbered scenario in the spec's "Testing — Client" list:

1. Sidebar click on a photo with EXIF → File + Timestamps + Camera all render.
2. Sidebar click on a photo without EXIF → Camera section omitted.
3. Sidebar click on a video → File + Timestamps (Start, End, Duration); no Camera.
4. Timeline click on a `video_segment` bar → File + "This segment" + "Source video" + (no Camera).
5. Queue an offset and click "Update timeline"; click an affected file → `original → shifted` and "Pending sync" badge.
6. Click "Apply" → confirm → click the file again → badge gone, only new value, no arrow.
7. Click "Clear" selection → panel returns to "Select a file to see data".
8. Browser console clean (no JS errors).

- [ ] **Step 3: Document in README**

In `README.md`, in the "Web timeline preview" section, add a bullet to the panels list:

```markdown
- **Details** (right) — click any source file or timeline item to inspect timestamps, EXIF (photos), and segment trim info (video segments)
```

- [ ] **Step 4: Document in agents.md**

In `agents.md`, in whatever section lists the web frontend modules, add a one-line note that `src/photowalk/web/file_entry.py` is the single source of truth for the per-file response shape, and that the details panel is implemented in `app.js` via `renderDetails(source, entry)`.

- [ ] **Step 5: Commit docs**

```bash
git add README.md agents.md
git commit -m "docs: note timeline details panel"
```

- [ ] **Step 6: Open a PR (optional, ask user first)**

If the user wants a PR, push the branch and run `gh pr create`. Otherwise, leave the branch local for review.

---

## Self-Review (against spec)

| Spec section | Covered by |
|---|---|
| Layout — 300px right column, header, body, scroll | Task 3 (HTML + CSS) |
| Empty state ("Select a file to see data") | Task 3 markup; Task 4 `clearDetails` |
| File section (Name, Type, Path) | Task 4 |
| Timestamps section — photo (Captured) | Task 5 |
| Timestamps section — video (Start, End, Duration) | Task 5 |
| `video_segment` "This segment" + "Source video" blocks | Task 6 |
| Pending-sync badge + `original → shifted` | Task 7 |
| Camera section, photos-only, omit if all-null | Task 8 |
| Click behavior — sidebar shows source-only view | Task 4 wiring; Task 6 condition (`source === 'timeline'`) |
| Click behavior — timeline segment shows dual view | Task 6 condition |
| Clear button resets panel | Task 4 |
| Server: extend `_metadata_to_file_entry` with new fields | Task 1 (consolidation) + Task 2 (new fields) |
| Server: `build_preview` mirrors new fields | Task 1 (uses shared helper) |
| No new endpoints | Tasks 1+2 (only `/api/files`, preview, apply payloads grow) |
| Server tests: `/api/files` new fields | Task 2 step 5 |
| Server tests: preview new fields | Task 2 step 7 |
| Server tests: apply response new fields | Task 2 step 9 |
| Manual browser tests per spec | Task 9 |
| Snapshot of unshifted file payload as `originalFilesByPath` | Task 4 |
| Snapshot refreshed on apply | Task 4 (`confirmApply` update) |

No unaddressed requirements. No placeholders.
