# Timeline Nudge Buttons — Design

## Summary

Add `←` and `→` buttons to the Details panel that shift the currently-selected timeline item by ±1 second per click. The shift reuses the existing offset queue (`pendingStack`) and triggers a debounced preview so the timeline updates without a manual "Update timeline" click.

## Motivation

The current sync flow requires the user to (1) select files via sidebar checkboxes, (2) type a duration like `-1s`, (3) click "Add to queue", (4) click "Update timeline". For small per-item adjustments this is too heavy. The nudge buttons reduce that to one click per second of adjustment for the item the user is already looking at.

## Scope

- Two buttons (`←`, `→`) and a running-total label, rendered in a new "Adjust" section at the top of the Details panel.
- Section is shown **only** when the user has selected an item by clicking a timeline bar. Sidebar selection does not show the section.
- Each click is `±1s`; no configurable increment.
- Nudges flow through the existing `pendingStack` and `/api/timeline/preview` endpoint. They are committed to disk via the existing "Apply" button. No new backend endpoint.

## Architecture

```
[click ←]  →  mutateNudge(path, -1)  →  scheduleDebouncedPreview()
                  │                            │
                  ▼                            ▼  (after 150ms idle)
            update pendingStack            updateTimeline()
            (coalesce or push)             (existing function:
                  │                         POST /api/timeline/preview,
                  ▼                         re-render sidebar + timeline)
            update running-total
            label immediately
                                                │
                                                ▼
                                        re-apply selection to
                                        the now-rebuilt timeline bar
```

No new server endpoint. All logic lives in `src/photowalk/web/assets/app.js`.

## UI

```
┌─ Details ───────────────────┐
│ Adjust                      │
│   [ ← ]  −2s  [ → ]         │
│ ─────────────────────────── │
│ File                        │
│   Name  IMG_0123.jpg        │
│   …                         │
```

- The "Adjust" section is rendered by `renderDetails` only when its `source` argument is `'timeline'`.
- The running-total label sits between the buttons. It reads from the current nudge entry on `pendingStack` for this file, and is hidden when the delta is `0s`.
- The buttons themselves are always enabled when the section is shown — there is no per-click disable during the debounce window. Clicks during the window simply reset the timer and update the local label.

## Queue mutation: last-entry coalesce

A nudge is just an offset queue entry with `target_paths.length === 1` and a `source.origin === 'nudge'` marker.

On click of `←` (delta `-1`) or `→` (delta `+1`) for file `path`:

```
top = pendingStack[pendingStack.length - 1]
if top
   AND top.target_paths.length === 1
   AND top.target_paths[0] === path
   AND top.source.kind === 'duration'
   AND top.source.origin === 'nudge':
       top.delta_seconds += delta
       top.source.text = formatSignedSeconds(top.delta_seconds)
       if top.delta_seconds === 0:
           pendingStack.pop()
else:
       pendingStack.push({
         id: crypto.randomUUID(),
         delta_seconds: delta,
         source: { kind: 'duration', text: formatSignedSeconds(delta), origin: 'nudge' },
         target_paths: [path],
       })
```

The `origin: 'nudge'` field distinguishes nudge entries from user-typed `-1s` duration entries so we never coalesce into the latter. Other code paths ignore the field.

When `delta_seconds` reaches `0` after coalescing (user pressed `←` then `→` on the same file), the entry is removed so the queue stays clean.

If the user performs another sync action between nudge clicks, the next nudge click pushes a fresh entry instead of coalescing — correct, just slightly less tidy. This is acceptable.

`previewIsCurrent` is set to `false` on every nudge click, mirroring `addToQueue`. The "Apply" button stays disabled until the next preview returns, governed by the existing `updateButtons()`.

## Debounce + preview

- One module-level debounce timer (150 ms), shared across nudge clicks.
- Each click resets the timer and updates the running-total label immediately for instant button feedback.
- When the timer fires, call the existing `updateTimeline()`. That function already POSTs `/api/timeline/preview`, re-renders the sidebar and timeline, and flips `previewIsCurrent = true`.
- After preview completes, re-read the running-total label from `pendingStack` so the displayed value reflects whatever the server may have normalized.

The 150 ms window is short enough to feel responsive on a single click and long enough to coalesce realistic key-mash bursts into one network round-trip.

## Selection persistence across re-render

`updateTimeline()` rebuilds the timeline SVG, which clears the `.selected` class on bars. After each `renderTimeline` we must re-apply the selection so the user can keep clicking `←` without losing the Adjust section.

Implementation:

- Track the currently-selected path and source (`'timeline'` vs `'sidebar'`) in module-level state.
- After each `renderTimeline`, re-apply the `.selected` class to the matching timeline bar (by `data-path`) and re-render the Details panel from the new entry data so the running-total stays in sync.

If the selected timeline bar was a `video_segment`, the matching bar after preview may have shifted but should still be uniquely identified by `data-path` plus position. We re-select the first bar matching the path. If the source path no longer appears on the timeline (unlikely after a 1 s shift, but possible), the selection is cleared and the empty state returns.

## Edge cases

- **Photos vs videos**: identical behavior. The offset model already handles both.
- **Video segments**: per the brainstorming decision, shifting a segment block shifts the source video's timestamp, which moves all sibling segments derived from the same source. No special hint is shown. This matches existing Sync semantics.
- **Apply commits the queue**: nudges are consumed along with everything else. Re-selecting the same item after Apply shows `0 s`.
- **Apply disabled until preview runs**: existing `updateButtons()` handles this; nudge clicks set `previewIsCurrent = false`, the debounced preview re-enables it.
- **Server error during nudge preview**: the existing toast in `updateTimeline()`'s catch already reports failure. The pending nudge entry remains on the stack; the user can click `Update timeline` manually or `Clear queue`.

## Testing

Frontend has no automated test harness today; adding one is out of scope. Verification is manual:

1. Open the app with at least one photo and one video on the timeline.
2. Click a photo bar on the timeline. Confirm the Adjust section appears at the top of Details with `← [hidden total] →`.
3. Click `←` twice. Confirm the label reads `−2s`, the queue panel shows one row, and after ~150 ms the timeline re-renders.
4. Click `→` twice. Confirm the running-total label disappears, the queue row disappears, and the timeline re-renders.
5. Click a sidebar entry. Confirm the Adjust section does not appear.
6. Click a timeline bar, then click `←` 5 times within 150 ms. In the Network tab, confirm exactly one POST to `/api/timeline/preview` fires after the burst.
7. Click `←` on a `video_segment` block whose source has multiple segments on the timeline. Confirm all sibling segments reorder accordingly.
8. After a nudge preview, click "Apply". Confirm the file's timestamp on disk shifts by the displayed delta and the queue clears.

## Files changed

- `src/photowalk/web/assets/app.js` — add nudge handlers, debounce timer, queue coalescing, selection persistence across re-render, Adjust-section render path in `renderDetails`.
- `src/photowalk/web/assets/style.css` — styling for the Adjust section (button row, running-total label).
- `src/photowalk/web/assets/index.html` — no change. The Adjust section is rendered via JS like all other Details sections.

No backend changes.

## Out of scope

- Configurable increment (e.g. ±0.5 s, ±5 s).
- Keyboard shortcuts for nudging.
- Per-segment-only shift (would require modeling per-segment offsets, which the current data model does not support).
- A separate "Reset" button on the Adjust section — pressing `→` until the delta returns to zero is sufficient.
- Automated tests for the frontend.
