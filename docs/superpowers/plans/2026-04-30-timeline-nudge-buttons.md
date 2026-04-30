# Timeline Nudge Buttons — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `←` / `→` buttons to the Details panel that shift the currently-selected timeline item by ±1 second per click via the existing offset queue, with a debounced preview.

**Architecture:** Pure frontend change in `src/photowalk/web/assets/`. Each click coalesces into the `pendingStack` (the same queue used by the Sync panel) as a `{kind: 'duration', origin: 'nudge'}` entry, then triggers a 150 ms-debounced call to the existing `/api/timeline/preview` endpoint. Selection state is tracked at the module level so it survives the timeline re-render that follows each preview.

**Tech Stack:** Vanilla JS (IIFE in `app.js`), HTML, CSS. No backend changes. No automated frontend tests (none exist today).

---

### Task 1: Add CSS for the Adjust section

**Files:**
- Modify: `src/photowalk/web/assets/style.css`

- [ ] **Step 1: Append the Adjust section styles**

Add at the end of `src/photowalk/web/assets/style.css`:

```css
/* Details panel — Adjust section */
.adjust-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.adjust-btn {
  background: #2a3a5a;
  color: #e0e0e0;
  border: 1px solid #444;
  border-radius: 3px;
  padding: 4px 12px;
  cursor: pointer;
  font-size: 1rem;
  font-family: inherit;
  min-width: 36px;
}

.adjust-btn:hover {
  background: #3a4a6a;
}

.adjust-total {
  color: #d9a04a;
  font-size: 0.9rem;
  font-family: monospace;
  min-width: 36px;
  text-align: center;
}
```

- [ ] **Step 2: Commit**

```bash
git add src/photowalk/web/assets/style.css
git commit -m "style: add adjust-section styles for timeline nudge buttons"
```

---

### Task 2: Add module state and helper functions

This task adds new state variables and pure helper functions. Nothing is wired up yet — the helpers have no callers until later tasks.

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Add module-level state variables**

Find this block near the top of the IIFE:

```javascript
  let allFiles = [];                // most recent files response
  let lastPreviewFiles = [];        // files from last preview, for diff modal
  let previewIsCurrent = false;     // false if stack changed since last preview
  let originalFilesByPath = {};       // path -> full file record at app load (or after apply)
  let renderPollInterval = null;
  let currentImageDuration = 3.5;
  let currentTimelineEntries = [];
  let selectedRenderFormat = '1920x1080';
```

Append three new state variables to the end of that block so it reads:

```javascript
  let allFiles = [];                // most recent files response
  let lastPreviewFiles = [];        // files from last preview, for diff modal
  let previewIsCurrent = false;     // false if stack changed since last preview
  let originalFilesByPath = {};       // path -> full file record at app load (or after apply)
  let renderPollInterval = null;
  let currentImageDuration = 3.5;
  let currentTimelineEntries = [];
  let selectedRenderFormat = '1920x1080';
  let selectedPath = null;          // path of the currently selected file
  let selectedSource = null;        // 'timeline' or 'sidebar' or null
  let nudgeDebounceTimer = null;
```

- [ ] **Step 2: Add the helper functions**

Insert these four helpers immediately above the existing `function renderDetails(source, entry) {` line:

```javascript
  function formatSignedSeconds(seconds) {
    const sign = seconds >= 0 ? '+' : '-';
    return `${sign}${Math.abs(seconds)}s`;
  }

  function findNudgeEntry(path) {
    const top = pendingStack[pendingStack.length - 1];
    if (top
        && top.target_paths.length === 1
        && top.target_paths[0] === path
        && top.source.kind === 'duration'
        && top.source.origin === 'nudge') {
      return top;
    }
    return null;
  }

  function scheduleDebouncedPreview() {
    if (nudgeDebounceTimer !== null) clearTimeout(nudgeDebounceTimer);
    nudgeDebounceTimer = setTimeout(() => {
      nudgeDebounceTimer = null;
      updateTimeline();
    }, 150);
  }

  function mutateNudge(path, delta) {
    const top = findNudgeEntry(path);
    if (top) {
      top.delta_seconds += delta;
      if (top.delta_seconds === 0) {
        const idx = pendingStack.indexOf(top);
        if (idx !== -1) pendingStack.splice(idx, 1);
      } else {
        top.source.text = formatSignedSeconds(top.delta_seconds);
      }
    } else {
      pendingStack.push({
        id: crypto.randomUUID(),
        delta_seconds: delta,
        source: { kind: 'duration', text: formatSignedSeconds(delta), origin: 'nudge' },
        target_paths: [path],
      });
    }

    previewIsCurrent = false;
    updateButtons();
    renderQueue();

    const nudge = findNudgeEntry(path);
    const label = document.querySelector('.adjust-total');
    if (label) {
      label.textContent = nudge ? formatSignedSeconds(nudge.delta_seconds) : '';
    }

    scheduleDebouncedPreview();
  }
```

- [ ] **Step 3: Verify the file still parses**

Run:

```bash
node --check src/photowalk/web/assets/app.js
```

Expected: no output (success). If `node` is not installed, open the file in a text editor and visually confirm the new code is well-formed (matching braces).

- [ ] **Step 4: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat: add nudge state and helpers for timeline adjustments"
```

---

### Task 3: Track selection state in `selectFile`, `clearDetails`, and `confirmApply`

This task records `selectedPath` and `selectedSource` when the user clicks an item, and clears them when the selection is wiped. No visible change yet.

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Update `selectFile` to record selection state**

Find:

```javascript
  function selectFile(path, type, el) {
    document.querySelectorAll('.sidebar-item.selected').forEach(e => e.classList.remove('selected'));
    document.querySelectorAll('.timeline-bar.selected').forEach(e => e.classList.remove('selected'));
    el.classList.add('selected');
    if (el.classList.contains('sidebar-item')) {
      document.querySelectorAll(`.timeline-bar[data-path="${CSS.escape(path)}"]`).forEach(b => b.classList.add('selected'));
    } else {
      document.querySelectorAll(`.sidebar-item[data-path="${CSS.escape(path)}"]`).forEach(b => b.classList.add('selected'));
    }
```

Replace with:

```javascript
  function selectFile(path, type, el) {
    document.querySelectorAll('.sidebar-item.selected').forEach(e => e.classList.remove('selected'));
    document.querySelectorAll('.timeline-bar.selected').forEach(e => e.classList.remove('selected'));
    el.classList.add('selected');
    selectedPath = path;
    selectedSource = el.classList.contains('sidebar-item') ? 'sidebar' : 'timeline';
    if (el.classList.contains('sidebar-item')) {
      document.querySelectorAll(`.timeline-bar[data-path="${CSS.escape(path)}"]`).forEach(b => b.classList.add('selected'));
    } else {
      document.querySelectorAll(`.sidebar-item[data-path="${CSS.escape(path)}"]`).forEach(b => b.classList.add('selected'));
    }
```

- [ ] **Step 2: Update `clearDetails` to reset selection state**

Find:

```javascript
  function clearDetails() {
    const body = document.getElementById('details-panel-body');
    body.innerHTML = '<div id="details-empty">Select a file to see data</div>';
  }
```

Replace with:

```javascript
  function clearDetails() {
    selectedPath = null;
    selectedSource = null;
    const body = document.getElementById('details-panel-body');
    body.innerHTML = '<div id="details-empty">Select a file to see data</div>';
  }
```

- [ ] **Step 3: Clear selection state at the start of `confirmApply`'s post-success block**

In `confirmApply`, find:

```javascript
    pendingStack.length = 0;
    selection.clear();
    previewIsCurrent = false;
    renderQueue();
    renderSidebar(allFiles);
    renderTimelineFromData(res.timeline);
```

Replace with:

```javascript
    pendingStack.length = 0;
    selection.clear();
    previewIsCurrent = false;
    selectedPath = null;
    selectedSource = null;
    renderQueue();
    renderSidebar(allFiles);
    renderTimelineFromData(res.timeline);
```

This prevents the re-apply logic added in Task 4 from briefly restoring a stale selection during apply.

- [ ] **Step 4: Verify the file still parses**

Run:

```bash
node --check src/photowalk/web/assets/app.js
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat: track selected file path and source across renders"
```

---

### Task 4: Render the Adjust section and re-apply selection after timeline re-render

This task makes the feature visible. It (a) renders the Adjust section in the Details panel when `source === 'timeline'`, wires the buttons to `mutateNudge`, and (b) re-applies the timeline selection at the end of `renderTimeline` so the section survives the post-preview re-render.

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Render the Adjust section in `renderDetails`**

In `renderDetails`, find:

```javascript
    const filename = path.split('/').pop();

    const fileSection = document.createElement('div');
    fileSection.className = 'details-section';
    fileSection.innerHTML = `
    <h4>File</h4>
```

Insert the Adjust section render BEFORE the `const fileSection` block, so the result reads:

```javascript
    const filename = path.split('/').pop();

    if (source === 'timeline') {
      const adjustSection = document.createElement('div');
      adjustSection.className = 'details-section';
      const nudge = findNudgeEntry(path);
      const totalText = nudge ? formatSignedSeconds(nudge.delta_seconds) : '';
      adjustSection.innerHTML = `
        <h4>Adjust</h4>
        <div class="adjust-controls">
          <button type="button" class="adjust-btn" data-delta="-1" aria-label="Shift earlier 1 second">←</button>
          <span class="adjust-total">${escapeHtml(totalText)}</span>
          <button type="button" class="adjust-btn" data-delta="1" aria-label="Shift later 1 second">→</button>
        </div>
      `;
      adjustSection.querySelectorAll('.adjust-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const delta = parseInt(btn.dataset.delta, 10);
          mutateNudge(path, delta);
        });
      });
      body.appendChild(adjustSection);
    }

    const fileSection = document.createElement('div');
    fileSection.className = 'details-section';
    fileSection.innerHTML = `
    <h4>File</h4>
```

- [ ] **Step 2: Re-apply selection at the end of `renderTimeline`**

Find the end of `renderTimeline`:

```javascript
    renderAxis(positions, scale, padding, gap);
  }
```

Replace with:

```javascript
    renderAxis(positions, scale, padding, gap);

    if (selectedPath && selectedSource === 'timeline') {
      const bar = document.querySelector(
        `.timeline-bar[data-path="${CSS.escape(selectedPath)}"]`,
      );
      if (bar) {
        bar.classList.add('selected');
        const matchingEntry = entries.find(e => e.source_path === selectedPath);
        if (matchingEntry) {
          renderDetails('timeline', matchingEntry);
        }
      } else {
        clearDetails();
      }
    }
  }
```

- [ ] **Step 3: Verify the file still parses**

Run:

```bash
node --check src/photowalk/web/assets/app.js
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat: render adjust section and persist timeline selection across re-render"
```

---

### Task 5: Manual verification in the browser

Frontend has no automated test harness; the feature is verified by exercising the UI.

- [ ] **Step 1: Start the web server**

Run, in a directory containing at least one photo and one video with timestamps:

```bash
uv run photowalk web .
```

Expected: server logs a URL like `http://127.0.0.1:8765`. Open it in a browser. The console should be free of errors.

- [ ] **Step 2: Verify the empty state**

With nothing selected, the Details panel should show "Select a file to see data". No Adjust section. No buttons.

- [ ] **Step 3: Verify the section appears only on timeline selection**

Click a sidebar entry. Confirm the Details panel populates but does **not** show an Adjust section.

Click a bar on the timeline. Confirm the Details panel now shows the Adjust section at the top, with `←` and `→` buttons and an empty running-total label between them.

- [ ] **Step 4: Verify a single nudge**

With a timeline bar selected, click `←` once. Within ~150 ms:

- The running-total label should read `-1s`.
- A new row should appear in the Sync panel queue: `1. -1s → <filename>`.
- The timeline should re-render. The Adjust section should still be visible (selection persisted).
- The "Apply" button should be enabled.

- [ ] **Step 5: Verify coalescing and zero-pop**

Click `←` again. Confirm:
- The label reads `-2s`.
- The queue still has exactly one row, now reading `-2s → <filename>`.

Click `→` twice. After the second click:
- The label is empty.
- The queue row disappears entirely.
- The "Apply" button is disabled (`previewIsCurrent` becomes `true` after the preview but the queue is empty so apply is disabled per existing logic).

- [ ] **Step 6: Verify debounce**

Open the browser DevTools Network tab. With a timeline bar selected, click `←` 5 times within 150 ms (a quick burst).

Expected: exactly **one** POST to `/api/timeline/preview` after the burst settles. The label updates immediately on each click; only the network call is debounced.

- [ ] **Step 7: Verify video segment behavior**

If your test directory produces multiple `video_segment` entries from the same source video (i.e. photos interleave with a single long video), select one segment bar and click `←`. Confirm:
- All sibling segments derived from the same source video also shift on the timeline.
- The Adjust section's running-total reads `-1s`.

This matches the spec's chosen behavior: shifting a segment shifts the source video's timestamp, which moves all derived segments.

- [ ] **Step 8: Verify Apply consumes the nudge**

With a non-zero nudge pending, click "Apply" and confirm in the modal. After the modal closes:
- The selected file's timestamp on disk has shifted (verify with `exiftool` for photos or `ffprobe` for videos if convenient).
- The Details panel returns to the empty state.
- Re-clicking the same timeline bar shows the Adjust section with an empty running-total label (the queue was consumed).

- [ ] **Step 9: If anything failed, fix and re-verify**

Common issues to watch for:
- Buttons render but clicking does nothing → check that the click handlers in Task 4, Step 1 reference `mutateNudge` correctly.
- Section disappears after preview → check that Task 4, Step 2's re-apply block is present.
- Multiple network calls per click → check the debounce timer in Task 2 (`scheduleDebouncedPreview`).

---

### Task 6: Final review

- [ ] **Step 1: Review changed files**

```bash
git diff --stat HEAD~4
```

Expected changed files:
- `src/photowalk/web/assets/style.css`
- `src/photowalk/web/assets/app.js`

(`index.html` is unchanged.)

- [ ] **Step 2: Run the existing backend test suite to confirm no regressions**

```bash
uv run pytest -q --ignore=tests/test_stitcher.py
```

Expected: all tests pass.

- [ ] **Step 3: Check git status**

```bash
git status
```

Expected: clean working tree.

---

## Self-Review Checklist

**1. Spec coverage:**
- Adjust section in Details panel, top, timeline-only → Task 4 (`source === 'timeline'` gate, prepended before `fileSection`)
- Two buttons (`←`, `→`) and running-total label → Task 4
- Buttons hidden when nothing selected → falls out of the `if (!file)` early return in `renderDetails` (existing) plus the timeline-only gate
- Click goes through `pendingStack` with `origin: 'nudge'` → Task 2 (`mutateNudge`)
- Last-entry coalesce, pop on zero → Task 2 (`mutateNudge`)
- 150 ms debounce on preview → Task 2 (`scheduleDebouncedPreview`)
- `previewIsCurrent` set to false on each click → Task 2 (`mutateNudge`)
- Selection persistence across re-render → Task 4, Step 2
- Selection cleared on apply → Task 3, Step 3
- Photos and videos same behavior → no special-casing in `mutateNudge`; falls out for free
- Video segments shift the source → existing offset model handles this; `mutateNudge` writes a normal duration entry
- No backend changes → confirmed; only `app.js` and `style.css` touched

**2. Placeholder scan:** No TBD, TODO, or vague instructions. Every code step has the actual code.

**3. Type consistency:**
- `pendingStack` entry shape (`id`, `delta_seconds`, `source`, `target_paths`) matches what `addToQueue` produces and what `/api/timeline/preview` expects. The added `source.origin` field is ignored by the existing renderer and by the server (it only inspects `kind`, `text`, `wrong`, `correct`).
- `selectedSource` is one of `'timeline'`, `'sidebar'`, or `null` — used only as a string equality check in Task 4, Step 2.
- `formatSignedSeconds` is called with non-zero integers only (callers guard against zero), so the `+0s` edge case never appears in the UI.
- `findNudgeEntry` returns either the top stack entry or `null` — no other shape.
