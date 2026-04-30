# Render Ratio Presets

## Overview

Replace the free-text "Resolution (optional)" field in the Render modal with a row of aspect-ratio preset buttons. Each preset maps to a hardcoded resolution that the existing `StitchRequest.format` field already accepts.

## Background

The current Render modal has a text input for resolution (`1920x1080`). Users must know the exact pixel dimensions they want. Aspect ratios are more intuitive — photographers and videographers think in terms of landscape/portrait orientation and ratios like 16:9 vs 4:3.

## Goals

- Make resolution selection intuitive via aspect-ratio buttons.
- Default to landscape HD (16:9 → 1920×1080).
- Keep the change UI-only; reuse the existing backend contract.

## Non-Goals

- Custom resolution input (out of scope; CLI still supports arbitrary resolutions).
- Quality/pixel-density selector (e.g., 720p vs 4K for the same ratio).
- Changing the `StitchRequest` model or stitch pipeline.

## Design

### UI — `index.html`

Replace the existing resolution field:

```html
<div class="render-field">
  <label>Aspect ratio</label>
  <div class="ratio-buttons">
    <button type="button" class="ratio-btn active" data-format="1920x1080" data-label="16:9">16:9</button>
    <button type="button" class="ratio-btn" data-format="1080x1920" data-label="9:16">9:16</button>
    <button type="button" class="ratio-btn" data-format="1920x1440" data-label="4:3">4:3</button>
    <button type="button" class="ratio-btn" data-format="1080x1440" data-label="3:4">3:4</button>
  </div>
  <div class="ratio-resolution" id="ratio-resolution">1920 × 1080</div>
</div>
```

Remove the old `<input type="text" id="render-format">` field entirely.

### State — `app.js`

Track the selected format in a variable:

```javascript
let selectedRenderFormat = '1920x1080';
```

Wire the ratio buttons in `bindSyncPanel()` or a new `bindRenderModal()`:

```javascript
document.querySelectorAll('.ratio-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.ratio-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedRenderFormat = btn.dataset.format;
    document.getElementById('ratio-resolution').textContent = selectedRenderFormat.replace('x', ' × ');
  });
});
```

In `openRenderModal()`, reset to the default:

```javascript
selectedRenderFormat = '1920x1080';
document.querySelectorAll('.ratio-btn').forEach(b => b.classList.remove('active'));
document.querySelector('.ratio-btn[data-format="1920x1080"]').classList.add('active');
document.getElementById('ratio-resolution').textContent = '1920 × 1080';
```

In `startRender()`, replace:

```javascript
const format = document.getElementById('render-format').value.trim() || null;
```

with:

```javascript
const format = selectedRenderFormat;
```

### Styles — `style.css`

Add:

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

### Backend changes

None. The `StitchRequest.format` field already validates `"1920x1080"`, `"1080x1920"`, etc.

### Preset mapping

| Button label | Resolution | Orientation |
|--------------|------------|-------------|
| 16:9         | 1920×1080  | Landscape   |
| 9:16         | 1080×1920  | Portrait    |
| 4:3          | 1920×1440  | Landscape   |
| 3:4          | 1080×1440  | Portrait    |

## Testing Plan

1. **Unit test** — `test_web_stitch.py`: verify that a request with `format: "1080x1920"` is accepted and passed through to the stitch runner.
2. **Manual verification**: open Render modal, click each ratio button, confirm resolution text updates, start a draft render and verify output dimensions.

## Files Changed

- `src/photowalk/web/assets/index.html` — replace resolution input with ratio buttons
- `src/photowalk/web/assets/style.css` — ratio button styles
- `src/photowalk/web/assets/app.js` — wire buttons, track selected format, send to server
