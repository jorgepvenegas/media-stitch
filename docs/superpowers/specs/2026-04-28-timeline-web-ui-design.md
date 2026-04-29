# Timeline Web UI — Design Document

## Overview

A read-only web-based preview for the `photowalk stitch` workflow. A local FastAPI server serves a single-page app that visualizes the chronological timeline of videos and images, allows clicking any item to preview it, and lists all source files in a sidebar.

Future versions may add interactive features (drag-to-reorder, timestamp adjustment via the existing `sync` tool), but this design covers only the read-only preview.

---

## Goals

- Provide a visual timeline of how `photowalk stitch` will assemble media.
- Let users verify source files by previewing videos and images before running the CLI stitch.
- Reuse existing `photowalk` modules (`collect_files`, `extract_metadata`, `build_timeline`) without duplication.
- Keep the server stateless and offline-capable (no external CDN dependencies).

---

## Non-Goals

- Editing timeline order or durations.
- Adjusting timestamps via the UI (future work).
- Rendering or previewing the stitched output.
- Persisting state across server restarts.

---

## CLI Entry Point

```bash
photowalk web <path> [--port 8080] [--recursive]
```

| Argument | Description |
|----------|-------------|
| `path` | Directory or file(s) to scan for media |
| `--port` | Local server port (default: 8080) |
| `--recursive` | Scan subdirectories |

---

## UI Layout

Single-screen layout with three regions:

```
┌──────────────────────────────────────────────────────┐
│  PREVIEW PLAYER                                      │
│  (video element or <img>, full width, ~40vh height)  │
├──────────┬───────────────────────────────────────────┤
│ SIDEBAR  │           TIMELINE                        │
│          │  ┌─────────────────────────────────────┐  │
│ [source  │  │  [█████] [░] [██] [░] [████] [░]   │  │
│  files]  │  │  video  img video img  video  img   │  │
│          │  └─────────────────────────────────────┘  │
│          │  time axis ──o──o──o──o──o──o──o──o──    │
└──────────┴───────────────────────────────────────────┘
```

### Preview Player (top)
- Full-width container (~40% viewport height).
- `<video>` element for videos, `<img>` for photos.
- Loads the selected source file on click from timeline or sidebar.
- Videos use native browser controls.

### Sidebar (bottom-left, ~260px)
- Scrollable list of **source files** (originals from disk, not split segments).
- Each row: type icon, filename, timestamp, duration.
- Sorted chronologically.
- Files with missing timestamps shown at the bottom with a warning icon.
- Clicking a row selects it and loads the preview.

### Timeline (bottom-right, remaining width)
- Single horizontal track (video segments and images alternate chronologically).
- Rendered as an SVG.
- **Video segments** (`kind="video_segment"`): bars representing sub-clips of original videos after splitting around inline images. Color: blue.
- **Images** (`kind="image"`): bars with width representing their display duration in the final stitch (default 3.5s). Color: green.
- Horizontal scroll with a time axis below the track.
- Clicking any bar loads the preview.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serves the SPA HTML page |
| `GET` | `/api/timeline` | JSON timeline data (`all_entries` from `TimelineMap`) |
| `GET` | `/api/files` | JSON list of source files with metadata |
| `GET` | `/media/{path:path}` | Static file serving with path validation |

### `GET /api/timeline` Response

```json
{
  "entries": [
    {
      "kind": "video_segment",
      "source_path": "/Users/.../IMG_001.mp4",
      "start_time": "2024-06-15T14:23:10",
      "duration_seconds": 45.2,
      "trim_start": 0.0,
      "trim_end": 45.2,
      "original_video": "/Users/.../IMG_001.mp4"
    },
    {
      "kind": "image",
      "source_path": "/Users/.../IMG_002.jpg",
      "start_time": "2024-06-15T14:24:00",
      "duration_seconds": 3.5
    }
  ],
  "settings": {
    "image_duration": 3.5
  }
}
```

### `GET /api/files` Response

```json
{
  "files": [
    {
      "path": "/Users/.../IMG_001.mp4",
      "type": "video",
      "timestamp": "2024-06-15T14:23:10",
      "duration_seconds": 120.5,
      "has_timestamp": true
    }
  ]
}
```

---

## Data Flow

1. CLI parses args, calls `collect_files(path, recursive)`.
2. For each file, calls `extract_metadata()`.
3. Calls `build_timeline()` with `(path, metadata)` pairs → `TimelineMap`.
4. FastAPI app created with the scanned file set and timeline.
5. Browser loads `/` → receives HTML shell.
6. Frontend JS fetches `/api/timeline` and `/api/files` on load.
7. Renders SVG timeline and sidebar from JSON.
8. Clicking a bar/row loads `/media/<path>` into the preview player.

The server is **stateless**: every API request re-uses the timeline computed at startup. No database, no caching layer.

---

## File Structure

```
src/photowalk/
├── web/
│   ├── __init__.py
│   ├── server.py          # FastAPI app factory, endpoints, static file serving
│   └── assets/            # Embedded static assets
│       ├── index.html     # SPA shell
│       ├── app.js         # SVG timeline renderer, sidebar, preview player
│       └── style.css      # Layout, lane colors, scrollbars
```

### Asset Strategy

HTML, JS, and CSS are stored as files in `assets/` and read into memory at import time. FastAPI serves them from memory strings. No external CDN dependencies — works fully offline.

### Path Validation on `/media/{path}`

The endpoint checks that the requested path exists in the original scanned file set before serving. This prevents directory traversal attacks (e.g., `../../../etc/passwd`).

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| No media files found | Empty timeline + sidebar message: "No media files found in `<path>`" |
| File missing timestamp | Listed in sidebar with warning icon; omitted from timeline |
| `extract_metadata` / `ffprobe` fails | Silently skip file (matches existing CLI behavior) |
| Requested media file not in scan set | Return HTTP 404 |
| File deleted while server running | 404 on preview; timeline unchanged until page refresh |

---

## Dependencies

New runtime dependency:
- `fastapi` — web framework
- `uvicorn` — ASGI server (can be declared as an optional extra, e.g., `pip install photowalk[web]`)

No new frontend dependencies (vanilla JS + SVG).

---

## Testing Strategy

- **Backend unit tests** (`tests/test_web_server.py`) using FastAPI `TestClient`:
  - `GET /api/timeline` returns correct structure for a mocked `TimelineMap`.
  - `GET /media/<path>` returns 404 for paths outside the scan set.
  - `GET /` returns the HTML shell with expected asset references.
- **Frontend:** Manual testing for the initial read-only version. The SVG renderer is thin enough (~250 lines) that automated browser tests are deferred until interactive features are added.

---

## Future Work (Out of Scope)

- Drag-to-reorder items in the timeline.
- Adjust image display duration per file.
- In-app timestamp correction (reusing the `sync` tool).
- Live playhead scrubbing across the timeline.
- Export / trigger stitch directly from the UI.
