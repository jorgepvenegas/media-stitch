# Timeline Photo Duration Control — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a photo duration input to the Timeline header with instant preview, carry it through the Update timeline flow, and pre-fill the Render modal.

**Architecture:** The frontend owns `currentImageDuration` state. Changing the input instantly re-renders the SVG client-side. The `POST /api/timeline/preview` request includes the duration; the server falls back to `app.state.image_duration` when absent. The Render modal reads from the same frontend state.

**Tech Stack:** FastAPI, Pydantic, vanilla JS, pytest

---

### Task 1: Add `image_duration` to `PreviewRequest`

**Files:**
- Modify: `src/photowalk/web/sync_models.py`

- [ ] **Step 1: Add the optional field**

```python
class PreviewRequest(BaseModel):
    offsets: list[OffsetEntry]
    image_duration: float | None = None
```

- [ ] **Step 2: Commit**

```bash
git add src/photowalk/web/sync_models.py
git commit -m "feat: add image_duration to PreviewRequest"
```

---

### Task 2: Use request-provided duration in `api_timeline_preview`

**Files:**
- Modify: `src/photowalk/web/server.py`

- [ ] **Step 1: Update the endpoint body**

Find this block in `api_timeline_preview`:

```python
    @app.post("/api/timeline/preview")
    async def api_timeline_preview(req: PreviewRequest):
        return build_preview(
            app.state.metadata_pairs,
            req.offsets,
            image_duration=app.state.image_duration,
        )
```

Replace with:

```python
    @app.post("/api/timeline/preview")
    async def api_timeline_preview(req: PreviewRequest):
        image_duration = req.image_duration if req.image_duration is not None else app.state.image_duration
        return build_preview(
            app.state.metadata_pairs,
            req.offsets,
            image_duration=image_duration,
        )
```

- [ ] **Step 2: Commit**

```bash
git add src/photowalk/web/server.py
git commit -m "feat: use request-provided image_duration in timeline preview"
```

---

### Task 3: Add backend tests for `image_duration` in preview

**Files:**
- Modify: `tests/test_cli_sync.py`

- [ ] **Step 1: Write the failing test for explicit duration**

Find the existing preview test (around `test_web_preview_with_offset`). After it, add:

```python
def test_web_preview_with_custom_image_duration(client):
    """Preview request can override the default image_duration."""
    res = client.post("/api/timeline/preview", json={
        "offsets": [],
        "image_duration": 7.5,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["settings"]["image_duration"] == 7.5
```

- [ ] **Step 2: Write the failing test for fallback behavior**

```python
def test_web_preview_fallback_image_duration(client):
    """Preview without image_duration falls back to the app default."""
    res = client.post("/api/timeline/preview", json={
        "offsets": [],
    })
    assert res.status_code == 200
    data = res.json()
    assert data["settings"]["image_duration"] == 3.5
```

- [ ] **Step 3: Run tests to verify they pass**

```bash
uv run pytest tests/test_cli_sync.py::test_web_preview_with_custom_image_duration tests/test_cli_sync.py::test_web_preview_fallback_image_duration -v
```

Expected: both PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_cli_sync.py
git commit -m "test: verify custom and fallback image_duration in preview"
```

---

### Task 4: Add duration input to the Timeline header in HTML

**Files:**
- Modify: `src/photowalk/web/assets/index.html`

- [ ] **Step 1: Add the control after the Timeline heading**

Find:

```html
    <div id="timeline">
      <h3>Timeline</h3>
      <div id="timeline-scroll">
```

Replace with:

```html
    <div id="timeline">
      <div class="timeline-header">
        <h3>Timeline</h3>
        <div class="timeline-duration-control">
          <label for="timeline-image-duration">Photo duration:</label>
          <input type="number" id="timeline-image-duration" value="3.5" step="0.1" min="0.1">
          <span>s</span>
        </div>
      </div>
      <div id="timeline-scroll">
```

- [ ] **Step 2: Commit**

```bash
git add src/photowalk/web/assets/index.html
git commit -m "feat: add photo duration input to timeline header"
```

---

### Task 5: Add CSS for the timeline header and duration control

**Files:**
- Modify: `src/photowalk/web/assets/style.css`

- [ ] **Step 1: Append the new styles at the end of the file**

```css
.timeline-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 8px;
}

.timeline-header h3 {
  margin: 0;
}

.timeline-duration-control {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #ccc;
}

.timeline-duration-control label {
  cursor: pointer;
}

.timeline-duration-control input {
  width: 56px;
  padding: 2px 6px;
  font-size: 13px;
  background: #2a2a2a;
  border: 1px solid #444;
  border-radius: 4px;
  color: #eee;
  text-align: right;
}

.timeline-duration-control input:focus {
  outline: none;
  border-color: #4dabf7;
}
```

- [ ] **Step 2: Commit**

```bash
git add src/photowalk/web/assets/style.css
git commit -m "style: timeline header and duration control layout"
```

---

### Task 6: Wire up frontend state and instant re-render

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Add `currentImageDuration` state and initialize it**

After the existing state declarations at the top of the IIFE:

```javascript
  let currentImageDuration = timelineData.settings.image_duration || 3.5;
```

After `renderTimelineFromData(timelineData);` in the initial load block, add:

```javascript
  document.getElementById('timeline-image-duration').value = String(currentImageDuration);
```

- [ ] **Step 2: Wire the duration input for instant re-render**

After `bindSyncPanel();` in the initial load block, add:

```javascript
  document.getElementById('timeline-image-duration').addEventListener('change', (e) => {
    let val = parseFloat(e.target.value);
    if (Number.isNaN(val) || val < 0.1) {
      val = 0.1;
    }
    currentImageDuration = val;
    e.target.value = String(val);
    const entries = app.state?.timeline_response?.entries;
    if (entries && entries.length > 0) {
      renderTimeline(entries, currentImageDuration);
    }
  });
```

Wait — `app.state` doesn't exist on the client. The timeline entries are already in `timelineData.entries`. After `updateTimeline()` runs, the latest entries are available via `allFiles` indirectly, but we need the entries themselves. Let's track `currentTimelineEntries` as a new state variable.

Add to state declarations:

```javascript
  let currentTimelineEntries = timelineData.entries || [];
```

Update the change handler:

```javascript
  document.getElementById('timeline-image-duration').addEventListener('change', (e) => {
    let val = parseFloat(e.target.value);
    if (Number.isNaN(val) || val < 0.1) {
      val = 0.1;
    }
    currentImageDuration = val;
    e.target.value = String(val);
    if (currentTimelineEntries.length > 0) {
      renderTimeline(currentTimelineEntries, currentImageDuration);
    }
  });
```

In `renderTimelineFromData`, update `currentTimelineEntries`:

```javascript
  function renderTimelineFromData(td) {
    const entries = td.entries;
    currentTimelineEntries = entries;
    if (entries.length > 0) {
      renderTimeline(entries, td.settings.image_duration);
    } else {
      document.getElementById('timeline-scroll').innerHTML =
        '<div style="padding:20px;color:#666;">No timeline entries.</div>';
    }
  }
```

- [ ] **Step 3: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat: wire timeline duration input with instant re-render"
```

---

### Task 7: Send `image_duration` in preview request and sync state after response

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Update `updateTimeline` to include the duration**

Find the `updateTimeline` function and replace its body with:

```javascript
  async function updateTimeline() {
    let res;
    try {
      res = await fetch('/api/timeline/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          offsets: pendingStack,
          image_duration: currentImageDuration,
        }),
      }).then(r => r.json());
    } catch (e) {
      showToast('Could not update timeline', { error: true });
      return;
    }

    allFiles = res.files;
    lastPreviewFiles = res.files;
    renderSidebar(allFiles);
    renderTimelineFromData({ entries: res.entries, settings: res.settings });
    if (res.settings && res.settings.image_duration != null) {
      currentImageDuration = res.settings.image_duration;
      document.getElementById('timeline-image-duration').value = String(currentImageDuration);
    }
    previewIsCurrent = true;
    updateButtons();
  }
```

- [ ] **Step 2: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat: send image_duration with preview request and sync after response"
```

---

### Task 8: Pre-fill Render modal from `currentImageDuration`

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Update `openRenderModal`**

Find:

```javascript
    document.getElementById('render-image-duration').value = String(timelineData.settings.image_duration || 3.5);
```

Replace with:

```javascript
    document.getElementById('render-image-duration').value = String(currentImageDuration);
```

- [ ] **Step 2: Sync duration after Apply in `confirmApply`**

Find this block near the end of `confirmApply`:

```javascript
    renderSidebar(allFiles);
    renderTimelineFromData(res.timeline);
```

After `renderTimelineFromData(res.timeline);`, add:

```javascript
    if (res.timeline && res.timeline.settings && res.timeline.settings.image_duration != null) {
      currentImageDuration = res.timeline.settings.image_duration;
      document.getElementById('timeline-image-duration').value = String(currentImageDuration);
    }
```

- [ ] **Step 3: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat: render modal and apply flow use currentImageDuration"
```

---

### Task 9: Run all tests and verify

- [ ] **Step 1: Run the full test suite**

```bash
uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Run the specific new tests**

```bash
uv run pytest tests/test_cli_sync.py::test_web_preview_with_custom_image_duration tests/test_cli_sync.py::test_web_preview_fallback_image_duration -v
```

Expected: both PASS.

- [ ] **Step 3: Commit any fixes if needed**

If tests fail, fix and commit before proceeding.

---

### Task 10: Final review and wrap-up

- [ ] **Step 1: Review all changed files**

```bash
git diff --stat HEAD~9
```

Expected changed files:
- `src/photowalk/web/sync_models.py`
- `src/photowalk/web/server.py`
- `src/photowalk/web/assets/index.html`
- `src/photowalk/web/assets/style.css`
- `src/photowalk/web/assets/app.js`
- `tests/test_cli_sync.py`

- [ ] **Step 2: Final commit if everything is clean**

```bash
git status
# should show nothing pending
git log --oneline -10
```

---

## Self-Review Checklist

**1. Spec coverage:**
- ✅ Timeline header input → Task 4, Task 6
- ✅ Instant SVG re-render on input change → Task 6
- ✅ Send `image_duration` with `POST /api/timeline/preview` → Task 7
- ✅ Server fallback when absent → Task 2, Task 3
- ✅ Render modal pre-filled from same state → Task 8
- ✅ Apply flow syncs duration → Task 8
- ✅ Edge cases (NaN, zero, negative) → Task 6

**2. Placeholder scan:** No TBD, TODO, or vague instructions found.

**3. Type consistency:**
- `PreviewRequest.image_duration: float | None = None` matches server-side `req.image_duration is not None` check.
- Frontend `currentImageDuration` is always a number; input value is stringified with `String()`.
