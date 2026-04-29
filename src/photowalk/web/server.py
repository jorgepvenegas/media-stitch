import subprocess
from pathlib import Path
from typing import Set

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

from photowalk.api import extract_metadata
from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.timeline import TimelineMap
from photowalk.offset import parse_duration, parse_reference, OffsetError
from photowalk.web.file_entry import metadata_to_file_entry
from photowalk.web.sync_apply import apply_offsets
from photowalk.web.sync_models import ApplyRequest, ParseRequest, PreviewRequest
from photowalk.web.sync_preview import build_preview
from photowalk.stitcher import stitch
from photowalk.writers import write_photo_timestamp, write_video_timestamp
from photowalk.web.stitch_models import StitchRequest, StitchStatus
from photowalk.web.stitch_runner import start_stitch, cancel_stitch, StitchJob


def _load_asset(filename: str) -> str:
    asset_dir = Path(__file__).parent / "assets"
    return (asset_dir / filename).read_text()


def create_app(
    scan_files: Set[Path],
    timeline: TimelineMap,
    image_duration: float = 3.5,
    *,
    file_list: "list[dict] | None" = None,
    metadata_pairs: "list[tuple[Path, object]] | None" = None,
) -> FastAPI:
    """Create the FastAPI application.

    Args:
        scan_files: Set of media file paths that are allowed to be served.
        timeline: Pre-built timeline to expose via /api/timeline.
        image_duration: Default display duration (seconds) for image entries.
        file_list: Optional pre-built list of file metadata dicts (same shape
            as /api/files response).  When provided, ``extract_metadata`` is
            NOT called again — callers that have already extracted metadata
            (e.g. ``build_app_from_path``) pass it here to avoid double I/O.
        metadata_pairs: Optional list of (Path, metadata) tuples for use by
            endpoints like preview/apply that need the original metadata objects.
    """
    app = FastAPI()
    app.state.metadata_pairs = metadata_pairs or []
    app.state.image_duration = image_duration
    app.state.scan_files = scan_files

    def _serialize_timeline(tl: TimelineMap) -> dict:
        entries = []
        for entry in tl.all_entries:
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

    app.state.timeline_response = _serialize_timeline(timeline)

    if file_list is not None:
        app.state.file_list = file_list
    else:
        _file_list: list[dict] = []
        for _path in sorted(scan_files):
            _meta = extract_metadata(_path)
            if _meta is None:
                continue
            _file_list.append(metadata_to_file_entry(_path, _meta))
        app.state.file_list = _file_list
    app.state.timeline_map = timeline
    app.state.stitch_job: StitchJob | None = None

    @app.get("/", response_class=HTMLResponse)
    async def index():
        html = _load_asset("index.html")
        return HTMLResponse(content=html)

    @app.get("/assets/{filename}")
    async def asset(filename: str):
        allowed = {"style.css", "app.js", "index.html"}
        if filename not in allowed:
            raise HTTPException(status_code=404, detail="Asset not found")
        content = _load_asset(filename)
        media_type = "text/css" if filename.endswith(".css") else "application/javascript" if filename.endswith(".js") else "text/html"
        return HTMLResponse(content=content, media_type=media_type)

    @app.get("/api/timeline")
    async def api_timeline():
        return app.state.timeline_response

    @app.get("/api/files")
    async def api_files():
        return {"files": app.state.file_list}

    @app.get("/media/{path:path}")
    async def media(path: str):
        resolved = Path(path).resolve()
        if resolved not in scan_files:
            raise HTTPException(status_code=404, detail="File not found")
        if not resolved.exists():
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
        return build_preview(
            app.state.metadata_pairs,
            req.offsets,
            image_duration=app.state.image_duration,
        )

    @app.post("/api/sync/apply")
    async def api_sync_apply(req: ApplyRequest):
        result = apply_offsets(
            app.state.metadata_pairs,
            req.offsets,
            write_photo=write_photo_timestamp,
            write_video=write_video_timestamp,
        )

        refreshed_pairs: list = []
        for path in sorted(app.state.scan_files):
            meta = extract_metadata(path)
            if meta is not None:
                refreshed_pairs.append((path, meta))
        app.state.metadata_pairs = refreshed_pairs

        preview = build_preview(refreshed_pairs, [], image_duration=app.state.image_duration)
        timeline_response = {"entries": preview["entries"], "settings": preview["settings"]}
        app.state.file_list = preview["files"]
        app.state.timeline_response = timeline_response

        return {
            "applied": result["applied"],
            "failed": result["failed"],
            "files": preview["files"],
            "timeline": timeline_response,
        }

    @app.post("/api/stitch")
    async def api_stitch(req: StitchRequest):
        if not req.output.strip():
            raise HTTPException(status_code=422, detail="Output path is required")
        output_path = Path(req.output)
        if not output_path.parent.exists():
            raise HTTPException(status_code=400, detail="Output directory does not exist")

        if app.state.stitch_job is not None and app.state.stitch_job.state == "running":
            raise HTTPException(status_code=409, detail="A render is already in progress")

        job = start_stitch(app.state.timeline_map, req, stitch_fn=stitch)
        app.state.stitch_job = job
        return StitchStatus(state="running", message="Stitching...", output_path=req.output).model_dump()

    @app.post("/api/stitch/cancel")
    async def api_stitch_cancel():
        job = app.state.stitch_job
        if job is not None and job.state == "running":
            cancel_stitch(job)
            return StitchStatus(
                state="cancelled",
                message="Render cancelled",
                output_path=str(job.output_path) if job.output_path else None,
            ).model_dump()
        return StitchStatus(state="idle", message="No render in progress").model_dump()

    @app.get("/api/stitch/status")
    async def api_stitch_status():
        job = app.state.stitch_job
        if job is None:
            return StitchStatus(state="idle", message="No render in progress").model_dump()
        return StitchStatus(
            state=job.state,  # type: ignore[arg-type]
            message=job.message,
            output_path=str(job.output_path) if job.output_path else None,
        ).model_dump()

    @app.post("/api/open-folder")
    async def api_open_folder(body: dict):
        import sys
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
    from photowalk.api import extract_metadata
    from photowalk.timeline import build_timeline

    files = collect_files([path], recursive=recursive)
    scan_files = set(files)

    # Extract metadata once; reuse for both timeline building and /api/files.
    pairs = []
    prebuilt_file_list: list[dict] = []
    for f in sorted(files):
        meta = extract_metadata(f)
        if meta is None:
            continue
        pairs.append((f, meta))
        prebuilt_file_list.append(metadata_to_file_entry(f, meta))

    timeline = build_timeline(pairs)
    app = create_app(
        scan_files, timeline, image_duration, file_list=prebuilt_file_list, metadata_pairs=pairs
    )
    app.state.media_count = len(files)
    return app
