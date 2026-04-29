# Timeline Details Panel — Design

**Status:** Draft
**Date:** 2026-04-29
**Author:** Jorge Venegas

## Summary

Add a right-hand details panel to the web timeline UI. Clicking any
timeline bar (or sidebar file) populates the panel with the file's
metadata — timestamps for both photos and videos, EXIF-style camera
data for photos, and segment-specific timing when a `video_segment`
bar is clicked. Supports a "pending sync" view that shows
`original → shifted` timestamps when the user has queued offsets but
not yet applied them.

## Motivation

The timeline currently shows colored bars without surfacing the
underlying metadata. To audit timestamps, EXIF, or the result of a
queued sync offset, users have no in-UI inspection path — they have
to drop back to the CLI (`photowalk info`). This panel makes that
inspection a single click.

## User-Facing Behavior

### Layout

A new 300px column is added to the right of the timeline in the
existing `#bottom` flex row. New DOM order:

```
#bottom = #sidebar (260px) | #timeline (flex) | #details-panel (300px)
```

The panel has an `<h3>Details</h3>` header matching the sidebar and
timeline header styling. Body content scrolls vertically within the
panel; horizontal layout does not change above the bottom row.

### Empty state

When no file is selected, the body shows a centered muted-text
message:

> Select a file to see data

This is the initial state when the page loads, and the state after
the existing "Clear" selection button is pressed.

### Populated state — sections

Sections render top-to-bottom. A section is omitted entirely if all
its fields are empty.

**File** (always shown)
- Filename — basename, bold
- Type — `photo` or `video`
- Path — full path, monospace, wraps to next line on overflow

**Timestamps** (always shown)

- Photos: `Captured: 2026-04-27 23:28:01`
- Videos: `Start`, `End`, `Duration`
- Video segments (timeline click on `video_segment` only): a
  "This segment" block appears above the source video block,
  containing:
  - `Start on timeline` — the segment's `start_time`
  - `Trim start` — seconds offset within the source video
  - `Trim end` — seconds offset within the source video
  - `Segment duration` — `duration_seconds`
  Below it, a "Source video" block with the full file's start/end/duration.
- A timestamp with no value renders as `—` in dim text.

**Pending sync view.** If the file is part of an in-flight (queued
but not yet applied) sync offset, every timestamp in the panel is
rendered as `original → shifted`, and a "Pending sync" badge (reusing
the existing `.shifted-badge` style) appears next to the section
header. The timeline must be in preview state for this to apply —
i.e. the user has clicked "Update timeline" since adding the offset.
On apply, the queue is cleared and the panel re-renders with the new
on-disk values as the only timestamp.

**Camera** (photos only)
- Camera model
- Shutter speed
- ISO
- Focal length
- Missing fields render as `—`. Section is omitted entirely if all
  four are empty.

### Click behavior

| Source         | Behavior                                                              |
|----------------|-----------------------------------------------------------------------|
| Sidebar item   | Render File + Timestamps (no segment block) + Camera (if photo).      |
| Timeline bar (kind=`image`)         | Same as sidebar.                                |
| Timeline bar (kind=`video`)         | Same as sidebar.                                |
| Timeline bar (kind=`video_segment`) | File + Timestamps with "This segment" + "Source video" sub-blocks. Camera section is N/A for videos. |

The existing "Clear" selection button additionally resets the panel
to its empty state.

## Implementation

### Server changes

**`src/photowalk/web/server.py`**

Extend `_metadata_to_file_entry(path, meta)` to include all fields
from the metadata dataclasses. Existing keys (`path`, `type`,
`timestamp`, `duration_seconds`, `has_timestamp`) remain unchanged
for backward compatibility with the sidebar and timeline rendering.

New keys for `PhotoMetadata`:
- `camera_model: str | None`
- `shutter_speed: str | None`
- `iso: int | None`
- `focal_length: str | None`

New keys for `VideoMetadata`:
- `end_timestamp: str | None` (ISO-8601)

No new endpoints. `/api/files` and the `apply` response (which also
returns a `files` array) both ship the wider shape.

**`src/photowalk/web/sync_preview.py`**

`build_preview` produces the same `files` shape via its own
file-entry builder. Update it to mirror the new fields so that
post-preview and post-apply payloads carry them too. If the builder
currently shares logic with the server's helper, lift it to a small
shared function in `server.py` (or a new module) and import from
both places — do not duplicate the field list.

### Client changes — `src/photowalk/web/assets/app.js`

1. Build / update `filesByPath` map from `/api/files` to include the
   new fields.
2. Snapshot the unshifted file payload — when `/api/files` first
   loads, retain a copy of `filesByPath` as `originalFilesByPath`.
   This snapshot is also refreshed after a successful apply (using
   the `files` array the apply response returns), since post-apply
   the on-disk state becomes the new "original". The preview
   endpoint returns shifted values in `lastPreviewFiles`; the
   snapshot lets the panel render `original → shifted` without a
   second roundtrip.
3. Add `renderDetails(source, entry)` where:
   - `source` is `"sidebar"` or `"timeline"`
   - `entry` is the `/api/files` record (sidebar) or the timeline
     entry (timeline)
   - The function builds DOM into `#details-panel-body`. It looks up
     the file metadata from `filesByPath` using `entry.path` or
     `entry.source_path`.
4. Wire handlers:
   - Sidebar block click (currently in the `selectFile` invocation
     near line 83): call `renderDetails("sidebar", file)`.
   - Timeline rect click (line 224): call
     `renderDetails("timeline", timelineEntry)`.
5. Pending-sync detection: the existing client globals
   `previewIsCurrent` (true after "Update timeline", false after
   queue change / clear / apply) and `lastPreviewFiles` (each entry
   has a `shifted: bool` flag set by `build_preview`) drive this.
   When rendering, if `previewIsCurrent` is true AND the file's
   entry in `lastPreviewFiles` has `shifted === true`, render
   timestamps as `original → shifted`, where original comes from
   `originalFilesByPath` and shifted comes from `lastPreviewFiles`.
6. "Clear" selection handler additionally resets the panel to the
   empty state.

### Markup — `src/photowalk/web/assets/index.html`

Add inside `#bottom`, after `#timeline`:

```html
<div id="details-panel">
  <h3>Details</h3>
  <div id="details-panel-body">
    <div id="details-empty">Select a file to see data</div>
  </div>
</div>
```

### Styles — `src/photowalk/web/assets/style.css`

- `#details-panel`: 300px width, same dark-blue background as
  `#sidebar`, left border `1px solid #333`, flex column.
- `#details-panel h3`: matches `#sidebar h3` padding and font.
- `#details-panel-body`: flex 1, overflow-y auto, padding 12px 16px.
- `#details-empty`: muted color (`#666`), italic, centered.
- Section headers (e.g. `.details-section h4`): small, uppercase,
  letter-spaced, dim.
- Field rows: label on left (dim), value on right (bright), with a
  small gap. Path field wraps to a second line in monospace.
- Original-arrow-shifted: render shifted value bold, original in dim
  with a `→` separator.

## Data Flow

```
page load → GET /api/files                  → filesByPath (snapshot)
            GET /api/timeline               → timeline entries
user click → renderDetails(source, entry)
                ↓
            looks up file in filesByPath
                ↓
            checks shifted-paths set + preview state
                ↓
            builds File + Timestamps (+ Segment) + Camera DOM
post-apply → server returns updated files[] → filesByPath replaced;
                                              shifted set cleared;
                                              if a file is selected,
                                              re-render details
```

## Testing

### Server

Extend `tests/web/test_server.py` (or the closest existing module):

- `/api/files` for a photo includes `camera_model`, `shutter_speed`,
  `iso`, `focal_length` (verify with a fixture photo that has EXIF).
- `/api/files` for a video includes `end_timestamp`.
- `apply` response `files` payload also includes the new fields.

If `sync_preview.build_preview` has its own tests, extend them too.

### Client

No client unit tests exist in this project. Per `CLAUDE.md`,
manually verify in the browser before declaring done:

- Select a photo via sidebar — Camera section appears with EXIF.
- Select a photo with no EXIF — Camera section omitted.
- Select a video — Timestamps shows start/end/duration.
- Click a `video_segment` bar — "This segment" + "Source video"
  blocks both render.
- Queue an offset, click "Update timeline", click an affected file —
  timestamps shown as `original → shifted` with "Pending sync" badge.
- Click apply, confirm — panel re-renders with the new on-disk
  timestamps as the only value (no badge, no arrow).
- Click "Clear" selection — panel returns to empty state.

## Out of Scope

- Editing metadata from the panel.
- New EXIF fields not currently parsed (aperture, GPS, lens model).
- Per-file thumbnails in the panel.
- Showing histograms or audio waveforms.
- Persisting which file was selected across page reloads.

## Open Questions

None.
