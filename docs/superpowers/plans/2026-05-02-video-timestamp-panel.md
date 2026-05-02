# Video Timestamp Preview Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a timestamp panel next to the video player that shows the actual timestamp when paused, with a copy button for the ISO string.

**Architecture:** Modify the existing `#preview` container to be a flex row with video on left and a new timestamp panel on right. The panel updates on video `pause`/`play` events. Timestamp is calculated as `file.timestamp + (currentTime - trimStart)`.

**Tech Stack:** Vanilla JS (existing app.js), HTML, CSS

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/photowalk/web/assets/index.html` | Add `#timestamp-panel` div inside `#preview` |
| `src/photowalk/web/assets/style.css` | Add styles for `#preview` flex layout and `#timestamp-panel` |
| `src/photowalk/web/assets/app.js` | Add panel rendering, event listeners, copy logic |

---

## Task 1: Add timestamp panel HTML

**Files:** Modify: `src/photowalk/web/assets/index.html`

- [ ] **Step 1: Add timestamp panel div inside `#preview`**

Find the `#preview` div (lines ~8-12) and add the panel:

```html
  <div id="preview">
    <video id="preview-video" controls style="display:none;"></video>
    <img id="preview-image" style="display:none;">
    <div id="preview-placeholder">Select an item to preview</div>
    <div id="timestamp-panel">
      <div id="timestamp-content">
        <div id="timestamp-label">Select a video to see timestamp</div>
      </div>
    </div>
  </div>
```

- [ ] **Step 2: Commit**

```bash
git add src/photowalk/web/assets/index.html
git commit -m "feat(web): add timestamp panel HTML structure"
```

---

## Task 2: Add CSS styles

**Files:** Modify: `src/photowalk/web/assets/style.css`

- [ ] **Step 1: Update `#preview` to flex row**

Find the existing `#preview` rule (around line 14) and change it:

```css
/* Preview player */
#preview {
  height: 40vh;
  background: #0f0f1a;
  display: flex;
  flex-direction: row;
  border-bottom: 1px solid #333;
}
```

- [ ] **Step 2: Add video container to take remaining width**

Add after `#preview-placeholder`:

```css
#preview-video, #preview-image {
  flex: 1;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
```

Remove the duplicate `max-width/max-height` from `#preview video, #preview img` if present.

- [ ] **Step 3: Add timestamp panel styles**

Add at end of file:

```css
/* Timestamp panel */
#timestamp-panel {
  width: 220px;
  min-width: 220px;
  background: #16213e;
  border-left: 1px solid #333;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

#timestamp-content {
  text-align: center;
  width: 100%;
}

#timestamp-label {
  color: #666;
  font-size: 0.9rem;
  font-style: italic;
}

#timestamp-display {
  display: none;
}

#timestamp-display.visible {
  display: block;
}

.timestamp-section-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #888;
  margin-bottom: 4px;
}

.timestamp-divider {
  border: none;
  border-top: 1px solid #333;
  margin: 8px 0;
}

.timestamp-human {
  font-size: 1rem;
  color: #e0e0e0;
  margin-bottom: 4px;
}

.timestamp-iso {
  font-size: 0.85rem;
  color: #888;
  font-family: monospace;
  margin-bottom: 12px;
}

#timestamp-copy-btn {
  background: #2a3a5a;
  color: #e0e0e0;
  border: 1px solid #444;
  padding: 6px 14px;
  cursor: pointer;
  font-size: 0.85rem;
  width: 100%;
}

#timestamp-copy-btn:hover {
  background: #3a4a6a;
}

#timestamp-copy-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

#timestamp-placeholder {
  color: #666;
  font-style: italic;
  font-size: 0.9rem;
}
```

- [ ] **Step 4: Commit**

```bash
git add src/photowalk/web/assets/style.css
git commit -m "feat(web): add timestamp panel styles"
```

---

## Task 3: Implement panel logic in app.js

**Files:** Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Add timestamp panel HTML template and state variables**

Find the state variables section (around line 5) and add:

```javascript
let selectedSource = null;        // 'timeline' or 'sidebar' or null
let currentVideoFile = null;     // currently selected video file record
let videoPaused = true;          // track playback state
```

Add this HTML template at the top (inside the IIFE, after the `const video` line around line 22):

```javascript
  const timestampPanel = document.getElementById('timestamp-panel');

  function renderTimestampPanel() {
    const label = document.getElementById('timestamp-label');
    const display = document.getElementById('timestamp-display');
    const placeholder = document.getElementById('timestamp-placeholder');
    const copyBtn = document.getElementById('timestamp-copy-btn');

    if (!selectedPath || !currentVideoFile) {
      // No selection
      label.style.display = '';
      label.textContent = 'Select a video to see timestamp';
      display.classList.remove('visible');
      return;
    }

    if (currentVideoFile.type !== 'video') {
      // Photo selected
      label.style.display = '';
      label.textContent = 'No playback for photos';
      display.classList.remove('visible');
      return;
    }

    if (!videoPaused) {
      // Video playing
      label.style.display = '';
      label.textContent = 'Playing...';
      display.classList.remove('visible');
      return;
    }

    // Video paused - show timestamp
    label.style.display = 'none';
    display.classList.add('visible');

    // Calculate actual timestamp
    const trimStart = video.dataset.trimStart ? parseFloat(video.dataset.trimStart) : 0;
    const offsetSeconds = video.currentTime - trimStart;
    const tsMs = new Date(currentVideoFile.timestamp).getTime() + (offsetSeconds * 1000);
    const tsDate = new Date(tsMs);

    // Format timestamps
    const human = tsDate.toLocaleString();
    const iso = tsDate.toISOString();

    document.getElementById('timestamp-human').textContent = human;
    document.getElementById('timestamp-iso').textContent = iso;

    // Wire copy button (only once)
    if (!copyBtn.dataset.wired) {
      copyBtn.dataset.wired = 'true';
      copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(iso).then(() => {
          copyBtn.textContent = 'Copied!';
          copyBtn.disabled = true;
          setTimeout(() => {
            copyBtn.textContent = 'Copy ISO';
            copyBtn.disabled = false;
          }, 1500);
        });
      });
    }
  }
```

- [ ] **Step 2: Update `selectFile` to track the video file and call render**

Find the `selectFile` function (around line 170). Update it to store the file record and reset panel state:

```javascript
  function selectFile(path, type, el) {
    // ... existing selection code ...

    currentVideoFile = null;  // reset
    videoPaused = true;       // reset to paused state

    const video = document.getElementById('preview-video');
    const img = document.getElementById('preview-image');
    const placeholder = document.getElementById('preview-placeholder');
    placeholder.style.display = 'none';

    if (type === 'video') {
      // Get the file record for timestamp calculations
      currentVideoFile = originalFilesByPath[path] || null;

      let src = '/media/' + path;
      const trimStart = el.dataset.trimStart;
      const trimEnd = el.dataset.trimEnd;
      if (trimStart !== undefined && trimEnd !== undefined) {
        src += '#t=' + parseFloat(trimStart) + ',' + parseFloat(trimEnd);
        video.dataset.trimStart = trimStart;
        video.dataset.trimEnd = trimEnd;
      } else {
        delete video.dataset.trimStart;
        delete video.dataset.trimEnd;
      }
      video.src = src;
      video.style.display = 'block';
      img.style.display = 'none';
      video.load();
      renderTimestampPanel();
    } else {
      img.src = '/media/' + path;
      img.style.display = 'block';
      video.style.display = 'none';
      video.pause();
      video.src = '';
      delete video.dataset.trimStart;
      delete video.dataset.trimEnd;
      renderTimestampPanel();
    }
  }
```

- [ ] **Step 3: Add video event listeners for play/pause**

Find the existing `video.addEventListener('loadedmetadata', ...)` section (around line 30) and add after it:

```javascript
  video.addEventListener('play', () => {
    videoPaused = false;
    renderTimestampPanel();
  });

  video.addEventListener('pause', () => {
    videoPaused = true;
    renderTimestampPanel();
  });

  video.addEventListener('ended', () => {
    videoPaused = true;
    renderTimestampPanel();
  });
```

- [ ] **Step 4: Update index.html with the timestamp-display element**

Edit `index.html` to replace the `#timestamp-content` with proper structure:

```html
    <div id="timestamp-panel">
      <div id="timestamp-content">
        <div id="timestamp-label">Select a video to see timestamp</div>
        <div id="timestamp-display">
          <div class="timestamp-section-label">Current timestamp</div>
          <hr class="timestamp-divider">
          <div id="timestamp-human" class="timestamp-human"></div>
          <div id="timestamp-iso" class="timestamp-iso"></div>
          <button id="timestamp-copy-btn" type="button">Copy ISO</button>
        </div>
      </div>
    </div>
```

- [ ] **Step 5: Test manually**

Run the web server and test:
1. Select a video → panel shows "Select a video to see timestamp"
2. Click play → panel shows "Playing..."
3. Click pause → panel shows timestamps + Copy ISO button
4. Click Copy ISO → button shows "Copied!" for 1.5s, clipboard has ISO string
5. Select a photo → panel shows "No playback for photos"

- [ ] **Step 6: Commit**

```bash
git add src/photowalk/web/assets/app.js src/photowalk/web/assets/index.html
git commit -m "feat(web): implement video timestamp preview panel"
```

---

## Task 4: Final review and verification

- [ ] **Step 1: Run existing tests to ensure no regressions**

```bash
cd /Users/jorge/code/photo-walk && uv run pytest tests/ -v --tb=short 2>&1 | head -100
```

- [ ] **Step 2: Manual verification of all states**

Test each state from the spec checklist:
- [ ] Select video → panel shows "Select a video to see timestamp"
- [ ] Play video → panel shows "Playing..."
- [ ] Pause video → panel shows timestamp + copy button
- [ ] Click Copy ISO → clipboard contains ISO string
- [ ] Copy button shows "Copied!" briefly
- [ ] Select photo → panel shows "No playback for photos"
- [ ] Deselect file → panel shows "Select a video to see timestamp"

- [ ] **Step 3: Push to remote**

```bash
git push
```

---

## Self-Review Checklist

- [ ] All spec requirements covered (panel layout, states, timestamp calculation, copy button)
- [ ] No placeholders (TBD, TODO, implement later)
- [ ] Type consistency (methods match between tasks)
- [ ] Files follow existing patterns
- [ ] CSS selectors match HTML structure