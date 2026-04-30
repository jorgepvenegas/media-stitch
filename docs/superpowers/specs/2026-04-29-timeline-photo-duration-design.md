# Timeline Photo Duration Control

## Overview

Add an inline photo duration input to the Timeline header so users can preview how long photos appear in the timeline before rendering. The value also carries over to the Render modal so the user only sets it once.

## Background

Currently, the web UI timeline renders photos using a fixed `image_duration` (default 3.5s) loaded from the server. The only place to change this is inside the Render modal, which means you can't preview the effect of a different duration without first opening the render dialog. After applying offsets via the sync panel, users also can't see how a longer/shorter photo duration affects total timeline length until render time.

## Goals

- Let users change photo duration directly in the timeline view and see instant feedback.
- Carry the chosen duration into the Render modal.
- Keep the change minimal and backward-compatible.

## Non-Goals

- Persist the duration value across page reloads (out of scope; server default remains the source of truth).
- Add duration controls per individual photo (out of scope).
- Change the CLI `image_duration` default or how the server initializes it.

## Design

### Frontend

#### UI — `index.html`

Add a small inline control to the Timeline header, immediately after `<h3>Timeline</h3>`:

```html
<div class="timeline-duration-control">
  <label>Photo duration:</label>
  <input type="number" id="timeline-image-duration" value="3.5" step="0.1" min="0.1">
  <span>s</span>
</div>
```

#### State — `app.js`

1. New variable: `let currentImageDuration = timelineData.settings.image_duration || 3.5;`
2. On page load, set `#timeline-image-duration.value = currentImageDuration`.
3. Wire the input's `change` event:
   - Parse with `parseFloat`; if `NaN` or `< 0.1`, fall back to `0.1`.
   - Update `currentImageDuration`.
   - Immediately re-render the timeline SVG using the current entries and the new duration (no server round-trip).
4. In `updateTimeline()` (the `POST /api/timeline/preview` call):
   - Include `image_duration: currentImageDuration` in the request body.
   - After receiving the response, update `currentImageDuration = res.settings.image_duration` so the server-returned value is authoritative.
5. In `openRenderModal()`:
   - Set `#render-image-duration.value = String(currentImageDuration)` instead of reading from `timelineData.settings.image_duration`.
6. In `confirmApply()`:
   - After the apply response, sync `currentImageDuration = res.timeline.settings.image_duration`.

### Backend

#### Request model — `sync_models.py`

```python
class PreviewRequest(BaseModel):
    offsets: list[OffsetEntry]
    image_duration: float | None = None
```

The field is optional so existing callers (tests, API consumers) are unaffected.

#### Endpoint — `server.py`

In `api_timeline_preview`, change the `build_preview` call:

```python
image_duration = req.image_duration if req.image_duration is not None else app.state.image_duration
return build_preview(
    app.state.metadata_pairs,
    req.offsets,
    image_duration=image_duration,
)
```

No changes to `sync_preview.py` are needed; `build_preview` already accepts `image_duration` as a keyword argument.

### Data Flow

```
User changes timeline duration input
    ↓
currentImageDuration updated
renderTimelineFromData(entries, currentImageDuration)   ← instant SVG re-render
    ↓
User clicks "Update timeline"
POST /api/timeline/preview { offsets: [...], image_duration: currentImageDuration }
    ↓
Server falls back to app.state.image_duration when field is absent
    ↓
Response includes settings.image_duration
    ↓
Client updates currentImageDuration from response
Render modal pre-fills from currentImageDuration
```

### Edge Cases

| Scenario | Handling |
|----------|----------|
| Non-numeric input in duration field | `parseFloat` yields `NaN` → fallback to `0.1` |
| Zero or negative value | HTML `min="0.1"` plus client-side clamp to `0.1` |
| Preview request omits `image_duration` | Server falls back to `app.state.image_duration` |
| Apply refreshes timeline | `confirmApply` syncs `currentImageDuration` from response |

## Testing Plan

1. **Unit test** — `test_cli_sync.py` or a new web test:
   - `POST /api/timeline/preview` with `image_duration` returns entries with the specified duration in `settings.image_duration`.
   - `POST /api/timeline/preview` without `image_duration` falls back to the default.
2. **Frontend manual verification**:
   - Change timeline duration → photo bars resize instantly.
   - Update timeline with a pending offset stack → response reflects the custom duration.
   - Open Render modal → duration matches the timeline value.

## Files Changed

- `src/photowalk/web/assets/index.html` — add duration input to timeline header
- `src/photowalk/web/assets/app.js` — wire input, carry value through update/render flow
- `src/photowalk/web/sync_models.py` — add `image_duration` to `PreviewRequest`
- `src/photowalk/web/server.py` — use request-provided duration in `api_timeline_preview`
- `tests/test_cli_sync.py` — add tests for the new preview parameter

## Alternatives Considered

- **Pure client-side override** — no server changes, but overrides server-returned data which is brittle if the server ever computes metadata from `image_duration`.
- **Server-side state mutation via PUT endpoint** — keeps server as single source of truth, but adds unnecessary HTTP calls and server-side state for a visualization preference.

The chosen approach (request-level override with server fallback) is the minimal correct solution.
