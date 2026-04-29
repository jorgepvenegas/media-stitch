# Web UI Timestamp Sync — Design

**Status:** Approved
**Date:** 2026-04-29

## Goal

Let users adjust timestamps on photos and videos directly from the web timeline UI, in the same way the `photowalk sync` CLI command does — but with preview-first workflow, multi-step edits, and explicit on-disk apply.

## Motivation

Before running `stitch`, users frequently need to align cameras whose clocks drift relative to each other (e.g. one camera shows UTC, another shows local time). Today this requires leaving the UI, running `photowalk sync` for each affected subset, then re-launching `web` to verify the result. Folding sync into the UI shortens the loop: queue offsets, preview the resulting timeline, apply once it looks right.

## Decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | What does "Update timeline" do to disk? | Preview-only; a separate "Apply" button writes to disk. |
| 2 | Multiple offsets per session? | Stack of pending offsets, applied in order. |
| 3 | Offset input format? | Both duration string (`-8h23m5s`) and reference-pair (`wrong=correct`), reusing `offset.py`. |
| 4 | File selection? | Free multi-select via sidebar checkboxes, with "All videos" / "All photos" convenience buttons. |
| 5 | Safety on apply? | Confirmation modal with per-file `old → new` diff. |
| 6 | Pending stack persistence? | Browser memory only; refresh = lost. After successful apply, server re-extracts from disk. |

## Data Model

### Pending offset stack (browser-owned)

```js
{
  id: <uuid>,
  delta_seconds: <number>,            // signed
  source: { kind: "duration",  text: "-8h23m5s" }
        | { kind: "reference", wrong: "...", correct: "..." },
  target_paths: [<absolute_path>, ...]  // snapshot at queue time
}
```

`target_paths` is captured at the moment the entry is queued ("All videos" expands to concrete paths immediately). This freezes intent so later entries that touch a subset still apply cleanly.

### Files without timestamps

Excluded from selection in the UI (greyed out, checkbox disabled). Defense in depth: server preview/apply silently drops paths it sees with no timestamp.

### Reference-pair with multi-select

The `wrong=correct` parse yields a single `delta_seconds`; that delta is applied uniformly to every path in `target_paths`. Same semantics as the CLI.

## API Endpoints (new)

### `POST /api/offset/parse`

Validates an offset input and returns its delta in seconds. Reuses parsers in `offset.py`.

```
Request:  { kind: "duration",  text: "-8h23m5s" }
       |  { kind: "reference", wrong: "<iso>", correct: "<iso>" }
Response: { delta_seconds: -30185 }
       |  { error: "<message>" }
```

A reference pair whose delta is zero is treated as a parse error (no point queueing a no-op entry).

### `POST /api/timeline/preview`

Returns a freshly-built timeline reflecting the cumulative effect of the pending stack, without touching disk.

```
Request:  { offsets: [<entry>, ...] }
Response: {
  entries:  [...],         // same shape as GET /api/timeline
  settings: { image_duration: <float> },
  files:    [<file_entry>, ...]   // sidebar updates; each entry gets shifted: bool
}
```

Server logic (in `web/sync_preview.py`):
1. Start from the cached `(path, meta)` pairs the app was built with. **Never mutate** this cache.
2. For each entry in stack order, for each path in `target_paths`, add `delta_seconds` to that file's working timestamp.
3. Build a new `TimelineMap` via `build_timeline` on the shifted pairs.
4. Serialize via the existing `_metadata_to_file_entry` helper, extended with a `shifted: bool` flag (true when net delta ≠ 0 for that path).

### `POST /api/sync/apply`

Writes the cumulative effect of the stack to disk, one file at a time, then re-extracts and returns refreshed state.

```
Request:  { offsets: [<entry>, ...] }
Response: {
  applied:  [{ path, old_ts, new_ts }, ...],
  failed:   [{ path, error }, ...],
  files:    [...],
  timeline: {...}
}
```

Server logic (in `web/sync_apply.py`):
1. Compute **net delta per path** by summing across the stack. Zero-delta paths are skipped.
2. For each remaining path, dispatch to the appropriate writer (piexif for photos, ffmpeg for videos) — same writers used by the CLI `sync` command.
3. Per-file try/except: errors recorded in `failed[]`; the batch never aborts on a single failure.
4. After the batch (success and failure both), re-run `extract_metadata` for **every** path on disk. The refreshed list and a freshly built timeline are returned. This refreshed state is the source of truth even when writes partially failed.
5. Update the server's startup cache (`app.state` or equivalent) with the refreshed pairs so subsequent `GET /api/files` / `GET /api/timeline` reflect disk truth.

## UI Components

The current UI has 3 panels (preview player, source files sidebar, timeline). The sync feature adds a fourth, always-visible **Sync panel** docked above the timeline.

### Sync panel layout

```
┌─ Sync ────────────────────────────────────────────────┐
│  Mode:  ( ) Duration   ( ) Reference pair             │
│                                                       │
│  [ -8h23m5s            ]   ← duration mode            │
│   or                                                  │
│  Wrong:   [ 2026-04-27T23:28:01+00:00 ]               │
│  Correct: [ 2026-04-27T07:05:00       ]               │
│                                                       │
│  Selection: [All videos] [All photos] [Clear]         │
│             3 of 14 files selected                    │
│                                                       │
│              [ Add to queue ]                         │
├───────────────────────────────────────────────────────┤
│  Pending offsets (3)              [Update timeline]   │
│  1. -8h23m5s   → 7 videos              [×]            │
│  2. +30s       → IMG_0421.jpg          [×]            │
│  3. -1h        → 4 photos              [×]            │
│                                          [ Apply ]    │
└───────────────────────────────────────────────────────┘
```

### Sidebar changes

- Each row gets a checkbox to the left of the existing content.
- Files with `has_timestamp: false` render greyed out, checkbox disabled.
- "All videos" / "All photos" toggle the matching checkboxes (skipping greyed rows).
- Selection state lives in JS, independent of the pending stack.

### Visual cue for shifted files

When a preview response is in effect, files whose net delta ≠ 0 render their timestamp in italic with a small "shifted" badge, so the user can see what changed without manual diffing.

## Data Flow

### Flow A — Add to queue

```
User fills offset input, picks selection, clicks "Add to queue"
  → POST /api/offset/parse            (validate, get delta_seconds)
  ← { delta_seconds }  or  { error }
  → if error: show inline below input, abort
  → if ok:    snapshot checked paths, push entry to JS stack, render stack list
```

Selection checkboxes persist after queueing (user may queue another offset against the same selection).

### Flow B — Update timeline (preview)

```
User clicks "Update timeline"
  → POST /api/timeline/preview { offsets: <stack> }
  ← { entries, settings, files }
  → replace timeline render with entries
  → replace sidebar timestamps with files (mark shifted ones with badge)
```

The existing timeline renderer is reused unchanged.

### Flow C — Apply

```
User clicks "Apply"
  → UI builds the diff modal from the last preview response (already has old + new for each file)
  → User confirms in modal
  → POST /api/sync/apply { offsets: <stack> }
  ← { applied, failed, files, timeline }
  → if failed is non-empty:
       show toast/banner: "Applied N of M. K files failed:" with expandable list
  → refresh sidebar + timeline from response
  → clear pending stack, uncheck all selections, close modal
```

The diff modal is built from the **last preview** response — no extra preview call before apply. If the user hasn't clicked "Update timeline" since their last queue mutation, the modal reflects the most recent preview, which may be stale; UI guard: "Apply" is disabled until "Update timeline" has been clicked since the last stack change.

## Error Handling

| Case | Behavior |
|------|----------|
| Invalid offset string | Server `/api/offset/parse` returns `{ error }`. UI shows inline error in red. Stack untouched. |
| Reference pair with zero delta | Same as invalid offset (no-op entries blocked at parse time). |
| Empty selection on "Add to queue" | Button disabled — no server call. |
| Files without timestamps in selection | Cannot be checked in UI; defense-in-depth skip on server. |
| Preview server error (5xx, network) | Toast "Could not update timeline" with retry; last good preview remains on screen. |
| Apply — single writer failure | Recorded in `failed[]`; batch continues. UI shows partial-success banner with file/error list. |
| Apply — total failure (server crash, network) | Modal "Apply failed — no changes confirmed." Stack/selection preserved. UI auto-refreshes from `GET /api/files` + `/api/timeline` since some writes may have completed before the crash. |
| Concurrent apply/preview | Out of scope (local single-user). UI disables buttons while a request is in flight. |
| Multi-tab | Out of scope. Last apply wins. Documented limitation. |
| Undo after apply | Out of scope. Spec recommends user-managed backups, matching CLI behavior. Backup-on-apply is a future enhancement. |

## Testing

### Backend unit tests (~18 new)

**`web/sync_preview.py`**
- Single duration entry shifts only `target_paths`; other files untouched.
- Multiple stack entries compose: same file in two entries gets the summed delta.
- Reference-pair entry produces same shift as a duration entry with the equivalent delta.
- Files with no timestamp are silently skipped, even if listed in `target_paths`.
- Original cached `(path, meta)` pairs are not mutated.
- Returned `files` entries flag `shifted: true` only when net delta ≠ 0.
- Empty stack returns the same data as `GET /api/timeline` + `GET /api/files`.

**`web/sync_apply.py`**
- Net-delta-per-path computation: stack `[+1h, -30m]` against the same file → +30m written once, not two writes.
- Zero net delta paths are skipped (no writer call).
- Writer failure on one file does not abort the batch; failure recorded in `failed[]`.
- Re-extraction runs after writes (mock writers; assert `extract_metadata` is called per path post-batch).

**`web/server.py` — endpoint contracts (FastAPI TestClient)**
- `POST /api/offset/parse` — duration ok, reference ok, both error cases.
- `POST /api/timeline/preview` — empty stack, single-entry stack, multi-entry stack returns expected shifts.
- `POST /api/sync/apply` — happy path (mocked writers); partial failure returns both `applied` and `failed`.

### Frontend manual smoke checklist

The repo has no JS test framework, and adding one is out of scope. Manual checks at completion:

- [ ] Sync panel renders; mode toggle (duration / reference) works.
- [ ] Sidebar checkboxes appear; "All videos" / "All photos" toggle correctly; greyed rows cannot be checked.
- [ ] Bad offset string → inline error; queue not mutated.
- [ ] "Add to queue" → entry appears with correct target count.
- [ ] "Update timeline" → timeline re-renders; shifted files show badge.
- [ ] Removing a queue entry (×) → next "Update timeline" reflects removal.
- [ ] "Apply" → diff modal shows `old → new` per file; cancel does nothing.
- [ ] Apply confirm → files on disk actually shift (verify via `photowalk info` after).
- [ ] Apply with one un-writable file → partial-failure banner; written files reflect new times; sidebar refreshes.

### Explicitly out of test scope

- JS unit tests (no harness; adding one is scope creep).
- ffmpeg/piexif internals (covered by existing CLI tests).
- Multi-tab concurrency (declared out of scope).
- Browser automation / E2E.

## Files Touched

**New**
- `src/photowalk/web/sync_preview.py` — pure timeline-recompute logic.
- `src/photowalk/web/sync_apply.py` — orchestrates writers + re-extract.
- `tests/web/test_sync_preview.py`
- `tests/web/test_sync_apply.py`
- `tests/web/test_sync_endpoints.py`

**Modified**
- `src/photowalk/web/server.py` — three new endpoints; refresh `app.state` after apply; extend `_metadata_to_file_entry` with `shifted` flag.
- `src/photowalk/web/assets/index.html` — sync panel markup, sidebar checkboxes, diff modal.
- `src/photowalk/web/assets/style.css` — panel + checkbox + badge styles.
- `src/photowalk/web/assets/app.js` — pending stack state, queue/preview/apply flows, modal rendering.

**Untouched (intentionally)**
- `src/photowalk/offset.py` — reused as-is.
- `src/photowalk/writers.py` — reused as-is.
- `src/photowalk/timeline.py` — reused as-is.

## Out of Scope (future enhancements)

- Backup-on-apply (sidecar copies before writing).
- Undo / redo after apply.
- Persistent pending stack across page refresh.
- Multi-tab coordination.
- JS test harness.
