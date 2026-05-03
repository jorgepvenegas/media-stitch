import subprocess
import sys
from pathlib import Path
from typing import Set

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

from photowalk.catalog import MediaCatalog
from photowalk.timeline import TimelineMap
from photowalk.offset import parse_duration, parse_reference, OffsetError
from photowalk.stitcher import stitch
from photowalk.writers import write_photo_timestamp, write_video_timestamp
from photowalk.web.stitch_models import StitchRequest, StitchStatus
from photowalk.web.sync_models import ApplyRequest, ParseRequest, PreviewRequest
from photowalk.web.session import WebSession, StitchConflictError


def _load_asset(filename: str) -> str:
    vue_dist = Path(__file__).parent / "vue-app" / "dist"
    return (vue_dist / filename).read_text()


def create_app(
    scan_files: Set[Path],
    timeline: TimelineMap,
    image_duration: float = 3.5,
    *,
    catalog: MediaCatalog | None = None,
    scan_path: Path | None = None,
) -> FastAPI:
    app = FastAPI()

    if catalog is None:
        pairs = []
        for f in sorted(scan_files):
            from photowalk.api import extract_metadata
            meta = extract_metadata(f)
            if meta is not None:
                pairs.append((f, meta))
        catalog = MediaCatalog(pairs)

    app.state.session = WebSession(
        catalog=catalog,
        timeline_map=timeline,
        scan_files=scan_files,
        image_duration=image_duration,
        scan_path=scan_path,
    )

    @app.get("/", response_class=HTMLResponse)
    async def index():
        html = _load_asset("index.html")
        return HTMLResponse(content=html)

    @app.get("/assets/{filename}")
    async def asset(filename: str):
        vue_assets = Path(__file__).parent / "vue-app" / "dist" / "assets"
        file_path = vue_assets / filename
        if file_path.exists():
            return FileResponse(file_path)
        raise HTTPException(status_code=404, detail="Asset not found")

    @app.get("/api/timeline")
    async def api_timeline():
        return app.state.session.get_timeline()

    @app.get("/api/files")
    async def api_files():
        return {"files": app.state.session.files}

    @app.get("/media/{path:path}")
    async def media(path: str):
        resolved = Path(path).resolve()
        if not app.state.session.is_allowed_media(resolved):
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(resolved)

    @app.post("/api/offset/parse")
    async def api_offset_parse(req: ParseRequest):
        src = req.root
        try:
            if src.kind == "duration":
                td = parse_duration(src.text)
            else:
                td = parse_reference(f"{src.wrong}={src.correct}")
        except OffsetError as e:
            return {"error": str(e)}

        delta = td.total_seconds()
        if delta == 0.0:
            return {"error": "Offset is zero — nothing to apply"}
        return {"delta_seconds": delta}

    @app.post("/api/timeline/preview")
    async def api_timeline_preview(req: PreviewRequest):
        image_duration = (
            req.image_duration if req.image_duration is not None else None
        )
        return app.state.session.preview(req.offsets, image_duration=image_duration)

    @app.post("/api/sync/apply")
    async def api_sync_apply(req: ApplyRequest):
        return app.state.session.apply(
            req.offsets,
            write_photo=write_photo_timestamp,
            write_video=write_video_timestamp,
        )

    @app.post("/api/stitch")
    async def api_stitch(req: StitchRequest):
        if not req.output.strip():
            raise HTTPException(status_code=422, detail="Output path is required")
        output_path = Path(req.output)
        if not output_path.parent.exists():
            raise HTTPException(status_code=400, detail="Output directory does not exist")

        try:
            job = app.state.session.start_stitch(req, stitch_fn=stitch)
        except StitchConflictError:
            raise HTTPException(status_code=409, detail="A render is already in progress")

        return StitchStatus(
            state="running", message="Stitching...", output_path=req.output
        ).model_dump()

    @app.post("/api/stitch/cancel")
    async def api_stitch_cancel():
        cancelled = app.state.session.cancel_stitch()
        status = app.state.session.stitch_status
        if cancelled:
            return StitchStatus(
                state="cancelled",
                message="Render cancelled",
                output_path=status.output_path,
            ).model_dump()
        return status.model_dump()

    @app.get("/api/stitch/status")
    async def api_stitch_status():
        return app.state.session.stitch_status.model_dump()

    @app.post("/api/open-folder")
    async def api_open_folder(body: dict):
        path = Path(body.get("path", ""))
        if not path.exists():
            raise HTTPException(status_code=400, detail="Path does not exist")
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=False)
            elif sys.platform == "win32":
                subprocess.run(["explorer", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except Exception:
            pass  # Best-effort
        return {"ok": True}

    return app


def build_app_from_path(
    path: Path,
    recursive: bool = False,
    image_duration: float = 3.5,
) -> FastAPI:
    from photowalk.collector import collect_files
    from photowalk.timeline import build_timeline

    path = path.resolve()
    files = collect_files([path], recursive=recursive)
    scan_files = set(files)
    catalog = MediaCatalog.scan([path], recursive=recursive)
    timeline = catalog.timeline()
    app = create_app(
        scan_files, timeline, image_duration, catalog=catalog, scan_path=path
    )
    app.state.media_count = len(files)
    return app
