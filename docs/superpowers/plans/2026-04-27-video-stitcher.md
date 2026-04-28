# Video Stitcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `photowalk stitch` command that composes a single output video from a directory of photos and videos, inserting white-background image clips at their filmed-at timestamps.

**Architecture:** Three-phase pipeline: (1) `timeline.py` scans a directory and builds a sorted timeline map of videos and images; (2) `image_clip.py` generates 3.5-second white-background video clips from each photo; (3) `stitcher.py` splits videos at image insertion points, builds an ffmpeg concat list, and assembles the final output.

**Tech Stack:** Python 3.10+, click, Pillow, ffmpeg, pytest. Follows existing photowalk patterns: mock `subprocess.run` for ffmpeg tests, use `CliRunner` for CLI tests.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/photowalk/timeline.py` | Scan directory, extract metadata, build `TimelineMap`, associate inline images with videos |
| `src/photowalk/image_clip.py` | Compute scaled image dimensions and generate white-background clips via ffmpeg |
| `src/photowalk/stitcher.py` | Split videos, build concat list, run final ffmpeg concat demuxer |
| `src/photowalk/cli.py` | Add `stitch` subcommand, wire modules together |
| `tests/test_timeline.py` | Unit tests for timeline building and image/video association |
| `tests/test_image_clip.py` | Unit tests for scaling math and ffmpeg clip generation |
| `tests/test_stitcher.py` | Unit tests for video splitting, concat list building, and assembly |
| `tests/test_cli_stitch.py` | CLI integration tests using Click's CliRunner |

---

## Existing Patterns to Follow

- **Mock subprocess:** Use `@patch("photowalk.image_clip.subprocess.run")` or `@patch("photowalk.stitcher.subprocess.run")` — never shell out in tests.
- **CLI tests:** Use `CliRunner().isolated_filesystem()`, create empty files with `Path("file.mp4").touch()`, and mock `extract_metadata` or `subprocess.run` as needed.
- **Error handling:** Missing ffmpeg → `RuntimeError` with clear message. Missing timestamps → skip with warning. CLI errors → `click.echo(click.style(..., fg="red"), err=True)` + `raise click.Exit(1)`.
- **Dataclasses:** Use frozen dataclasses with `to_dict()` for JSON serialization (follow `models.py`).

---

## Shared Types

These go in `src/photowalk/timeline.py` and are imported by `image_clip.py` and `stitcher.py`:

```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Literal


@dataclass
class TimelineEntry:
    start_time: datetime
    duration_seconds: float
    kind: Literal["video", "image", "video_segment"]
    source_path: Path
    clip_path: Optional[Path] = None
    original_video: Optional[Path] = None
    trim_start: Optional[float] = None
    trim_end: Optional[float] = None


@dataclass
class VideoTimeline:
    video_path: Path
    video_start: datetime
    video_end: datetime
    segments: List[TimelineEntry] = field(default_factory=list)


@dataclass
class TimelineMap:
    video_timelines: List[VideoTimeline] = field(default_factory=list)
    standalone_images: List[TimelineEntry] = field(default_factory=list)
    all_entries: List[TimelineEntry] = field(default_factory=list)
```

---

### Task 1: Timeline Builder (`timeline.py`)

**Files:**
- Create: `src/photowalk/timeline.py`
- Test: `tests/test_timeline.py`

**Description:** Scan a directory, extract metadata from all photos/videos, build a sorted timeline. For each video, identify images whose timestamp falls within `[video_start, video_end]`. Images outside all video ranges are standalone.

- [ ] **Step 1: Write the failing test — build timeline with one video and one inline image**

```python
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from photowalk.timeline import build_timeline
from photowalk.models import PhotoMetadata, VideoMetadata


def test_build_timeline_inline_image():
    video_meta = VideoMetadata(
        source_path=Path("video.mp4"),
        start_timestamp=datetime(2024, 7, 15, 12, 0, 0),
        end_timestamp=datetime(2024, 7, 15, 12, 2, 0),
        duration_seconds=120.0,
    )
    photo_meta = PhotoMetadata(
        source_path=Path("photo.jpg"),
        timestamp=datetime(2024, 7, 15, 12, 0, 30),
    )

    with patch("photowalk.timeline.extract_metadata", side_effect=[video_meta, photo_meta]):
        result = build_timeline([Path("video.mp4"), Path("photo.jpg")])

    assert len(result.video_timelines) == 1
    vt = result.video_timelines[0]
    assert vt.video_path == Path("video.mp4")
    assert len(vt.segments) == 3
    assert vt.segments[0].kind == "video_segment"
    assert vt.segments[1].kind == "image"
    assert vt.segments[1].source_path == Path("photo.jpg")
    assert vt.segments[2].kind == "video_segment"
    assert result.standalone_images == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_timeline.py::test_build_timeline_inline_image -v`
Expected: FAIL — `build_timeline` not defined

- [ ] **Step 3: Write implementation**

Create `src/photowalk/timeline.py` with the shared types above plus:

```python
def _make_video_segments(
    video_path: Path,
    video_start: datetime,
    duration_seconds: float,
    inline_images: List[TimelineEntry],
) -> List[TimelineEntry]:
    segments: List[TimelineEntry] = []
    current_offset = 0.0

    for img in sorted(inline_images, key=lambda e: e.start_time):
        img_offset = (img.start_time - video_start).total_seconds()
        if img_offset > current_offset:
            segments.append(
                TimelineEntry(
                    start_time=video_start + timedelta(seconds=current_offset),
                    duration_seconds=img_offset - current_offset,
                    kind="video_segment",
                    source_path=video_path,
                    original_video=video_path,
                    trim_start=current_offset,
                    trim_end=img_offset,
                )
            )
        segments.append(img)
        current_offset = img_offset

    if current_offset < duration_seconds:
        segments.append(
            TimelineEntry(
                start_time=video_start + timedelta(seconds=current_offset),
                duration_seconds=duration_seconds - current_offset,
                kind="video_segment",
                source_path=video_path,
                original_video=video_path,
                trim_start=current_offset,
                trim_end=duration_seconds,
            )
        )

    return segments


def build_timeline(files: List[Path]) -> TimelineMap:
    photos: List[TimelineEntry] = []
    videos: List[VideoTimeline] = []

    for f in files:
        meta = extract_metadata(f)
        if meta is None:
            continue

        if isinstance(meta, PhotoMetadata) and meta.timestamp is not None:
            photos.append(
                TimelineEntry(
                    start_time=meta.timestamp,
                    duration_seconds=0.0,
                    kind="image",
                    source_path=f,
                )
            )
        elif isinstance(meta, VideoMetadata) and meta.start_timestamp is not None and meta.duration_seconds is not None:
            videos.append(
                VideoTimeline(
                    video_path=f,
                    video_start=meta.start_timestamp,
                    video_end=meta.end_timestamp or meta.start_timestamp + timedelta(seconds=meta.duration_seconds),
                )
            )

    videos.sort(key=lambda v: v.video_start)

    standalone: List[TimelineEntry] = []
    for img in sorted(photos, key=lambda p: p.start_time):
        placed = False
        for vt in videos:
            if vt.video_start <= img.start_time <= vt.video_end:
                vt.segments.append(img)
                placed = True
                break
        if not placed:
            standalone.append(img)

    for vt in videos:
        vt.segments = _make_video_segments(
            vt.video_path, vt.video_start, (vt.video_end - vt.video_start).total_seconds(), vt.segments
        )

    all_entries: List[TimelineEntry] = []
    for vt in videos:
        all_entries.extend(vt.segments)
    all_entries.extend(standalone)
    all_entries.sort(key=lambda e: e.start_time)

    return TimelineMap(
        video_timelines=videos,
        standalone_images=standalone,
        all_entries=all_entries,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_timeline.py::test_build_timeline_inline_image -v`
Expected: PASS

- [ ] **Step 5: Add more tests**

```python
def test_build_timeline_standalone_image():
    video_meta = VideoMetadata(
        source_path=Path("video.mp4"),
        start_timestamp=datetime(2024, 7, 15, 12, 0, 0),
        end_timestamp=datetime(2024, 7, 15, 12, 2, 0),
        duration_seconds=120.0,
    )
    photo_meta = PhotoMetadata(
        source_path=Path("photo.jpg"),
        timestamp=datetime(2024, 7, 15, 11, 30, 0),
    )

    with patch("photowalk.timeline.extract_metadata", side_effect=[video_meta, photo_meta]):
        result = build_timeline([Path("video.mp4"), Path("photo.jpg")])

    assert len(result.standalone_images) == 1
    assert len(result.video_timelines[0].segments) == 1


def test_build_timeline_multiple_inline_images():
    video_meta = VideoMetadata(
        source_path=Path("video.mp4"),
        start_timestamp=datetime(2024, 7, 15, 12, 0, 0),
        end_timestamp=datetime(2024, 7, 15, 12, 2, 0),
        duration_seconds=120.0,
    )
    photo1 = PhotoMetadata(
        source_path=Path("photo1.jpg"),
        timestamp=datetime(2024, 7, 15, 12, 0, 30),
    )
    photo2 = PhotoMetadata(
        source_path=Path("photo2.jpg"),
        timestamp=datetime(2024, 7, 15, 12, 1, 0),
    )

    with patch("photowalk.timeline.extract_metadata", side_effect=[video_meta, photo1, photo2]):
        result = build_timeline([Path("video.mp4"), Path("photo1.jpg"), Path("photo2.jpg")])

    vt = result.video_timelines[0]
    assert len(vt.segments) == 5  # seg, img, seg, img, seg
    kinds = [s.kind for s in vt.segments]
    assert kinds == ["video_segment", "image", "video_segment", "image", "video_segment"]


def test_build_timeline_empty():
    with patch("photowalk.timeline.extract_metadata", return_value=None):
        result = build_timeline([Path("file.txt")])

    assert result.video_timelines == []
    assert result.standalone_images == []
```

- [ ] **Step 6: Run all timeline tests**

Run: `pytest tests/test_timeline.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/photowalk/timeline.py tests/test_timeline.py
git commit -m "feat: add timeline builder for video stitcher"
```

---

### Task 2: Image Clip Generator (`image_clip.py`)

**Files:**
- Create: `src/photowalk/image_clip.py`
- Test: `tests/test_image_clip.py`

**Description:** For each image, compute scaled dimensions that fit within the output frame while preserving aspect ratio, then generate a 3.5-second video with white background and centered image using ffmpeg.

- [ ] **Step 1: Write the failing test — scaling math**

```python
from photowalk.image_clip import compute_scaled_dimensions


def test_scale_landscape_to_landscape():
    # 4:3 image into 16:9 frame — should fit by height
    w, h = compute_scaled_dimensions(4000, 3000, 1920, 1080)
    assert w == 1440
    assert h == 1080


def test_scale_portrait_to_landscape():
    # 3:4 image into 16:9 frame — should fit by height
    w, h = compute_scaled_dimensions(3000, 4000, 1920, 1080)
    assert w == 810
    assert h == 1080


def test_scale_landscape_to_portrait():
    # 16:9 image into 9:16 frame — should fit by width
    w, h = compute_scaled_dimensions(1920, 1080, 1080, 1920)
    assert w == 1080
    assert h == 607
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_image_clip.py::test_scale_landscape_to_landscape -v`
Expected: FAIL — `compute_scaled_dimensions` not defined

- [ ] **Step 3: Write implementation**

Create `src/photowalk/image_clip.py`:

```python
"""Generate white-background video clips from photos."""

import subprocess
from pathlib import Path
from typing import Tuple

from PIL import Image


def compute_scaled_dimensions(
    img_width: int, img_height: int, frame_width: int, frame_height: int
) -> Tuple[int, int]:
    """Scale image to fit within frame while preserving aspect ratio."""
    scale_w = frame_width / img_width
    scale_h = frame_height / img_height
    scale = min(scale_w, scale_h)
    return int(img_width * scale), int(img_height * scale)


def generate_image_clip(
    image_path: Path,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    duration: float = 3.5,
) -> bool:
    """Generate a video clip with white background and centered image."""
    try:
        with Image.open(image_path) as img:
            img_width, img_height = img.size
    except Exception:
        return False

    scaled_w, scaled_h = compute_scaled_dimensions(img_width, img_height, frame_width, frame_height)
    x_offset = (frame_width - scaled_w) // 2
    y_offset = (frame_height - scaled_h) // 2

    filter_str = (
        f"color=c=white:s={frame_width}x{frame_height}:d={duration}[bg];"
        f"[bg][0:v]overlay={x_offset}:{y_offset}:enable='between(t,0,{duration})'"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-vf", filter_str,
        "-c:v", "libx264",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found in PATH. Install FFmpeg: https://ffmpeg.org")

    return result.returncode == 0
```

- [ ] **Step 4: Run scaling tests to verify they pass**

Run: `pytest tests/test_image_clip.py -v`
Expected: PASS

- [ ] **Step 5: Write test for ffmpeg command generation**

```python
from pathlib import Path
from unittest.mock import patch, MagicMock

from photowalk.image_clip import generate_image_clip


def test_generate_image_clip_ffmpeg_command():
    with patch("photowalk.image_clip.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_img.size = (4000, 3000)
        mock_open.return_value.__enter__.return_value = mock_img

        with patch("photowalk.image_clip.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = generate_image_clip(
                Path("photo.jpg"), Path("clip.mp4"), 1920, 1080, duration=3.5
            )

    assert result is True
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    assert "-loop" in cmd
    assert "photo.jpg" in cmd
    assert "1920x1080" in cmd[cmd.index("-vf") + 1]
```

- [ ] **Step 6: Run test**

Run: `pytest tests/test_image_clip.py::test_generate_image_clip_ffmpeg_command -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/photowalk/image_clip.py tests/test_image_clip.py
git commit -m "feat: add image clip generator for video stitcher"
```

---

### Task 3: Video Stitcher (`stitcher.py`)

**Files:**
- Create: `src/photowalk/stitcher.py`
- Test: `tests/test_stitcher.py`

**Description:** Split videos at image insertion points, build a concat list, and run ffmpeg concat demuxer.

- [ ] **Step 1: Write the failing test — concat list building**

```python
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from photowalk.stitcher import build_concat_list, run_concat, stitch
from photowalk.timeline import TimelineEntry, TimelineMap, VideoTimeline


def test_build_concat_list():
    entries = [
        TimelineEntry(
            start_time=datetime(2024, 7, 15, 12, 0, 0),
            duration_seconds=30.0,
            kind="video_segment",
            source_path=Path("video.mp4"),
            clip_path=Path("seg1.mp4"),
        ),
        TimelineEntry(
            start_time=datetime(2024, 7, 15, 12, 0, 30),
            duration_seconds=3.5,
            kind="image",
            source_path=Path("photo.jpg"),
            clip_path=Path("img.mp4"),
        ),
    ]

    with patch("photowalk.stitcher.TemporaryDirectory") as mock_tmp:
        mock_tmp.return_value.__enter__.return_value = "/tmp/test"
        list_path = build_concat_list(entries, Path("/tmp/test/list.txt"))

    content = list_path.read_text()
    assert "seg1.mp4" in content
    assert "img.mp4" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_stitcher.py::test_build_concat_list -v`
Expected: FAIL — `build_concat_list` not defined

- [ ] **Step 3: Write implementation**

Create `src/photowalk/stitcher.py`:

```python
"""Stitch video segments and image clips into a single output video."""

import subprocess
import tempfile
from pathlib import Path
from typing import List

from photowalk.image_clip import generate_image_clip
from photowalk.timeline import TimelineEntry, TimelineMap


def build_concat_list(entries: List[TimelineEntry], output_path: Path) -> Path:
    """Write an ffmpeg concat demuxer list file."""
    lines = []
    for entry in entries:
        path = entry.clip_path or entry.source_path
        lines.append(f"file '{path.resolve()}'")
        lines.append(f"duration {entry.duration_seconds}")
    # ffmpeg concat demuxer requires a final file line without duration
    if entries:
        last_path = entries[-1].clip_path or entries[-1].source_path
        lines.append(f"file '{last_path.resolve()}'")

    output_path.write_text("\n".join(lines) + "\n")
    return output_path


def run_concat(concat_list_path: Path, output_path: Path) -> bool:
    """Run ffmpeg concat demuxer."""
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_path),
        "-c", "copy",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found in PATH. Install FFmpeg: https://ffmpeg.org")
    return result.returncode == 0


def _split_video_segment(
    video_path: Path,
    trim_start: float,
    trim_end: float,
    output_path: Path,
) -> bool:
    """Extract a segment from a video using ffmpeg trim."""
    duration = trim_end - trim_start
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(video_path),
        "-ss", str(trim_start),
        "-t", str(duration),
        "-c", "copy",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found in PATH. Install FFmpeg: https://ffmpeg.org")
    return result.returncode == 0


def stitch(
    timeline_map: TimelineMap,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    image_duration: float = 3.5,
    keep_temp: bool = False,
) -> bool:
    """Stitch all segments into a single output video."""
    temp_dir = Path(tempfile.mkdtemp(prefix="photowalk_stitch_"))
    try:
        # Generate image clips and split video segments
        for entry in timeline_map.all_entries:
            if entry.kind == "image":
                clip_path = temp_dir / f"img_{entry.source_path.stem}.mp4"
                ok = generate_image_clip(
                    entry.source_path,
                    clip_path,
                    frame_width,
                    frame_height,
                    image_duration,
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
                )
                if not ok:
                    return False
                entry.clip_path = seg_path

        concat_list_path = temp_dir / "concat_list.txt"
        build_concat_list(timeline_map.all_entries, concat_list_path)
        ok = run_concat(concat_list_path, output_path)
        return ok
    finally:
        if not keep_temp:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_stitcher.py::test_build_concat_list -v`
Expected: PASS

- [ ] **Step 5: Add test for `run_concat` ffmpeg command**

```python
def test_run_concat_command():
    with patch("photowalk.stitcher.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = run_concat(Path("list.txt"), Path("out.mp4"))

    assert result is True
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    assert "concat" in cmd
    assert "list.txt" in cmd
```

- [ ] **Step 6: Add test for `stitch` end-to-end with mocked ffmpeg**

```python
def test_stitch_success():
    from datetime import timedelta

    entry = TimelineEntry(
        start_time=datetime(2024, 7, 15, 12, 0, 0),
        duration_seconds=3.5,
        kind="image",
        source_path=Path("photo.jpg"),
    )
    timeline = TimelineMap(
        standalone_images=[entry],
        all_entries=[entry],
    )

    with patch("photowalk.stitcher.generate_image_clip", return_value=True) as mock_clip:
        with patch("photowalk.stitcher.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = stitch(timeline, Path("out.mp4"), 1920, 1080, keep_temp=True)

    assert result is True
    mock_clip.assert_called_once()
```

- [ ] **Step 7: Run all stitcher tests**

Run: `pytest tests/test_stitcher.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/photowalk/stitcher.py tests/test_stitcher.py
git commit -m "feat: add video stitcher assembly engine"
```

---

### Task 4: CLI Integration (`cli.py`)

**Files:**
- Modify: `src/photowalk/cli.py`
- Test: `tests/test_cli_stitch.py`

**Description:** Add the `stitch` subcommand to the CLI. It collects files, builds the timeline, determines output resolution, runs the stitcher, and reports progress.

- [ ] **Step 1: Write the failing CLI test**

```python
from pathlib import Path
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from photowalk.cli import main


def test_stitch_dry_run():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("video.mp4").touch()
        Path("photo.jpg").touch()

        video_meta = MagicMock()
        video_meta.media_type = "video"
        video_meta.start_timestamp = __import__("datetime").datetime(2024, 7, 15, 12, 0, 0)
        video_meta.end_timestamp = __import__("datetime").datetime(2024, 7, 15, 12, 2, 0)
        video_meta.duration_seconds = 120.0

        photo_meta = MagicMock()
        photo_meta.media_type = "photo"
        photo_meta.timestamp = __import__("datetime").datetime(2024, 7, 15, 12, 0, 30)

        with patch("photowalk.cli.extract_metadata", side_effect=[video_meta, photo_meta]):
            result = runner.invoke(main, ["stitch", ".", "--output", "out.mp4", "--dry-run"])

    assert result.exit_code == 0
    assert "Timeline" in result.output or "out.mp4" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_stitch.py::test_stitch_dry_run -v`
Expected: FAIL — `stitch` command not registered

- [ ] **Step 3: Add imports and helper to `cli.py`**

Add these imports near the top of `src/photowalk/cli.py`:

```python
from photowalk.stitcher import stitch
from photowalk.timeline import build_timeline
```

- [ ] **Step 4: Add the `stitch` command to `cli.py`**

Insert before the `if __name__ == "__main__":` block:

```python
@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", required=True, type=click.Path(path_type=Path))
@click.option("--format", "fmt", help="Output resolution like 1920x1080")
@click.option("--image-duration", default=3.5, type=float, help="Seconds to show each image")
@click.option("--keep-temp", is_flag=True, help="Preserve temporary files")
@click.option("--dry-run", is_flag=True, help="Preview timeline without generating output")
@click.option("--recursive", "-r", is_flag=True, help="Scan directories recursively")
def stitch_cmd(path, output, fmt, image_duration, keep_temp, dry_run, recursive):
    """Stitch photos and videos into a single chronological video."""
    files = _collect_files([path], recursive)
    files = [f for f in files if f.suffix.lower() in PHOTO_EXTENSIONS | VIDEO_EXTENSIONS]

    if not files:
        click.echo("No media files found.")
        return

    timeline = build_timeline(files)
    all_entries = timeline.all_entries

    if not all_entries:
        click.echo("No usable media found (all files missing timestamps).")
        return

    # Determine output resolution
    frame_width, frame_height = 1920, 1080
    if fmt:
        try:
            frame_width, frame_height = map(int, fmt.split("x"))
        except ValueError:
            click.echo(click.style("Error: --format must be WIDTHxHEIGHT (e.g. 1920x1080)", fg="red"), err=True)
            raise Exit(1)
    else:
        # Use first video's resolution via ffprobe
        for vt in timeline.video_timelines:
            try:
                from photowalk.extractors import run_ffprobe
                data = run_ffprobe(vt.video_path)
                if data and "streams" in data:
                    for stream in data["streams"]:
                        if stream.get("codec_type") == "video":
                            frame_width = int(stream.get("width", 1920))
                            frame_height = int(stream.get("height", 1080))
                            break
                    break
            except Exception:
                pass

    # Show timeline preview
    lines = [f"{'Start':<25} {'Duration':<10} {'Type':<15} {'Source'}"]
    lines.append("-" * 90)
    for entry in all_entries:
        start = entry.start_time.isoformat() if entry.start_time else "N/A"
        name = str(entry.source_path.name)[:40]
        lines.append(f"{start:<25} {entry.duration_seconds:<10.1f} {entry.kind:<15} {name}")
    click.echo("\n".join(lines))

    if dry_run:
        return

    click.echo(f"\nOutput: {output}")
    click.echo(f"Resolution: {frame_width}x{frame_height}")
    click.echo("Generating clips and stitching...")

    ok = stitch(timeline, output, frame_width, frame_height, image_duration, keep_temp)
    if ok:
        click.echo(click.style("Done!", fg="green"))
    else:
        click.echo(click.style("Error: Stitching failed.", fg="red"), err=True)
        raise Exit(1)
```

- [ ] **Step 5: Run CLI test to verify it passes**

Run: `pytest tests/test_cli_stitch.py::test_stitch_dry_run -v`
Expected: PASS

- [ ] **Step 6: Add more CLI tests**

```python
def test_stitch_no_files():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["stitch", ".", "--output", "out.mp4"])
    assert result.exit_code == 0
    assert "No media files found" in result.output


def test_stitch_invalid_format():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("video.mp4").touch()
        result = runner.invoke(main, ["stitch", ".", "--output", "out.mp4", "--format", "bad"])
    assert result.exit_code == 1
    assert "1920x1080" in result.output or "WIDTHxHEIGHT" in result.output
```

- [ ] **Step 7: Run all CLI stitch tests**

Run: `pytest tests/test_cli_stitch.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/photowalk/cli.py tests/test_cli_stitch.py
git commit -m "feat: add stitch CLI command"
```

---

### Task 5: Full Test Suite Run

- [ ] **Step 1: Run the entire test suite**

Run: `uv run pytest -v`
Expected: All tests PASS, including existing tests (no regressions)

- [ ] **Step 2: Commit any fixes if needed**

```bash
git add -A
git commit -m "test: add video stitcher test suite"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- [x] JSON timestamp map → `build_timeline()` in Task 1
- [x] 3.5-second image clips → `generate_image_clip()` in Task 2
- [x] White background → ffmpeg `color=c=white` filter in Task 2
- [x] Split videos at image points → `_split_video_segment()` in Task 3
- [x] Stitch with ffmpeg concat → `run_concat()` in Task 3
- [x] Output format detection/override → `--format` flag in Task 4
- [x] `--dry-run`, `--keep-temp` → implemented in Task 4
- [x] Error handling → documented in each task

**2. Placeholder scan:**
- [x] No "TBD", "TODO", or "implement later"
- [x] Every test has complete code
- [x] Every step has exact commands and expected output
- [x] No vague references to other tasks

**3. Type consistency:**
- [x] `TimelineEntry`, `VideoTimeline`, `TimelineMap` defined once in Task 1
- [x] `generate_image_clip` signature matches usage in Task 3
- [x] `stitch` signature matches CLI call in Task 4
- [x] `build_timeline` returns `TimelineMap` consistently
