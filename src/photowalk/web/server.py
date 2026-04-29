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
