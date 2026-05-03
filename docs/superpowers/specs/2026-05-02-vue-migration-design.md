# Vue Migration — Web UI Redesign

**Date:** 2026-05-02
**Status:** Draft

## Overview

Rewrite the web UI (`src/photowalk/web/assets/`) as a Vue 3 + TypeScript SPA served by the existing FastAPI backend. No backend changes.

## Goals

- **Reactivity** — state flows through Pinia stores; UI updates automatically when state changes
- **Component architecture** — three panels as isolated Vue components
- **Testability** — composables and stores are pure(ish) TypeScript, easy to unit test
- **Clean break** — old `assets/` replaced entirely by `vue-app/`; no hybrid state during migration

## Non-Goals

- No new backend endpoints
- No Vue Router (single-view SPA is fine for now)
- No SSR
- No Quasar or other full-stack frameworks

---

## Project Structure

```
src/photowalk/web/vue-app/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
├── postcss.config.js
├── src/
│   ├── main.ts                  # Vue app bootstrap
│   ├── App.vue                  # Root layout: 3-panel grid
│   ├── components/
│   │   ├── PreviewPanel.vue     # Video/image preview + timestamp panel
│   │   ├── SyncPanel.vue        # Offset input, queue, apply/render buttons
│   │   └── TimelinePanel.vue    # Sidebar + timeline SVG + axis + details
│   ├── stores/
│   │   └── appStore.ts          # Pinia store: files, selection, offsets, preview, render
│   ├── composables/
│   │   ├── useApi.ts           # All /api/* fetch calls
│   │   ├── useTimeline.ts      # Timeline SVG layout math
│   │   └── useRender.ts        # Render polling + cancel
│   └── types/
│       └── index.ts             # Shared TypeScript types (FileRecord, TimelineEntry, etc.)
```

**Old `assets/`** is removed once the Vue app is complete and serving at `/`.

---

## Backend Contract

No changes. The FastAPI server continues to expose:

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Serves the SPA index.html |
| `/assets/{filename}` | GET | Serves built static assets |
| `/media/{path}` | GET | Serves source media files |
| `/api/timeline` | GET | Initial timeline data |
| `/api/files` | GET | File list |
| `/api/offset/parse` | POST | Parse duration or reference offset |
| `/api/timeline/preview` | POST | Compute preview with offsets |
| `/api/sync/apply` | POST | Write timestamps to disk |
| `/api/stitch` | POST | Start video render |
| `/api/stitch/status` | GET | Poll render status |
| `/api/stitch/cancel` | POST | Cancel render |
| `/api/open-folder` | POST | Open output folder |

The Vue app is built to `src/photowalk/web/vue-app/dist/` (configured in `vite.config.ts`).

**Serving strategy:** `build_app_from_path` currently calls `_load_asset("index.html")`. After the migration, we update `server.py` to load from `vue-app/dist/index.html` instead of `assets/index.html`. The endpoint paths (`/api/*`, `/media/*`) stay identical.

---

## Component Design

### App.vue (Root)

Holds the 3-panel layout grid. Reads initial data from `useAppStore` on mount.

```vue
<template>
  <div class="app-layout">
    <PreviewPanel />
    <SyncPanel />
    <TimelinePanel />
  </div>
</template>
```

### PreviewPanel.vue

**State:** `selectedFile`, `isPlaying`, `currentTime`

**Sub-components (inline, not extracted):**
- `<video>` player with trim start/end support
- `<img>` for photo preview
- Timestamp panel (copy ISO, "Use as correct" button)

**Behavior:**
- Clicking a file in sidebar or timeline selects it here
- `isPlaying` drives the "Playing..." label vs. paused timestamp display
- `currentTime` + `trimStart` → compute actual playback timestamp

### SyncPanel.vue

**State:** `syncMode`, `offsetInput`, `pendingStack`, `previewIsCurrent`

**Behavior:**
- Duration vs. reference radio toggles the input form
- "Add to queue" → calls `useApi.parseOffset()` → pushes to `appStore.pendingStack`
- "Update timeline" → calls `useApi.previewTimeline()` → updates `appStore` files + entries
- "Apply" → calls `useApi.applySync()` → updates `appStore` files, clears queue
- "Render" → opens render modal

**Render modal** and **Apply modal** are sibling components, toggled by `v-if` from store state.

### TimelinePanel.vue

Holds sidebar, timeline SVG, axis, and details panel.

**State:** `imageDuration`, `timelineScale`, `zoom`, `selectedEntry`

**Behavior:**
- Sidebar renders `appStore.files`, grouped (has timestamp first, then without)
- Checkboxes update `appStore.selection`
- Timeline SVG uses `useTimeline` composable for layout math
- Axis ticks computed from layout positions
- Clicking a bar calls `appStore.selectFile()` → drives `PreviewPanel`

**Details panel** reads `appStore.selectedFile` and renders File / Timestamps / Camera sections. Includes the `±1s` nudge buttons that call `appStore.nudge()`.

---

## State Management (Pinia)

### useAppStore

```typescript
interface AppState {
  files: FileRecord[]           // current file list (original or preview)
  originalFilesByPath: Record<string, FileRecord>  // immutable originals
  selection: Set<string>        // paths
  pendingStack: OffsetEntry[]   // queue
  previewIsCurrent: boolean
  lastPreviewFiles: FileRecord[]
  timelineEntries: TimelineEntry[]
  timelineSettings: TimelineSettings
  selectedPath: string | null
  selectedSource: 'sidebar' | 'timeline' | null
  renderStatus: RenderStatus
  currentVideoFile: FileRecord | null
  isPlaying: boolean
  currentTime: number
}

interface FileRecord {
  path: string
  type: 'video' | 'photo'
  has_timestamp: boolean
  shifted: boolean
  timestamp: string | null
  end_timestamp: string | null
  duration_seconds: number | null
  trim_start?: number
  trim_end?: number
  // camera EXIF fields...
}

interface TimelineEntry {
  source_path: string
  kind: 'image' | 'video' | 'video_segment'
  start_time: string       // ISO
  duration_seconds: number
  trim_start?: number
  trim_end?: number
}

interface OffsetEntry {
  id: string
  delta_seconds: number
  source: { kind: 'duration'; text: string } | { kind: 'reference'; wrong: string; correct: string }
  target_paths: string[]
}
```

**Actions:** `selectFile`, `toggleSelection`, `addToQueue`, `removeFromQueue`, `clearQueue`, `nudge`, `applySync`, `startRender`, `cancelRender`

---

## Composables

### useApi

All fetch calls. Typed request/response. No side effects — just data.

```typescript
function useApi() {
  fetchTimeline(): Promise<TimelineResponse>
  fetchFiles(): Promise<FilesResponse>
  parseOffset(body): Promise<ParseResponse>
  previewTimeline(offsets, imageDuration): Promise<PreviewResponse>
  applySync(offsets): Promise<ApplyResponse>
  startRender(body): Promise<RenderStatus>
  pollRenderStatus(): Promise<RenderStatus>
  cancelRender(): Promise<void>
  openFolder(path): Promise<void>
}
```

### useTimeline

Pure layout math. Input: entries + imageDuration + scale. Output: positions array.

```typescript
function useTimeline() {
  computeLayout(entries, imageDuration, scale): Position[]
  formatAxisTicks(positions, scale): Tick[]
}
```

No DOM access. All SVG attribute computation happens in the component template or a lightweight `renderTimeline()` helper.

### useRender

Manages the render polling loop.

```typescript
function useRender() {
  startRender(body): void
  cancelRender(): Promise<void>
  pollStatus(): Promise<void>
}
```

Writes `renderStatus` to the store. Handles the open-folder callback.

---

## TypeScript Types

Shared types live in `src/types/index.ts`:

- `FileRecord`, `TimelineEntry`, `OffsetEntry`, `RenderStatus`
- Backend response shapes: `TimelineResponse`, `FilesResponse`, `ParseResponse`, etc.

These mirror the Pydantic models on the backend (`sync_models.py`, `stitch_models.py`, `file_entry.py`).

---

## Styling

**Tailwind CSS** with a custom dark theme:

```javascript
// tailwind.config.js
theme: {
  extend: {
    colors: {
      'app-bg': '#1a1a2e',
      'panel': '#16213e',
      'surface': '#0f0f1a',
      'border': '#333',
      'video-bar': '#4a90d9',
      'image-bar': '#5cb85c',
      'accent': '#d9a04a',
      'text': '#e0e0e0',
      'muted': '#888',
      'error': '#e74c3c',
    }
  }
}
```

All components use **scoped `<style>`** with utility classes from Tailwind. Custom CSS for complex layouts (timeline SVG rendering) goes in component `<style>` blocks.

**Existing CSS** (`style.css`) is NOT ported — Tailwind replaces it entirely.

---

## Migration Plan

1. **Scaffold** — create `vue-app/` with Vite, Vue 3, TypeScript, Tailwind, Pinia
2. **Types** — define `FileRecord`, `TimelineEntry`, `OffsetEntry`, all response types
3. **Store** — build `useAppStore` with all state and actions
4. **Composables** — implement `useApi`, `useTimeline`, `useRender`
5. **Components** — build `PreviewPanel`, `SyncPanel`, `TimelinePanel`
6. **App.vue** — layout shell wiring panels together
7. **Backend wiring** — update `server.py` to serve `vue-app/dist/`
8. **Test** — verify all features work: file selection, sync, preview, apply, render
9. **Delete old assets** — remove `assets/app.js`, `assets/style.css`

Steps 3–5 are order-independent; all three panels can be built in parallel once the store is ready.

---

## Error Handling

- API failures → show toast via a `useToast` composable (simple, no external lib)
- Render polling → graceful fallback if status endpoint is unreachable
- Missing timestamps → sidebar items disabled, visual warning state (keep existing pattern)
- Video trim bounds → `timeupdate` / `seeking` guards (keep existing pattern)

---

## Testing Strategy

- **Composables** — unit tests (Vitest), mock `fetch`
- **Store** — unit tests (Vitest), verify state transitions
- **Components** — shallow render tests (Vue Test Utils), mock store via Pinia
- **E2E** — minimal: start server + Vite dev server, open browser, basic smoke test