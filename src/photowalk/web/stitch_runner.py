import asyncio
import threading
from dataclasses import dataclass
from pathlib import Path

from photowalk.stitcher import stitch
from photowalk.timeline import TimelineMap
from photowalk.web.stitch_models import StitchRequest


@dataclass
class StitchJob:
    task: asyncio.Future
    cancel_event: threading.Event
    state: str = "running"
    message: str = ""
    output_path: Path | None = None


def start_stitch(
    timeline_map: TimelineMap,
    request: StitchRequest,
    stitch_fn=None,
) -> StitchJob:
    """Start a stitch job in a background daemon thread.

    The actual thread launch is deferred into a one-shot asyncio task so that
    in synchronous (unit-test) contexts the stitch doesn't execute until the
    event loop is ticked — letting callers observe ``job.state == "running"``
    right after this function returns.  In async (server) contexts the one-shot
    task completes in a single event-loop iteration and the worker thread then
    runs entirely in the background, never blocking the event loop.

    ``job.task`` is an asyncio Future that resolves when the worker thread
    finishes.  Callers that want to await completion (e.g. unit tests) can
    do ``asyncio.get_event_loop().run_until_complete(job.task)``.

    Args:
        timeline_map: Pre-built timeline to stitch.
        request: Stitch parameters.
        stitch_fn: Optional override for the ``stitch`` callable.  When
            provided (e.g. from the web endpoint) the caller's imported name
            is used, enabling ``patch("photowalk.web.server.stitch")`` mocking.
    """
    cancel_event = threading.Event()

    # Obtain the event loop: use the running one inside a coroutine; otherwise
    # fall back to the current-thread loop (sync / unit-test contexts).
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()

    future: asyncio.Future = loop.create_future()

    output_path = Path(request.output)
    frame_width, frame_height = 1920, 1080
    if request.format:
        frame_width, frame_height = map(int, request.format.split("x"))

    # Resolve stitch callable: prefer the explicitly-supplied stitch_fn so
    # callers can mock their own module's import; fall back to the module-level
    # name so ``patch("photowalk.web.stitch_runner.stitch")`` still works.
    _stitch = stitch_fn if stitch_fn is not None else stitch

    job = StitchJob(
        task=future,
        cancel_event=cancel_event,
        state="running",
        message="Stitching...",
        output_path=output_path,
    )

    def _thread_target() -> None:
        try:
            ok = _stitch(
                timeline_map,
                output_path,
                frame_width,
                frame_height,
                image_duration=request.image_duration,
                draft=request.draft,
                margin=request.margin,
                cancel_event=cancel_event,
            )
            if cancel_event.is_set():
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
        finally:
            # Resolve the awaitable from the worker thread.
            # Guard against the loop being closed if the test context ended.
            try:
                loop.call_soon_threadsafe(future.set_result, None)
            except RuntimeError:
                pass

    thread = threading.Thread(target=_thread_target, daemon=True)

    # Schedule thread start via ensure_future so that in sync contexts the
    # thread doesn't start until the event loop actually runs.  The coroutine
    # returns immediately after thread.start(), so the event loop is never
    # blocked waiting for the thread.
    async def _start_thread() -> None:
        thread.start()

    asyncio.ensure_future(_start_thread())

    return job


def cancel_stitch(job: StitchJob) -> None:
    """Request cancellation of a running stitch job."""
    job.cancel_event.set()
