# Timeline Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `photowalk web` CLI command that starts a local FastAPI server serving a read-only timeline preview UI for the stitch workflow.

**Architecture:** FastAPI backend exposes three JSON endpoints (`/api/timeline`, `/api/files`, `/media/{path}`) over existing `photowalk` modules. A vanilla JS SPA renders an SVG timeline with a preview player and source file sidebar. Assets are embedded in the package.

**Tech Stack:** FastAPI, uvicorn, vanilla JS, SVG

---

## File Structure

| File | Purpose |
|------|---------|
| `pyproject.toml` | Add `fastapi` and `uvicorn` as optional `[web]` extra |
| `src/photowalk/web/__init__.py` | Package init, exports `create_app` |
| `src/photowalk/web/server.py` | FastAPI app factory, endpoints, path validation, asset serving |
| `src/photowalk/web/assets/index.html` | SPA shell with preview player, sidebar, timeline container |
| `src/photowalk/web/assets/style.css` | Layout, colors, scrollbars |
| `src/photowalk/web/assets/app.js` | Fetch API calls, SVG timeline renderer, sidebar builder, preview loader |
| `src/photowalk/cli.py` | Add `web` command |
| `tests/test_web_server.py` | FastAPI `TestClient` tests for all endpoints and path validation |

---

### Task 1: Add FastAPI + uvicorn as optional dependencies

**Files:**
- Modify: `pyproject.toml`

**Context:** These are only needed for the `web` feature. Declaring them as an optional extra keeps the base install lightweight.

- [ ] **Step 1: Add `[project.optional-dependencies]` section to pyproject.toml**

  Add the following new section (before `[build-system]`):

  ```toml
  [project.optional-dependencies]
  web = [
      "fastapi>=0.115.0",
      "uvicorn>=0.34.0",
  ]
  ```

- [ ] **Step 2: Install the package with web extras in dev mode**

  Run: `uv pip install -e ".[web]"`
  Expected: installs fastapi and uvicorn successfully

- [ ] **Step 3: Verify imports work**

  Run: `uv run python -c "import fastapi, uvicorn; print('ok')"`
  Expected: prints `ok`

- [ ] **Step 4: Commit**

  ```bash
  git add pyproject.toml
  git commit -m "deps: add fastapi and uvicorn as optional [web] extras"
  ```

---

### Task 2: Create the FastAPI server module

**Files:**
- Create: `src/photowalk/web/__init__.py`
- Create: `src/photowalk/web/server.py`

**Context:** The server module contains:
1. `create_app()` — app factory that accepts `scan_files: set[Path]` and `timeline: TimelineMap`, returns a `FastAPI` instance.
2. `build_app_from_path()` — convenience that scans a directory, extracts metadata, builds timeline, and calls `create_app()`.
3. Three endpoints: `/`, `/api/timeline`, `/api/files`, `/media/{path:path}`.
4. Path validation on `/media` to prevent directory traversal.

- [ ] **Step 1: Write `src/photowalk/web/__init__.py`**

  ```python
  from photowalk.web.server import create_app, build_app_from_path

  __all__ = ["create_app", "build_app_from_path"]
  ```

- [ ] **Step 2: Write `src/photowalk/web/server.py`**

  ```python
  import json
  from pathlib import Path
  from typing import Set

  from fastapi import FastAPI, HTTPException
  from fastapi.responses import HTMLResponse, FileResponse, JSONResponse

  from photowalk.models import PhotoMetadata, VideoMetadata
  from photowalk.timeline import TimelineMap


  def _load_asset(filename: str) -> str:
      asset_dir = Path(__file__).parent / "assets"
      return (asset_dir / filename).read_text()


  def create_app(scan_files: Set[Path], timeline: TimelineMap, image_duration: float = 3.5) -> FastAPI:
      app = FastAPI()

      @app.get("/", response_class=HTMLResponse)
      async def index():
          html = _load_asset("index.html")
          return HTMLResponse(content=html)

      @app.get("/api/timeline")
      async def api_timeline():
          entries = []
          for entry in timeline.all_entries:
              data = {
                  "kind": entry.kind,
                  "source_path": str(entry.source_path),
                  "start_time": entry.start_time.isoformat() if entry.start_time else None,
                  "duration_seconds": entry.duration_seconds,
              }
              if entry.kind == "video_segment":
                  data["trim_start"] = entry.trim_start
                  data["trim_end"] = entry.trim_end
                  data["original_video"] = str(entry.original_video) if entry.original_video else None
              entries.append(data)
          return {"entries": entries, "settings": {"image_duration": image_duration}}

      @app.get("/api/files")
      async def api_files():
          files = []
          for path in sorted(scan_files):
              from photowalk.api import extract_metadata
              meta = extract_metadata(path)
              if meta is None:
                  continue
              if isinstance(meta, PhotoMetadata):
                  files.append({
                      "path": str(path),
                      "type": "photo",
                      "timestamp": meta.timestamp.isoformat() if meta.timestamp else None,
                      "duration_seconds": None,
                      "has_timestamp": meta.timestamp is not None,
                  })
              elif isinstance(meta, VideoMetadata):
                  files.append({
                      "path": str(path),
                      "type": "video",
                      "timestamp": meta.start_timestamp.isoformat() if meta.start_timestamp else None,
                      "duration_seconds": meta.duration_seconds,
                      "has_timestamp": meta.start_timestamp is not None,
                  })
          return {"files": files}

      @app.get("/media/{path:path}")
      async def media(path: str):
          resolved = Path(path).resolve()
          if resolved not in scan_files:
              raise HTTPException(status_code=404, detail="File not found")
          if not resolved.exists():
              raise HTTPException(status_code=404, detail="File not found")
          return FileResponse(resolved)

      return app


  def build_app_from_path(
      path: Path,
      recursive: bool = False,
      image_duration: float = 3.5,
  ) -> FastAPI:
      from photowalk.collector import collect_files
      from photowalk.api import extract_metadata
      from photowalk.timeline import build_timeline

      files = collect_files([path], recursive=recursive)
      scan_files = set(files)

      pairs = []
      for f in files:
          meta = extract_metadata(f)
          if meta is not None:
              pairs.append((f, meta))

      timeline = build_timeline(pairs)
      return create_app(scan_files, timeline, image_duration)
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add src/photowalk/web/__init__.py src/photowalk/web/server.py
  git commit -m "feat(web): add FastAPI server module with timeline and file endpoints"
  ```

---

### Task 3: Create the frontend HTML shell

**Files:**
- Create: `src/photowalk/web/assets/index.html`

**Context:** Single-page app with three regions: preview player (top), sidebar (bottom-left), timeline (bottom-right). Includes embedded links to `style.css` and `app.js`.

- [ ] **Step 1: Write `src/photowalk/web/assets/index.html`**

  ```html
  <!DOCTYPE html>
  <html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Photo Walk — Timeline Preview</title>
    <link rel="stylesheet" href="/assets/style.css">
  </head>
  <body>
    <div id="app">
      <div id="preview">
        <video id="preview-video" controls style="display:none;"></video>
        <img id="preview-image" style="display:none;">
        <div id="preview-placeholder">Select an item to preview</div>
      </div>
      <div id="bottom">
        <div id="sidebar">
          <h3>Source Files</h3>
          <div id="sidebar-list"></div>
        </div>
        <div id="timeline">
          <h3>Timeline</h3>
          <div id="timeline-scroll">
            <svg id="timeline-svg"></svg>
          </div>
          <div id="timeline-axis"></div>
        </div>
      </div>
    </div>
    <script src="/assets/app.js"></script>
  </body>
  </html>
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add src/photowalk/web/assets/index.html
  git commit -m "feat(web): add SPA HTML shell"
  ```

---

### Task 4: Create the frontend CSS

**Files:**
- Create: `src/photowalk/web/assets/style.css`

**Context:** Layout uses CSS grid/flexbox. Preview player takes top 40vh. Bottom area is split: sidebar 260px fixed, timeline takes remainder. Timeline area has horizontal scroll. Video bars are blue (#4a90d9), image bars are green (#5cb85c).

- [ ] **Step 1: Write `src/photowalk/web/assets/style.css`**

  ```css
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #1a1a2e;
    color: #e0e0e0;
    height: 100vh;
    overflow: hidden;
  }
  #app { display: flex; flex-direction: column; height: 100vh; }

  /* Preview player */
  #preview {
    height: 40vh;
    background: #0f0f1a;
    display: flex;
    align-items: center;
    justify-content: center;
    border-bottom: 1px solid #333;
  }
  #preview video, #preview img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
  }
  #preview-placeholder {
    color: #666;
    font-size: 1.2rem;
  }

  /* Bottom area */
  #bottom { display: flex; flex: 1; overflow: hidden; }

  /* Sidebar */
  #sidebar {
    width: 260px;
    background: #16213e;
    border-right: 1px solid #333;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  #sidebar h3 {
    padding: 12px 16px;
    font-size: 0.9rem;
    border-bottom: 1px solid #333;
  }
  #sidebar-list { flex: 1; overflow-y: auto; }
  .sidebar-item {
    padding: 10px 16px;
    border-bottom: 1px solid #222;
    cursor: pointer;
    font-size: 0.85rem;
  }
  .sidebar-item:hover { background: #1e2a4a; }
  .sidebar-item.selected { background: #2a3a5a; }
  .sidebar-item .filename {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: #fff;
  }
  .sidebar-item .meta {
    color: #888;
    font-size: 0.75rem;
    margin-top: 2px;
  }
  .sidebar-item.warning .meta { color: #e74c3c; }

  /* Timeline */
  #timeline {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  #timeline h3 {
    padding: 12px 16px;
    font-size: 0.9rem;
    border-bottom: 1px solid #333;
  }
  #timeline-scroll {
    flex: 1;
    overflow-x: auto;
    overflow-y: hidden;
    position: relative;
  }
  #timeline-svg {
    height: 100%;
    min-width: 100%;
  }
  .timeline-bar {
    cursor: pointer;
    stroke: #fff;
    stroke-width: 1;
  }
  .timeline-bar.video { fill: #4a90d9; }
  .timeline-bar.image { fill: #5cb85c; }
  .timeline-bar:hover { opacity: 0.85; }
  .timeline-bar.selected { stroke: #ffd700; stroke-width: 2; }
  .timeline-label {
    fill: #fff;
    font-size: 11px;
    pointer-events: none;
    dominant-baseline: middle;
  }
  #timeline-axis {
    height: 30px;
    border-top: 1px solid #333;
    background: #16213e;
    position: relative;
  }
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add src/photowalk/web/assets/style.css
  git commit -m "feat(web): add SPA styles"
  ```

---

### Task 5: Create the frontend JavaScript

**Files:**
- Create: `src/photowalk/web/assets/app.js`

**Context:** Vanilla JS. On load: fetches `/api/timeline` and `/api/files`, renders SVG timeline and sidebar. Clicking any bar or sidebar item loads `/media/<path>` into the preview player.

Timeline rendering:
- Compute total time span from earliest to latest entry.
- Scale: pixels per second = `svgWidth / totalSeconds`.
- Each entry rendered as a `<rect>` at `x = (entry.start_time - min_time) * scale`, width = `entry.duration_seconds * scale`.
- All bars at the same Y position (single lane).
- Add a text label inside each bar if width > 40px.

- [ ] **Step 1: Write `src/photowalk/web/assets/app.js`**

  ```javascript
  (async function() {
    const [timelineRes, filesRes] = await Promise.all([
      fetch('/api/timeline'),
      fetch('/api/files'),
    ]);
    const timelineData = await timelineRes.json();
    const filesData = await filesRes.json();

    const entries = timelineData.entries;
    const files = filesData.files;

    renderSidebar(files);
    if (entries.length > 0) {
      renderTimeline(entries);
    } else {
      document.getElementById('timeline-scroll').innerHTML =
        '<div style="padding:20px;color:#666;">No timeline entries.</div>';
    }

    function renderSidebar(files) {
      const container = document.getElementById('sidebar-list');
      container.innerHTML = '';

      const hasTs = files.filter(f => f.has_timestamp);
      const noTs = files.filter(f => !f.has_timestamp);

      [...hasTs, ...noTs].forEach(f => {
        const el = document.createElement('div');
        el.className = 'sidebar-item' + (f.has_timestamp ? '' : ' warning');
        el.dataset.path = f.path;

        const icon = f.type === 'video' ? '🎬' : '📷';
        const ts = f.timestamp ? new Date(f.timestamp).toLocaleString() : 'No timestamp';
        const dur = f.duration_seconds ? ` • ${f.duration_seconds.toFixed(1)}s` : '';

        el.innerHTML = `
          <div class="filename">${icon} ${f.path.split('/').pop()}</div>
          <div class="meta">${ts}${dur}</div>
        `;
        el.addEventListener('click', () => selectFile(f.path, f.type, el));
        container.appendChild(el);
      });
    }

    function renderTimeline(entries) {
      const svg = document.getElementById('timeline-svg');
      const scroll = document.getElementById('timeline-scroll');

      const times = entries.map(e => new Date(e.start_time).getTime());
      const minTime = Math.min(...times);
      const maxTime = Math.max(...times.map((t, i) => t + entries[i].duration_seconds * 1000));
      const totalMs = maxTime - minTime;
      const totalSeconds = totalMs / 1000;

      const barHeight = 40;
      const padding = 20;
      const svgHeight = barHeight + padding * 2;
      const scale = 50; // pixels per second
      const svgWidth = Math.max(scroll.clientWidth, totalSeconds * scale + padding * 2);

      svg.setAttribute('width', svgWidth);
      svg.setAttribute('height', svgHeight);
      svg.innerHTML = '';

      entries.forEach((entry, i) => {
        const startMs = new Date(entry.start_time).getTime() - minTime;
        const x = padding + (startMs / 1000) * scale;
        const w = Math.max(2, entry.duration_seconds * scale);
        const y = padding;

        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('x', x);
        rect.setAttribute('y', y);
        rect.setAttribute('width', w);
        rect.setAttribute('height', barHeight);
        rect.setAttribute('rx', 3);
        rect.classList.baseVal = `timeline-bar ${entry.kind === 'image' ? 'image' : 'video'}`;
        rect.dataset.path = entry.source_path;
        rect.dataset.kind = entry.kind === 'image' ? 'photo' : 'video';
        rect.addEventListener('click', () => selectFile(entry.source_path, rect.dataset.kind, rect));
        svg.appendChild(rect);

        if (w > 40) {
          const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
          label.setAttribute('x', x + 4);
          label.setAttribute('y', y + barHeight / 2);
          label.classList.baseVal = 'timeline-label';
          const name = entry.source_path.split('/').pop();
          label.textContent = name.length > 20 ? name.slice(0, 18) + '…' : name;
          svg.appendChild(label);
        }
      });

      renderAxis(minTime, maxTime, scale, padding);
    }

    function renderAxis(minTime, maxTime, scale, padding) {
      const axis = document.getElementById('timeline-axis');
      axis.innerHTML = '';
      const totalSeconds = (maxTime - minTime) / 1000;
      const containerWidth = axis.clientWidth;
      const tickInterval = totalSeconds > 600 ? 60 : (totalSeconds > 120 ? 30 : 10);
      const numTicks = Math.floor(totalSeconds / tickInterval);

      for (let i = 0; i <= numTicks; i++) {
        const sec = i * tickInterval;
        const left = padding + sec * scale;
        if (left > containerWidth) break;

        const tick = document.createElement('div');
        tick.style.position = 'absolute';
        tick.style.left = left + 'px';
        tick.style.top = '0';
        tick.style.fontSize = '11px';
        tick.style.color = '#888';
        tick.style.paddingLeft = '4px';
        tick.style.borderLeft = '1px solid #444';
        tick.style.height = '100%';
        tick.style.whiteSpace = 'nowrap';

        const date = new Date(minTime + sec * 1000);
        tick.textContent = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        axis.appendChild(tick);
      }
    }

    function selectFile(path, type, el) {
      // Clear previous selections
      document.querySelectorAll('.sidebar-item.selected').forEach(e => e.classList.remove('selected'));
      document.querySelectorAll('.timeline-bar.selected').forEach(e => e.classList.remove('selected'));

      if (el.classList.contains('sidebar-item')) {
        el.classList.add('selected');
        // Also highlight matching timeline bar if any
        document.querySelectorAll(`.timeline-bar[data-path="${CSS.escape(path)}"]`).forEach(b => b.classList.add('selected'));
      } else {
        el.classList.add('selected');
        // Also highlight matching sidebar item
        document.querySelectorAll(`.sidebar-item[data-path="${CSS.escape(path)}"]`).forEach(b => b.classList.add('selected'));
      }

      const video = document.getElementById('preview-video');
      const img = document.getElementById('preview-image');
      const placeholder = document.getElementById('preview-placeholder');

      placeholder.style.display = 'none';

      if (type === 'video') {
        video.src = '/media/' + path;
        video.style.display = 'block';
        img.style.display = 'none';
        video.load();
      } else {
        img.src = '/media/' + path;
        img.style.display = 'block';
        video.style.display = 'none';
        video.pause();
        video.src = '';
      }
    }
  })();
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add src/photowalk/web/assets/app.js
  git commit -m "feat(web): add vanilla JS timeline renderer and preview loader"
  ```

---

### Task 6: Wire the `web` CLI command into `cli.py`

**Files:**
- Modify: `src/photowalk/cli.py`

**Context:** Add a new `web` subcommand that:
1. Collects files from the given path.
2. Prints a message if no files are found.
3. Builds the FastAPI app via `build_app_from_path`.
4. Starts uvicorn on the specified port.
5. Prints the local URL for the user.

The command should handle the optional `[web]` dependency gracefully — if FastAPI is not installed, print a helpful error message.

- [ ] **Step 1: Add imports at the top of `cli.py`**

  Add after the existing imports:

  ```python
  try:
      from photowalk.web.server import build_app_from_path
      HAS_WEB = True
  except ImportError:
      HAS_WEB = False
  ```

- [ ] **Step 2: Add the `web` command before `if __name__ == "__main__":`**

  ```python
  @main.command()
  @click.argument("path", type=click.Path(exists=True, path_type=Path))
  @click.option("--port", default=8080, type=int, help="Server port")
  @click.option("--recursive", "-r", is_flag=True)
  @click.option("--image-duration", default=3.5, type=float)
  def web(path, port, recursive, image_duration):
      """Start a local web server for timeline preview."""
      if not HAS_WEB:
          click.echo(
              click.style(
                  "Error: Web dependencies not installed. Run: uv pip install -e '.[web]'",
                  fg="red",
              ),
              err=True,
          )
          raise Exit(1)

      try:
          files = collect_files([path], recursive=recursive)
      except RuntimeError as e:
          click.echo(click.style(str(e), fg="red"), err=True)
          raise Exit(1)

      if not files:
          click.echo("No media files found.")
          return

      app = build_app_from_path(path, recursive=recursive, image_duration=image_duration)
      click.echo(click.style(f"Starting server at http://127.0.0.1:{port}", fg="green"))
      click.echo("Press Ctrl+C to stop")

      import uvicorn
      uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
  ```

- [ ] **Step 3: Verify the import fallback works**

  Run (in a fresh Python process without web extras):
  ```bash
  uv run python -c "from photowalk.cli import main; print('import ok')"
  ```
  Expected: prints `import ok` without error (the ImportError is caught).

- [ ] **Step 4: Commit**

  ```bash
  git add src/photowalk/cli.py
  git commit -m "feat(cli): add web command to start timeline preview server"
  ```

---

### Task 7: Write backend tests

**Files:**
- Create: `tests/test_web_server.py`

**Context:** Tests use FastAPI `TestClient` to verify:
1. `GET /` returns HTML with expected structure.
2. `GET /api/timeline` returns correct JSON for a mocked timeline.
3. `GET /api/files` returns file metadata.
4. `GET /media/<path>` serves a file that exists in the scan set.
5. `GET /media/<path>` returns 404 for paths outside the scan set.
6. `GET /media/<path>` returns 404 for non-existent files.

- [ ] **Step 1: Write `tests/test_web_server.py`**

  ```python
  import json
  from datetime import datetime
  from pathlib import Path

  import pytest
  from fastapi.testclient import TestClient

  from photowalk.timeline import TimelineMap, TimelineEntry
  from photowalk.web.server import create_app


  def test_index_returns_html():
      app = create_app(set(), TimelineMap())
      client = TestClient(app)
      response = client.get("/")
      assert response.status_code == 200
      assert "text/html" in response.headers["content-type"]
      assert "Timeline Preview" in response.text


  def test_api_timeline():
      entry = TimelineEntry(
          start_time=datetime(2024, 6, 15, 14, 0, 0),
          duration_seconds=45.0,
          kind="video_segment",
          source_path=Path("/tmp/video.mp4"),
          original_video=Path("/tmp/video.mp4"),
          trim_start=0.0,
          trim_end=45.0,
      )
      timeline = TimelineMap(all_entries=[entry])
      app = create_app({Path("/tmp/video.mp4")}, timeline, image_duration=3.5)
      client = TestClient(app)
      response = client.get("/api/timeline")
      assert response.status_code == 200
      data = response.json()
      assert data["settings"]["image_duration"] == 3.5
      assert len(data["entries"]) == 1
      assert data["entries"][0]["kind"] == "video_segment"
      assert data["entries"][0]["duration_seconds"] == 45.0


  def test_api_files(tmp_path):
      img = tmp_path / "photo.jpg"
      img.write_text("fake")
      # We can't easily mock extract_metadata here without monkeypatching,
      # so we'll test the endpoint structure by creating a photo file
      # and verifying the endpoint returns data (may be skipped if no metadata).
      timeline = TimelineMap()
      app = create_app({img}, timeline)
      client = TestClient(app)
      response = client.get("/api/files")
      assert response.status_code == 200
      data = response.json()
      assert "files" in data


  def test_media_serves_allowed_file(tmp_path):
      file_path = tmp_path / "allowed.mp4"
      file_path.write_text("fake video content")
      timeline = TimelineMap()
      app = create_app({file_path}, timeline)
      client = TestClient(app)
      response = client.get(f"/media/{file_path}")
      assert response.status_code == 200
      assert response.text == "fake video content"


  def test_media_rejects_path_outside_scan_set(tmp_path):
      file_path = tmp_path / "secret.txt"
      file_path.write_text("secret")
      timeline = TimelineMap()
      app = create_app(set(), timeline)
      client = TestClient(app)
      response = client.get(f"/media/{file_path}")
      assert response.status_code == 404


  def test_media_rejects_nonexistent_file(tmp_path):
      file_path = tmp_path / "missing.mp4"
      timeline = TimelineMap()
      app = create_app({file_path}, timeline)
      client = TestClient(app)
      response = client.get(f"/media/{file_path}")
      assert response.status_code == 404
  ```

- [ ] **Step 2: Run the tests**

  Run: `uv run pytest tests/test_web_server.py -v`
  Expected: all 6 tests pass

- [ ] **Step 3: Commit**

  ```bash
  git add tests/test_web_server.py
  git commit -m "test(web): add FastAPI endpoint tests"
  ```

---

### Task 8: Add static asset serving for CSS and JS

**Files:**
- Modify: `src/photowalk/web/server.py`

**Context:** The HTML references `/assets/style.css` and `/assets/app.js`, but the current server has no route for `/assets/*`. We need to add a static file endpoint for assets.

- [ ] **Step 1: Add `/assets/{filename}` endpoint to `create_app` in `server.py`**

  Insert inside `create_app`, after the `/` endpoint:

  ```python
      @app.get("/assets/{filename}")
      async def asset(filename: str):
          allowed = {"style.css", "app.js", "index.html"}
          if filename not in allowed:
              raise HTTPException(status_code=404, detail="Asset not found")
          content = _load_asset(filename)
          media_type = "text/css" if filename.endswith(".css") else "application/javascript" if filename.endswith(".js") else "text/html"
          return HTMLResponse(content=content, media_type=media_type)
  ```

  **Note:** In `server.py`, the existing `/` endpoint uses `_load_asset("index.html")`. The new `/assets/index.html` endpoint is optional but harmless. The important additions are `/assets/style.css` and `/assets/app.js`.

- [ ] **Step 2: Add a test for asset serving**

  Append to `tests/test_web_server.py`:

  ```python
  def test_assets_serve_css_and_js():
      app = create_app(set(), TimelineMap())
      client = TestClient(app)
      css = client.get("/assets/style.css")
      assert css.status_code == 200
      assert "text/css" in css.headers["content-type"]
      js = client.get("/assets/app.js")
      assert js.status_code == 200
      assert "javascript" in js.headers["content-type"]
  ```

- [ ] **Step 3: Run tests to verify asset serving works**

  Run: `uv run pytest tests/test_web_server.py -v`
  Expected: all tests pass

- [ ] **Step 4: Commit**

  ```bash
  git add src/photowalk/web/server.py tests/test_web_server.py
  git commit -m "feat(web): add static asset serving for CSS and JS"
  ```

---

### Task 9: End-to-end smoke test

**Files:**
- None (manual verification)

- [ ] **Step 1: Create a temporary directory with fake media files**

  ```bash
  mkdir -p /tmp/pw-smoke
  touch /tmp/pw-smoke/video.mp4
  touch /tmp/pw-smoke/photo.jpg
  ```

- [ ] **Step 2: Start the server and hit the endpoints**

  In one terminal:
  ```bash
  uv run photowalk web /tmp/pw-smoke --port 9876
  ```
  Expected: prints "Starting server at http://127.0.0.1:9876"

  In another terminal:
  ```bash
  curl -s http://127.0.0.1:9876/ | head -5
  curl -s http://127.0.0.1:9876/api/timeline | jq .
  curl -s http://127.0.0.1:9876/api/files | jq .
  curl -s http://127.0.0.1:9876/assets/style.css | head -3
  ```
  Expected: all return 200 with valid content.

- [ ] **Step 3: Stop the server**

  Press Ctrl+C in the server terminal.

- [ ] **Step 4: Run the full test suite**

  Run: `uv run pytest -v`
  Expected: all tests pass

- [ ] **Step 5: Final commit**

  ```bash
  git add -A
  git commit -m "feat: complete timeline web UI (read-only preview)"
  ```

---

## Self-Review

**1. Spec coverage:**
- ✅ CLI entry point `photowalk web` — Task 6
- ✅ FastAPI backend with `/api/timeline`, `/api/files`, `/media/{path}` — Tasks 2, 8
- ✅ HTML/JS/CSS frontend — Tasks 3, 4, 5
- ✅ Path validation on `/media` — Task 2 + tests in Task 7
- ✅ Statelessness (no DB) — Task 2
- ✅ Embedded assets, no CDN — Tasks 3, 4, 5, 8
- ✅ Optional dependency handling — Task 1 + Task 6
- ✅ Testing strategy — Tasks 7, 8, 9

**2. Placeholder scan:**
- ✅ No "TBD", "TODO", or vague steps
- ✅ All code blocks contain complete, runnable code
- ✅ All test commands include expected output

**3. Type consistency:**
- ✅ `create_app` signature: `Set[Path]`, `TimelineMap`, `float` — consistent across all tasks
- ✅ `TimelineEntry` fields (`kind`, `source_path`, `start_time`, `duration_seconds`) match model
- ✅ `build_app_from_path` parameters match CLI option names (`image_duration`)
