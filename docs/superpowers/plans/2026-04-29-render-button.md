# Render Button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Render" button to the Photo Walk web UI that triggers the video stitcher with configurable settings, shows a blocking progress modal, and supports cancellation.

**Architecture:** Add optional `cancel_event` threading support to the existing stitch pipeline (`image_clip.py`, `stitcher.py`), then build a thin async runner (`stitch_runner.py`) and FastAPI endpoints (`server.py`), and wire the frontend modal with polling.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic, vanilla JS, CSS. Uses existing `subprocess.Popen` + poll pattern for cancellable ffmpeg.

---

## File Map

| File | Responsibility |
|------|----------------|
| `src/photowalk/ffmpeg_config.py` | New `_run_ffmpeg_cmd` helper with optional `cancel_event` |
| `src/photowalk/image_clip.py` | Pass `cancel_event` through to new helper |
| `src/photowalk/stitcher.py` | Pass `cancel_event` through stitch → split/concat/clip helpers |
| `src/photowalk/web/stitch_models.py` | `StitchRequest` and `StitchStatus` Pydantic models |
| `src/photowalk/web/stitch_runner.py` | `StitchJob`, `start_stitch`, `cancel_stitch` orchestrator |
| `src/photowalk/web/server.py` | `POST /api/stitch`, `POST /api/stitch/cancel`, `GET /api/stitch/status`, `POST /api/open-folder` |
| `src/photowalk/web/assets/index.html` | Render button + render modal markup |
| `src/photowalk/web/assets/style.css` | Render modal + spinner styles |
| `src/photowalk/web/assets/app.js` | Render button wiring, modal form, polling, cancellation |
| `tests/test_ffmpeg_config.py` | Tests for `_run_ffmpeg_cmd` helper |
| `tests/test_image_clip.py` | Tests for `cancel_event` in `generate_image_clip` |
| `tests/test_stitcher.py` | Tests for `cancel_event` in `stitch`, `_split_video_segment`, `run_concat` |
| `tests/test_web_stitch.py` | Tests for stitch endpoints and runner |

---

## Task 1: Add `_run_ffmpeg_cmd` helper to `ffmpeg_config.py`

**Files:**
- Modify: `src/photowalk/ffmpeg_config.py`
- Test: `tests/test_ffmpeg_config.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ffmpeg_config.py`:

```python
import threading
import time
from unittest.mock import patch, MagicMock

from photowalk.ffmpeg_config import _run_ffmpeg_cmd, ffmpeg_not_found_error


def test_run_ffmpeg_cmd_success():
    with patch("photowalk.ffmpeg_config.subprocess.Popen") as mock_popen:
        proc = MagicMock()
        proc.wait.side_effect = [None, None]  # first wait(timeout=0.5) returns None
        proc.poll.return_value = 0  # then poll says done
        proc.returncode = 0
        mock_popen.return_value = proc

        result = _run_ffmpeg_cmd(["ffmpeg", "-version"])
        assert result is True


def test_run_ffmpeg_cmd_failure():
    with patch("photowalk.ffmpeg_config.subprocess.Popen") as mock_popen:
        proc = MagicMock()
        proc.wait.side_effect = [None, None]
        proc.poll.return_value = 1
        proc.returncode = 1
        mock_popen.return_value = proc

        result = _run_ffmpeg_cmd(["ffmpeg", "-version"])
        assert result is False


def test_run_ffmpeg_cmd_cancelled():
    with patch("photowalk.ffmpeg_config.subprocess.Popen") as mock_popen:
        proc = MagicMock()
        # Simulate a slow process: first wait times out, then we cancel
        proc.wait.side_effect = [
            type("TE", (), {"__class__": TimeoutError})(),  # TimeoutExpired
            None,
        ]
        proc.poll.return_value = None  # still running after first timeout
        proc.terminate.return_value = None
        mock_popen.return_value = proc

        cancel_event = threading.Event()
        cancel_event.set()

        result = _run_ffmpeg_cmd(["ffmpeg", "-version"], cancel_event=cancel_event)
        assert result is False
        proc.terminate.assert_called_once()


def test_run_ffmpeg_cmd_missing_ffmpeg():
    with patch("photowalk.ffmpeg_config.subprocess.Popen", side_effect=FileNotFoundError):
        try:
            _run_ffmpeg_cmd(["ffmpeg", "-version"])
            assert False, "Expected RuntimeError"
        except RuntimeError as e:
            assert "ffmpeg" in str(e).lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_ffmpeg_config.py -v
```

Expected: `FAILED` — `_run_ffmpeg_cmd` not defined.

- [ ] **Step 3: Implement `_run_ffmpeg_cmd`**

Add to `src/photowalk/ffmpeg_config.py` **before** the existing `build_scale_pad_filter` function (after `ffmpeg_not_found_error`):

```python
import subprocess
import threading
import time


def _run_ffmpeg_cmd(cmd: list[str], cancel_event: threading.Event | None = None) -> bool:
    """Run an ffmpeg command with optional cancellation via threading.Event.

    Returns True if the command exits with code 0, False otherwise.
    Raises RuntimeError if ffmpeg is not found.
    """
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        raise RuntimeError(ffmpeg_not_found_error())

    while True:
        try:
            proc.wait(timeout=0.5)
            break
        except subprocess.TimeoutExpired:
            if cancel_event is not None and cancel_event.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                return False

    return proc.returncode == 0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_ffmpeg_config.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/ffmpeg_config.py tests/test_ffmpeg_config.py
git commit -m "feat: add cancellable ffmpeg command runner"
```

---

## Task 2: Wire `cancel_event` into `image_clip.py`

**Files:**
- Modify: `src/photowalk/image_clip.py`
- Test: `tests/test_image_clip.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_image_clip.py`:

```python
import threading
from unittest.mock import patch, MagicMock


def test_generate_image_clip_cancelled_before_run():
    with patch("photowalk.image_clip.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_img.size = (1920, 1080)
        mock_open.return_value.__enter__.return_value = mock_img

        with patch("photowalk.image_clip._run_ffmpeg_cmd") as mock_run:
            mock_run.return_value = True
            cancel_event = threading.Event()
            cancel_event.set()

            result = generate_image_clip(
                Path("photo.jpg"), Path("clip.mp4"), 1920, 1080,
                cancel_event=cancel_event,
            )

    assert result is False
    mock_run.assert_not_called()


def test_generate_image_clip_passes_cancel_event():
    with patch("photowalk.image_clip.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_img.size = (1920, 1080)
        mock_open.return_value.__enter__.return_value = mock_img

        with patch("photowalk.image_clip._run_ffmpeg_cmd") as mock_run:
            mock_run.return_value = True
            cancel_event = threading.Event()

            result = generate_image_clip(
                Path("photo.jpg"), Path("clip.mp4"), 1920, 1080,
                cancel_event=cancel_event,
            )

    assert result is True
    mock_run.assert_called_once()
    _, kwargs = mock_run.call_args
    assert kwargs["cancel_event"] is cancel_event
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_image_clip.py::test_generate_image_clip_cancelled_before_run tests/test_image_clip.py::test_generate_image_clip_passes_cancel_event -v
```

Expected: `FAILED` — `cancel_event` param not recognized.

- [ ] **Step 3: Implement cancellation in `image_clip.py`**

Replace the function signature and body in `src/photowalk/image_clip.py`:

```python
def generate_image_clip(
    image_path: Path,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    duration: float = 3.5,
    encode_config: FfmpegEncodeConfig | None = None,
    margin: float = 15.0,
    cancel_event: threading.Event | None = None,
) -> bool:
    """Generate a video clip with white background and centered image.

    Args:
        margin: White space percentage on each side (default 15%).
        cancel_event: If set, abort before or during ffmpeg execution.
    """
    if cancel_event is not None and cancel_event.is_set():
        return False

    try:
        with Image.open(image_path) as img:
            img_width, img_height = img.size
    except Exception:
        return False

    scaled_w, scaled_h = compute_scaled_dimensions(img_width, img_height, frame_width, frame_height, margin)

    if encode_config is None:
        encode_config = FfmpegEncodeConfig()

    filter_str = (
        f"color=c=white:s={frame_width}x{frame_height}:d={duration}[bg];"
        f"[0:v]scale={scaled_w}:{scaled_h}[img];"
        f"[bg][img]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2:enable='between(t,0,{duration})'"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-framerate", str(encode_config.fps),
        "-i", str(image_path),
        "-f", "lavfi",
        "-i", f"anullsrc=channel_layout=stereo:sample_rate={encode_config.audio_sample_rate}",
        "-vf", filter_str,
        "-c:v", "libx264",
        "-preset", encode_config.preset,
        "-crf", str(encode_config.crf),
        "-c:a", "aac",
        "-b:a", encode_config.audio_bitrate,
        "-ar", str(encode_config.audio_sample_rate),
        "-r", str(encode_config.fps),
        "-video_track_timescale", str(encode_config.video_track_timescale),
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(output_path),
    ]

    return _run_ffmpeg_cmd(cmd, cancel_event=cancel_event)
```

Also add `import threading` at the top of `src/photowalk/image_clip.py` and update the import from `ffmpeg_config`:

```python
from photowalk.ffmpeg_config import (
    FfmpegEncodeConfig,
    build_scale_pad_filter,
    ffmpeg_not_found_error,
    _run_ffmpeg_cmd,
)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_image_clip.py -v
```

Expected: all PASS (including existing tests — the `_run_ffmpeg_cmd` patch should be compatible).

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/image_clip.py tests/test_image_clip.py
git commit -m "feat: support cancel_event in generate_image_clip"
```

---

## Task 3: Wire `cancel_event` into `stitcher.py`

**Files:**
- Modify: `src/photowalk/stitcher.py`
- Test: `tests/test_stitcher.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_stitcher.py`:

```python
import threading
from unittest.mock import patch, MagicMock


def test_stitch_cancelled_before_any_clip():
    entry = TimelineEntry(
        start_time=datetime(2024, 7, 15, 12, 0, 0),
        duration_seconds=3.5,
        kind="image",
        source_path=Path("photo.jpg"),
    )
    timeline = TimelineMap(standalone_images=[entry], all_entries=[entry])
    cancel_event = threading.Event()
    cancel_event.set()

    with patch("photowalk.stitcher.generate_image_clip") as mock_clip:
        result = stitch(timeline, Path("out.mp4"), 1920, 1080, cancel_event=cancel_event)

    assert result is False
    mock_clip.assert_not_called()


def test_stitch_cancelled_during_clip():
    entry = TimelineEntry(
        start_time=datetime(2024, 7, 15, 12, 0, 0),
        duration_seconds=3.5,
        kind="image",
        source_path=Path("photo.jpg"),
    )
    timeline = TimelineMap(standalone_images=[entry], all_entries=[entry])
    cancel_event = threading.Event()

    def clip_with_cancel(*args, **kwargs):
        if kwargs.get("cancel_event") is cancel_event:
            cancel_event.set()
        return False

    with patch("photowalk.stitcher.generate_image_clip", side_effect=clip_with_cancel):
        result = stitch(timeline, Path("out.mp4"), 1920, 1080, cancel_event=cancel_event)

    assert result is False


def test_run_concat_cancelled():
    cancel_event = threading.Event()
    cancel_event.set()

    with patch("photowalk.stitcher._run_ffmpeg_cmd") as mock_run:
        result = run_concat(Path("list.txt"), Path("out.mp4"), cancel_event=cancel_event)

    assert result is False
    mock_run.assert_not_called()


def test_split_video_segment_cancelled():
    from photowalk.stitcher import _split_video_segment
    cancel_event = threading.Event()
    cancel_event.set()

    with patch("photowalk.stitcher._run_ffmpeg_cmd") as mock_run:
        result = _split_video_segment(
            Path("in.mp4"), 0.0, 5.0, Path("out.mp4"), 640, 480,
            cancel_event=cancel_event,
        )

    assert result is False
    mock_run.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_stitcher.py::test_stitch_cancelled_before_any_clip tests/test_stitcher.py::test_stitch_cancelled_during_clip tests/test_stitcher.py::test_run_concat_cancelled tests/test_stitcher.py::test_split_video_segment_cancelled -v
```

Expected: `FAILED` — `cancel_event` param not recognized.

- [ ] **Step 3: Implement cancellation in `stitcher.py`**

Add `import threading` at the top of `src/photowalk/stitcher.py` and update the `ffmpeg_config` import:

```python
from photowalk.ffmpeg_config import (
    FfmpegEncodeConfig,
    build_scale_pad_filter,
    ffmpeg_not_found_error,
    _run_ffmpeg_cmd,
)
```

Replace `run_concat`:

```python
def run_concat(
    concat_list_path: Path,
    output_path: Path,
    encode_config: FfmpegEncodeConfig | None = None,
    cancel_event: threading.Event | None = None,
) -> bool:
    """Run ffmpeg concat demuxer."""
    if cancel_event is not None and cancel_event.is_set():
        return False
    if encode_config is None:
        encode_config = FfmpegEncodeConfig()
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_path),
        "-c:v", "libx264",
        "-preset", encode_config.preset,
        "-crf", str(encode_config.crf),
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]
    return _run_ffmpeg_cmd(cmd, cancel_event=cancel_event)
```

Replace `_split_video_segment`:

```python
def _split_video_segment(
    video_path: Path,
    trim_start: float,
    trim_end: float,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    encode_config: FfmpegEncodeConfig | None = None,
    cancel_event: threading.Event | None = None,
) -> bool:
    """Extract a segment from a video using ffmpeg trim.

    Re-encodes instead of -c copy to ensure frame-accurate cuts at
    non-keyframe boundaries.
    """
    if cancel_event is not None and cancel_event.is_set():
        return False
    if encode_config is None:
        encode_config = FfmpegEncodeConfig()
    duration = trim_end - trim_start
    vf = build_scale_pad_filter(frame_width, frame_height)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(trim_start),
        "-i", str(video_path),
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", encode_config.preset,
        "-crf", str(encode_config.crf),
        "-c:a", "aac",
        "-b:a", encode_config.audio_bitrate,
        "-ar", str(encode_config.audio_sample_rate),
        "-r", str(encode_config.fps),
        "-video_track_timescale", str(encode_config.video_track_timescale),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]
    return _run_ffmpeg_cmd(cmd, cancel_event=cancel_event)
```

Replace `stitch` signature and its loop body:

```python
def stitch(
    timeline_map: TimelineMap,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    image_duration: float = 3.5,
    keep_temp: bool = False,
    draft: bool = False,
    margin: float = 15.0,
    cancel_event: threading.Event | None = None,
) -> bool:
    """Stitch all segments into a single output video."""
    temp_dir = Path(tempfile.mkdtemp(prefix="photowalk_stitch_"))
    encode_config = _resolve_encode_config(draft)
    if draft:
        frame_width, frame_height = compute_draft_resolution(frame_width, frame_height)
    try:
        for entry in timeline_map.all_entries:
            if cancel_event is not None and cancel_event.is_set():
                return False
            if entry.kind == "image":
                clip_path = temp_dir / f"img_{entry.source_path.stem}.mp4"
                ok = generate_image_clip(
                    entry.source_path,
                    clip_path,
                    frame_width,
                    frame_height,
                    image_duration,
                    encode_config=encode_config,
                    margin=margin,
                    cancel_event=cancel_event,
                )
                if not ok:
                    return False
                entry.clip_path = clip_path
                entry.duration_seconds = image_duration
            elif entry.kind == "video_segment":
                seg_path = temp_dir / f"seg_{entry.trim_start:.3f}_{entry.source_path.stem}.mp4"
                ok = _split_video_segment(
                    entry.source_path,
                    entry.trim_start or 0.0,
                    entry.trim_end or 0.0,
                    seg_path,
                    frame_width,
                    frame_height,
                    encode_config=encode_config,
                    cancel_event=cancel_event,
                )
                if not ok:
                    return False
                entry.clip_path = seg_path

        concat_list_path = temp_dir / "concat_list.txt"
        build_concat_list(timeline_map.all_entries, concat_list_path)
        ok = run_concat(concat_list_path, output_path, encode_config=encode_config, cancel_event=cancel_event)
        return ok
    finally:
        if keep_temp:
            print(f"Temp files preserved at: {temp_dir}")
        else:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_stitcher.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/stitcher.py tests/test_stitcher.py
git commit -m "feat: support cancel_event throughout stitch pipeline"
```

---

## Task 4: Create `stitch_models.py`

**Files:**
- Create: `src/photowalk/web/stitch_models.py`
- Test: `tests/test_web_stitch.py` (first validation tests)

- [ ] **Step 1: Create the models file**

Create `src/photowalk/web/stitch_models.py`:

```python
from typing import Literal

from pydantic import BaseModel, field_validator


class StitchRequest(BaseModel):
    output: str
    format: str | None = None
    draft: bool = False
    image_duration: float = 3.5
    margin: float = 15.0
    open_folder: bool = False

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        parts = v.split("x")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            raise ValueError('Format must be "WIDTHxHEIGHT" (e.g. "1920x1080")')
        return v


class StitchStatus(BaseModel):
    state: Literal["idle", "running", "done", "cancelled", "error"]
    message: str
    output_path: str | None = None
```

- [ ] **Step 2: Write model validation tests**

Create the start of `tests/test_web_stitch.py`:

```python
import pytest
from pydantic import ValidationError

from photowalk.web.stitch_models import StitchRequest, StitchStatus


def test_stitch_request_valid():
    req = StitchRequest(output="/tmp/out.mp4")
    assert req.output == "/tmp/out.mp4"
    assert req.draft is False
    assert req.image_duration == 3.5


def test_stitch_request_format_ok():
    req = StitchRequest(output="/tmp/out.mp4", format="1920x1080")
    assert req.format == "1920x1080"


def test_stitch_request_format_invalid():
    with pytest.raises(ValidationError):
        StitchRequest(output="/tmp/out.mp4", format="abc")


def test_stitch_request_format_partial():
    with pytest.raises(ValidationError):
        StitchRequest(output="/tmp/out.mp4", format="1920x")


def test_stitch_status_serialization():
    status = StitchStatus(state="running", message="Stitching...")
    d = status.model_dump()
    assert d["state"] == "running"
    assert d["message"] == "Stitching..."
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_web_stitch.py -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add src/photowalk/web/stitch_models.py tests/test_web_stitch.py
git commit -m "feat: add StitchRequest and StitchStatus pydantic models"
```

---

## Task 5: Create `stitch_runner.py`

**Files:**
- Create: `src/photowalk/web/stitch_runner.py`
- Test: `tests/test_web_stitch.py` (runner tests)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_web_stitch.py`:

```python
import asyncio
import threading
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from photowalk.timeline import TimelineMap, TimelineEntry
from photowalk.web.stitch_models import StitchRequest
from photowalk.web.stitch_runner import StitchJob, start_stitch, cancel_stitch


def _make_timeline():
    entry = TimelineEntry(
        start_time=datetime(2024, 7, 15, 12, 0, 0),
        duration_seconds=3.5,
        kind="image",
        source_path=Path("/tmp/photo.jpg"),
    )
    return TimelineMap(standalone_images=[entry], all_entries=[entry])


def test_start_stitch_runs_in_background():
    timeline = _make_timeline()
    req = StitchRequest(output="/tmp/out.mp4")

    with patch("photowalk.web.stitch_runner.stitch", return_value=True) as mock_stitch:
        job = start_stitch(timeline, req)
        assert job.state == "running"
        # Wait for async task to complete
        asyncio.get_event_loop().run_until_complete(job.task)

    assert job.state == "done"
    assert job.message == "Render complete"
    assert str(job.output_path) == "/tmp/out.mp4"
    mock_stitch.assert_called_once()


def test_start_stitch_sets_error_on_failure():
    timeline = _make_timeline()
    req = StitchRequest(output="/tmp/out.mp4")

    with patch("photowalk.web.stitch_runner.stitch", return_value=False):
        job = start_stitch(timeline, req)
        asyncio.get_event_loop().run_until_complete(job.task)

    assert job.state == "error"
    assert "failed" in job.message.lower()


def test_start_stitch_sets_error_on_exception():
    timeline = _make_timeline()
    req = StitchRequest(output="/tmp/out.mp4")

    with patch("photowalk.web.stitch_runner.stitch", side_effect=RuntimeError("boom")):
        job = start_stitch(timeline, req)
        asyncio.get_event_loop().run_until_complete(job.task)

    assert job.state == "error"
    assert "boom" in job.message


def test_cancel_stitch_sets_cancelled():
    timeline = _make_timeline()
    req = StitchRequest(output="/tmp/out.mp4")

    def slow_stitch(*args, **kwargs):
        # Simulate work that checks cancel_event
        import time
        for _ in range(20):
            if kwargs.get("cancel_event") and kwargs["cancel_event"].is_set():
                return False
            time.sleep(0.05)
        return True

    with patch("photowalk.web.stitch_runner.stitch", side_effect=slow_stitch):
        job = start_stitch(timeline, req)
        # Give the task a moment to start
        import time
        time.sleep(0.1)
        cancel_stitch(job)
        asyncio.get_event_loop().run_until_complete(job.task)

    assert job.state == "cancelled"
    assert job.cancel_event.is_set()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_web_stitch.py::test_start_stitch_runs_in_background tests/test_web_stitch.py::test_start_stitch_sets_error_on_failure tests/test_web_stitch.py::test_start_stitch_sets_error_on_exception tests/test_web_stitch.py::test_cancel_stitch_sets_cancelled -v
```

Expected: `FAILED` — `stitch_runner` module not found.

- [ ] **Step 3: Implement `stitch_runner.py`**

Create `src/photowalk/web/stitch_runner.py`:

```python
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
    job.task = asyncio.create_task(_run_stitch(timeline_map, request, job))
    return job


def cancel_stitch(job: StitchJob) -> None:
    """Request cancellation of a running stitch job."""
    job.cancel_event.set()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_web_stitch.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/web/stitch_runner.py tests/test_web_stitch.py
git commit -m "feat: add async stitch runner with cancellation"
```

---

## Task 6: Add stitch endpoints to `server.py`

**Files:**
- Modify: `src/photowalk/web/server.py`
- Test: `tests/test_web_stitch.py` (endpoint tests)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_web_stitch.py`:

```python
from fastapi.testclient import TestClient

from photowalk.timeline import TimelineMap, TimelineEntry
from photowalk.web.server import create_app


def _client_with_timeline(timeline):
    app = create_app(set(), timeline)
    return TestClient(app)


def test_api_stitch_validation_empty_output():
    timeline = TimelineMap()
    client = _client_with_timeline(timeline)
    r = client.post("/api/stitch", json={"output": ""})
    assert r.status_code == 422


def test_api_stitch_validation_bad_format():
    timeline = TimelineMap()
    client = _client_with_timeline(timeline)
    r = client.post("/api/stitch", json={"output": "/tmp/out.mp4", "format": "abc"})
    assert r.status_code == 422


def test_api_stitch_starts_job():
    entry = TimelineEntry(
        start_time=datetime(2024, 7, 15, 12, 0, 0),
        duration_seconds=3.5,
        kind="image",
        source_path=Path("/tmp/photo.jpg"),
    )
    timeline = TimelineMap(standalone_images=[entry], all_entries=[entry])
    app = create_app({Path("/tmp/photo.jpg")}, timeline)
    client = TestClient(app)

    with patch("photowalk.web.server.stitch", return_value=True):
        r = client.post("/api/stitch", json={"output": "/tmp/out.mp4"})

    assert r.status_code == 200
    data = r.json()
    assert data["state"] == "running"


def test_api_stitch_conflict_when_running():
    entry = TimelineEntry(
        start_time=datetime(2024, 7, 15, 12, 0, 0),
        duration_seconds=3.5,
        kind="image",
        source_path=Path("/tmp/photo.jpg"),
    )
    timeline = TimelineMap(standalone_images=[entry], all_entries=[entry])
    app = create_app({Path("/tmp/photo.jpg")}, timeline)
    client = TestClient(app)

    # Start first job (mocked to be slow)
    with patch("photowalk.web.server.stitch", side_effect=lambda *a, **k: __import__("time").sleep(1)):
        r1 = client.post("/api/stitch", json={"output": "/tmp/out.mp4"})
        assert r1.status_code == 200

        # Second start should conflict
        r2 = client.post("/api/stitch", json={"output": "/tmp/out2.mp4"})
        assert r2.status_code == 409


def test_api_stitch_status_idle():
    timeline = TimelineMap()
    client = _client_with_timeline(timeline)
    r = client.get("/api/stitch/status")
    assert r.status_code == 200
    assert r.json()["state"] == "idle"


def test_api_stitch_cancel():
    entry = TimelineEntry(
        start_time=datetime(2024, 7, 15, 12, 0, 0),
        duration_seconds=3.5,
        kind="image",
        source_path=Path("/tmp/photo.jpg"),
    )
    timeline = TimelineMap(standalone_images=[entry], all_entries=[entry])
    app = create_app({Path("/tmp/photo.jpg")}, timeline)
    client = TestClient(app)

    def slow_stitch(*args, **kwargs):
        import time
        for _ in range(20):
            if kwargs.get("cancel_event") and kwargs["cancel_event"].is_set():
                return False
            time.sleep(0.05)
        return True

    with patch("photowalk.web.server.stitch", side_effect=slow_stitch):
        client.post("/api/stitch", json={"output": "/tmp/out.mp4"})
        r = client.post("/api/stitch/cancel")
        assert r.status_code == 200
        assert r.json()["state"] in ("cancelled", "running")


def test_api_open_folder():
    timeline = TimelineMap()
    app = create_app(set(), timeline)
    client = TestClient(app)

    with patch("photowalk.web.server.subprocess.run") as mock_run:
        r = client.post("/api/open-folder", json={"path": "/tmp"})
        assert r.status_code == 200
        mock_run.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_web_stitch.py::test_api_stitch_validation_empty_output tests/test_web_stitch.py::test_api_stitch_validation_bad_format tests/test_web_stitch.py::test_api_stitch_starts_job tests/test_web_stitch.py::test_api_stitch_conflict_when_running tests/test_web_stitch.py::test_api_stitch_status_idle tests/test_web_stitch.py::test_api_stitch_cancel tests/test_web_stitch.py::test_api_open_folder -v
```

Expected: `FAILED` — endpoints don't exist.

- [ ] **Step 3: Implement endpoints in `server.py`**

Add imports at the top of `src/photowalk/web/server.py`:

```python
import re
import subprocess

from photowalk.web.stitch_models import StitchRequest, StitchStatus
from photowalk.web.stitch_runner import start_stitch, cancel_stitch, StitchJob
```

In `create_app`, after `app.state.file_list = _file_list`, add:

```python
    app.state.timeline_map = timeline
    app.state.stitch_job: StitchJob | None = None
```

Add these endpoint handlers inside `create_app` (after the existing `/api/sync/apply` endpoint, before the `return app`):

```python
    @app.post("/api/stitch")
    async def api_stitch(req: StitchRequest):
        output_path = Path(req.output)
        if not req.output.strip():
            raise HTTPException(status_code=422, detail="Output path is required")
        if output_path.parent.exists() is False:
            raise HTTPException(status_code=400, detail="Output directory does not exist")

        if app.state.stitch_job is not None and app.state.stitch_job.state == "running":
            raise HTTPException(status_code=409, detail="A render is already in progress")

        job = start_stitch(app.state.timeline_map, req)
        app.state.stitch_job = job
        return StitchStatus(state="running", message="Stitching...", output_path=req.output).model_dump()

    @app.post("/api/stitch/cancel")
    async def api_stitch_cancel():
        job = app.state.stitch_job
        if job is not None and job.state == "running":
            cancel_stitch(job)
            return StitchStatus(state="cancelled", message="Render cancelled", output_path=str(job.output_path) if job.output_path else None).model_dump()
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
        path = Path(body.get("path", ""))
        if not path.exists():
            raise HTTPException(status_code=400, detail="Path does not exist")

        import sys
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_web_stitch.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/web/server.py tests/test_web_stitch.py
git commit -m "feat: add stitch endpoints and open-folder endpoint to web server"
```

---

## Task 7: Add render button and modal to `index.html`

**Files:**
- Modify: `src/photowalk/web/assets/index.html`

- [ ] **Step 1: Add Render button**

In `src/photowalk/web/assets/index.html`, find this sync panel button row:

```html
      <div class="sync-row">
        <button id="btn-update-timeline" type="button" disabled>Update timeline</button>
        <button id="btn-clear-queue" type="button" disabled>Clear queue</button>
        <button id="btn-apply" type="button" disabled>Apply</button>
      </div>
```

Replace it with:

```html
      <div class="sync-row">
        <button id="btn-update-timeline" type="button" disabled>Update timeline</button>
        <button id="btn-clear-queue" type="button" disabled>Clear queue</button>
        <button id="btn-apply" type="button" disabled>Apply</button>
        <button id="btn-render" type="button">Render</button>
      </div>
```

- [ ] **Step 2: Add render modal markup**

After the existing `apply-modal` div and before the `toast` div, add:

```html
  <div id="render-modal" class="modal" style="display:none;">
    <div class="modal-content">
      <div id="render-form">
        <h3>Render Video</h3>
        <p class="render-confirm-text">
          This will generate a stitched video from the current timeline.
          The process may take several minutes.
        </p>
        <div class="render-field">
          <label>Output path</label>
          <input type="text" id="render-output" placeholder="/path/to/output.mp4">
        </div>
        <div class="render-field">
          <label>Resolution (optional)</label>
          <input type="text" id="render-format" placeholder="1920x1080">
        </div>
        <div class="render-field row">
          <label>Draft quality</label>
          <input type="checkbox" id="render-draft">
        </div>
        <div class="render-field">
          <label>Image duration (seconds)</label>
          <input type="number" id="render-image-duration" value="3.5" step="0.1" min="0.1">
        </div>
        <div class="render-field">
          <label>Margin (%)</label>
          <input type="number" id="render-margin" value="15" step="1" min="0">
        </div>
        <div class="render-field row">
          <label>Open output folder when done</label>
          <input type="checkbox" id="render-open-folder">
        </div>
        <div class="modal-actions">
          <button id="btn-render-cancel" type="button">Cancel</button>
          <button id="btn-render-start" type="button">Start Render</button>
        </div>
      </div>
      <div id="render-progress" style="display:none;">
        <div class="render-spinner"></div>
        <p class="render-status">Stitching...</p>
        <button id="btn-render-cancel-run" type="button">Cancel</button>
      </div>
    </div>
  </div>
```

- [ ] **Step 3: Commit**

```bash
git add src/photowalk/web/assets/index.html
git commit -m "feat: add render button and modal markup"
```

---

## Task 8: Add render modal styles to `style.css`

**Files:**
- Modify: `src/photowalk/web/assets/style.css`

- [ ] **Step 1: Add CSS**

Add to the end of `src/photowalk/web/assets/style.css`:

```css
/* Render modal */
.render-confirm-text { color: #888; font-size: 0.85rem; margin-bottom: 12px; }
.render-field { margin-bottom: 10px; }
.render-field label { display: block; font-size: 0.8rem; color: #888; margin-bottom: 2px; }
.render-field input[type="text"],
.render-field input[type="number"] {
  width: 100%;
  background: #0f0f1a;
  border: 1px solid #333;
  color: #e0e0e0;
  padding: 4px 8px;
  font-family: monospace;
}
.render-field.row { display: flex; align-items: center; gap: 8px; }
.render-field.row label { margin-bottom: 0; flex: 1; }
.render-field.row input[type="checkbox"] { cursor: pointer; }

.render-spinner {
  width: 40px; height: 40px;
  border: 3px solid #333;
  border-top-color: #4a90d9;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 12px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.render-status { text-align: center; color: #e0e0e0; }
#render-progress { text-align: center; padding: 20px; }
```

- [ ] **Step 2: Commit**

```bash
git add src/photowalk/web/assets/style.css
git commit -m "feat: add render modal styles"
```

---

## Task 9: Wire render logic in `app.js`

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Add render state and wiring**

Add this block to `app.js` immediately after the existing state declarations (after `let originalFilesByPath = {};`):

```javascript
  let renderPollInterval = null;
```

- [ ] **Step 2: Bind render handlers in `bindSyncPanel`**

Inside `bindSyncPanel()`, add these listeners after the existing apply modal listeners:

```javascript
    document.getElementById('btn-render').addEventListener('click', openRenderModal);
    document.getElementById('btn-render-cancel').addEventListener('click', closeRenderModal);
    document.getElementById('btn-render-start').addEventListener('click', startRender);
    document.getElementById('btn-render-cancel-run').addEventListener('click', cancelRender);
```

- [ ] **Step 3: Add render functions**

Add these functions to `app.js` after the existing `confirmApply` function (before the final `})();`):

```javascript
  function openRenderModal() {
    document.getElementById('render-output').value = '';
    document.getElementById('render-format').value = '';
    document.getElementById('render-draft').checked = false;
    document.getElementById('render-image-duration').value = String(app.state.image_duration || 3.5);
    document.getElementById('render-margin').value = '15';
    document.getElementById('render-open-folder').checked = false;
    document.getElementById('render-form').style.display = '';
    document.getElementById('render-progress').style.display = 'none';
    document.getElementById('render-modal').style.display = '';
  }

  function closeRenderModal() {
    document.getElementById('render-modal').style.display = 'none';
    if (renderPollInterval) {
      clearInterval(renderPollInterval);
      renderPollInterval = null;
    }
  }

  async function startRender() {
    const output = document.getElementById('render-output').value.trim();
    if (!output) {
      showToast('Output path is required', { error: true });
      return;
    }

    const format = document.getElementById('render-format').value.trim() || null;
    const draft = document.getElementById('render-draft').checked;
    const imageDuration = parseFloat(document.getElementById('render-image-duration').value);
    const margin = parseFloat(document.getElementById('render-margin').value);
    const openFolder = document.getElementById('render-open-folder').checked;

    const body = {
      output,
      format,
      draft,
      image_duration: imageDuration,
      margin,
      open_folder: openFolder,
    };

    let res;
    try {
      res = await fetch('/api/stitch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } catch (e) {
      showToast('Failed to start render', { error: true });
      return;
    }

    if (res.status === 409) {
      showToast('A render is already in progress', { error: true });
      return;
    }
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      showToast(data.detail || 'Failed to start render', { error: true });
      return;
    }

    document.getElementById('render-form').style.display = 'none';
    document.getElementById('render-progress').style.display = '';

    renderPollInterval = setInterval(pollRenderStatus, 1000);
  }

  async function pollRenderStatus() {
    let res;
    try {
      res = await fetch('/api/stitch/status');
    } catch (e) {
      return;
    }

    if (!res.ok) return;
    const data = await res.json();

    if (data.state === 'running') {
      document.querySelector('.render-status').textContent = data.message || 'Stitching...';
      return;
    }

    clearInterval(renderPollInterval);
    renderPollInterval = null;

    if (data.state === 'done') {
      const openFolder = document.getElementById('render-open-folder').checked;
      if (openFolder && data.output_path) {
        const dir = data.output_path.split('/').slice(0, -1).join('/') || '.';
        fetch('/api/open-folder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: dir }),
        }).catch(() => {});
      }
      showToast('Render complete');
      closeRenderModal();
    } else if (data.state === 'cancelled') {
      showToast('Render cancelled');
      closeRenderModal();
    } else if (data.state === 'error') {
      showToast(data.message || 'Render failed', { error: true, sticky: true });
      closeRenderModal();
    }
  }

  async function cancelRender() {
    try {
      await fetch('/api/stitch/cancel', { method: 'POST' });
    } catch (e) {
      showToast('Failed to cancel render', { error: true });
    }
  }
```

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all PASS (frontend has no automated tests in this suite, but backend should all pass).

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat: wire render button with modal, polling, and cancellation"
```

---

## Task 10: Final verification

- [ ] **Step 1: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 2: Manual frontend checklist**

Start the server and verify:

```bash
uv run photowalk web /path/to/photos --port 8080
```

1. Click **Render** → modal opens with image_duration pre-filled from app state.
2. Enter output path, adjust settings, click **Start Render** → progress overlay shows with spinner.
3. Click **Cancel** during run → status becomes cancelled, modal closes, toast appears.
4. Start another render, let it complete → toast "Render complete", folder opens if checkbox checked.
5. Try starting a second render while one is running → toast "A render is already in progress".

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete render button with stitch trigger, progress modal, and cancellation"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Render button in sync panel → Task 7
- [x] Popover modal with confirmation → Task 7
- [x] Output path input → Task 7, 9
- [x] Resolution, draft, image_duration, margin inputs → Task 7, 9
- [x] "Open output folder when done" checkbox → Task 7, 9
- [x] Progress overlay with spinner → Task 7, 8
- [x] Cancel button during run → Task 9
- [x] UI blocked during stitching → existing `.modal` CSS backdrop
- [x] Backend cancellation via threading.Event → Tasks 1-3
- [x] Single concurrent job limit → Task 6
- [x] Status polling endpoint → Task 6
- [x] Open folder endpoint → Task 6

**Placeholder scan:** No TBD, TODO, or vague requirements found.

**Type consistency:**
- `cancel_event: threading.Event | None` used consistently across `ffmpeg_config.py`, `image_clip.py`, `stitcher.py`
- `StitchRequest` and `StitchStatus` field names match endpoint usage in `server.py` and frontend JS
- `job.state` values (`idle`/`running`/`done`/`cancelled`/`error`) match `StitchStatus` Literal
