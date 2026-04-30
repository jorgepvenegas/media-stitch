# Render Ratio Presets — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the free-text resolution input in the Render modal with aspect-ratio preset buttons (16:9, 9:16, 4:3, 3:4).

**Architecture:** Pure UI change. The existing `StitchRequest.format` field already accepts `"1920x1080"` etc. Frontend tracks `selectedRenderFormat` state and sends it to the same `/api/stitch` endpoint. No backend model changes.

**Tech Stack:** Vanilla JS, HTML, CSS, FastAPI, pytest

---

### Task 1: Replace resolution input with ratio buttons in HTML

**Files:**
- Modify: `src/photowalk/web/assets/index.html`

- [ ] **Step 1: Replace the resolution field**

Find:

```html
        <div class="render-field">
          <label>Resolution (optional)</label>
          <input type="text" id="render-format" placeholder="1920x1080">
        </div>
```

Replace with:

```html
        <div class="render-field">
          <label>Aspect ratio</label>
          <div class="ratio-buttons">
            <button type="button" class="ratio-btn active" data-format="1920x1080">16:9</button>
            <button type="button" class="ratio-btn" data-format="1080x1920">9:16</button>
            <button type="button" class="ratio-btn" data-format="1920x1440">4:3</button>
            <button type="button" class="ratio-btn" data-format="1080x1440">3:4</button>
          </div>
          <div class="ratio-resolution" id="ratio-resolution">1920 × 1080</div>
        </div>
```

- [ ] **Step 2: Commit**

```bash
git add src/photowalk/web/assets/index.html
git commit -m "feat: replace resolution input with ratio preset buttons"
```

---

### Task 2: Add ratio button styles

**Files:**
- Modify: `src/photowalk/web/assets/style.css`

- [ ] **Step 1: Append the new styles**

Add at the end of `style.css`:

```css
.ratio-buttons {
  display: flex;
  gap: 8px;
}

.ratio-btn {
  flex: 1;
  padding: 8px 0;
  background: #2a2a2a;
  border: 1px solid #444;
  border-radius: 4px;
  color: #ccc;
  cursor: pointer;
  font-size: 13px;
}

.ratio-btn:hover {
  border-color: #666;
}

.ratio-btn.active {
  background: #4a90d9;
  border-color: #4a90d9;
  color: #fff;
}

.ratio-resolution {
  margin-top: 6px;
  font-size: 12px;
  color: #888;
  text-align: center;
}
```

- [ ] **Step 2: Commit**

```bash
git add src/photowalk/web/assets/style.css
git commit -m "style: ratio preset button styles"
```

---

### Task 3: Add `selectedRenderFormat` state and wire ratio buttons

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Add the state variable**

After the existing state declarations (after `let currentTimelineEntries = [];`):

```javascript
  let selectedRenderFormat = '1920x1080';
```

- [ ] **Step 2: Wire up the ratio button click handlers**

After the existing `document.getElementById('timeline-image-duration').addEventListener('change', ...)` block, add:

```javascript
  document.querySelectorAll('.ratio-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.ratio-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedRenderFormat = btn.dataset.format;
      document.getElementById('ratio-resolution').textContent = selectedRenderFormat.replace('x', ' \u00d7 ');
    });
  });
```

- [ ] **Step 3: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat: add selectedRenderFormat state and wire ratio buttons"
```

---

### Task 4: Reset ratio buttons when opening the Render modal

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Update `openRenderModal`**

Find:

```javascript
    document.getElementById('render-format').value = '';
```

Replace with:

```javascript
    selectedRenderFormat = '1920x1080';
    document.querySelectorAll('.ratio-btn').forEach(b => b.classList.remove('active'));
    document.querySelector('.ratio-btn[data-format="1920x1080"]').classList.add('active');
    document.getElementById('ratio-resolution').textContent = '1920 \u00d7 1080';
```

- [ ] **Step 2: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat: reset ratio buttons to 16:9 default when opening render modal"
```

---

### Task 5: Use `selectedRenderFormat` in `startRender`

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Replace the format read from DOM**

Find:

```javascript
    const format = document.getElementById('render-format').value.trim() || null;
```

Replace with:

```javascript
    const format = selectedRenderFormat;
```

- [ ] **Step 2: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat: send selectedRenderFormat to stitch endpoint"
```

---

### Task 6: Add backend test for portrait format

**Files:**
- Modify: `tests/test_web_stitch.py`

- [ ] **Step 1: Write the test**

After `test_stitch_request_format_ok`, add:

```python
def test_stitch_request_portrait_format_ok():
    req = StitchRequest(output="/tmp/out.mp4", format="1080x1920")
    assert req.format == "1080x1920"
```

- [ ] **Step 2: Run the test to verify it passes**

```bash
uv run pytest tests/test_web_stitch.py::test_stitch_request_portrait_format_ok -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_web_stitch.py
git commit -m "test: verify portrait format accepted by StitchRequest"
```

---

### Task 7: Run all tests and verify

- [ ] **Step 1: Run the full test suite**

```bash
uv run pytest -q --ignore=tests/test_stitcher.py
```

Expected: all tests pass (216+).

- [ ] **Step 2: Run all web stitch tests**

```bash
uv run pytest tests/test_web_stitch.py -v
```

Expected: all PASS.

- [ ] **Step 3: Commit any fixes if needed**

---

### Task 8: Final review

- [ ] **Step 1: Review changed files**

```bash
git diff --stat HEAD~8
```

Expected changed files:
- `src/photowalk/web/assets/index.html`
- `src/photowalk/web/assets/style.css`
- `src/photowalk/web/assets/app.js`
- `tests/test_web_stitch.py`

- [ ] **Step 2: Check git status**

```bash
git status
```

Expected: clean working tree.

---

## Self-Review Checklist

**1. Spec coverage:**
- ✅ Replace resolution input with ratio buttons → Task 1
- ✅ Add ratio button styles → Task 2
- ✅ Track selected format in JS state → Task 3
- ✅ Reset to default when opening modal → Task 4
- ✅ Send selected format to server → Task 5
- ✅ Backend test for portrait format → Task 6

**2. Placeholder scan:** No TBD, TODO, or vague instructions found.

**3. Type consistency:**
- `selectedRenderFormat` is always a string like `"1920x1080"` — matches `StitchRequest.format` validator expectations.
- The `\u00d7` (×) character is used consistently in resolution display strings.
