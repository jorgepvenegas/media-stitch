import asyncio
import threading
from dataclasses import dataclass, field
from pathlib import Path

from photowalk.stitcher import stitch
from photowalk.timeline import TimelineMap
from photowalk.web.stitch_models import StitchRequest


@dataclass
class StitchJob:
    task: asyncio.Task
    cancel_event: threading.Event
    state: str = "running"
    message: str = ""
    output_path: Path | None = None


async def _run_stitch(
    timeline_map: TimelineMap,
    request: StitchRequest,
    job: StitchJob,
) -> None:
    """Run stitch in a thread and update job state."""
    output_path = Path(request.output)
    job.output_path = output_path

    frame_width, frame_height = 1920, 1080
    if request.format:
        frame_width, frame_height = map(int, request.format.split("x"))

    loop = asyncio.get_running_loop()

    def _thread_target():
        try:
            ok = stitch(
                timeline_map,
                output_path,
                frame_width,
                frame_height,
                image_duration=request.image_duration,
                draft=request.draft,
                margin=request.margin,
                cancel_event=job.cancel_event,
            )
            if job.cancel_event.is_set():
                job.state = "cancelled"
                job.message = "Render cancelled"
            elif ok:
                job.state = "done"
                job.message = "Render complete"
            else:
                job.state = "error"
                job.message = "Stitching failed"
        except Exception as e:
            job.state = "error"
            job.message = str(e)

    try:
        await loop.run_in_executor(None, _thread_target)
    except Exception as e:
        job.state = "error"
        job.message = str(e)


def start_stitch(timeline_map: TimelineMap, request: StitchRequest) -> StitchJob:
    """Start a stitch job asynchronously."""
    cancel_event = threading.Event()
    job = StitchJob(
        task=None,  # type: ignore[arg-type]
        cancel_event=cancel_event,
        state="running",
        message="Stitching...",
        output_path=Path(request.output),
    )
    job.task = asyncio.ensure_future(_run_stitch(timeline_map, request, job))
    return job


def cancel_stitch(job: StitchJob) -> None:
    """Request cancellation of a running stitch job."""
    job.cancel_event.set()
