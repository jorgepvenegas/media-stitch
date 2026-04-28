# `--draft` Flag for `photowalk stitch` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--draft` flag to `photowalk stitch` that reduces resolution and encoder quality for faster preview rendering while preserving segment timing.

**Architecture:** Add `preset` and `crf` parameters to all ffmpeg-wrapping functions. Introduce a `_compute_draft_resolution` helper in `stitcher.py` that proportionally scales the requested resolution down to fit within 1280×720. Wire the `--draft` CLI flag through to the stitcher, which switches preset to `ultrafast`, CRF to 28, and applies the reduced resolution.

**Tech Stack:** Python, pytest, Click, ffmpeg CLI

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/photowalk/stitcher.py` | Draft resolution math, draft-aware parameter forwarding for split/concat |
| `src/photowalk/image_clip.py` | Accept `preset`/`crf` parameters and inject them into ffmpeg command |
| `src/photowalk/cli.py` | Add `--draft` flag and pass it to `stitch()` |
| `tests/test_stitcher.py` | Tests for draft resolution, draft parameter propagation in split/concat |
| `tests/test_image_clip.py` | Test that `preset`/`crf` reach the ffmpeg command |
| `tests/test_cli_stitch.py` | Test that `--draft` reaches `stitch()` |

---

### Task 1: Draft Resolution Helper

**Files:**
- Modify: `src/photowalk/stitcher.py`
- Test: `tests/test_stitcher.py`

- [ ] **Step 1: Write the failing test**

```python
def test_compute_draft_resolution_scales_down():
    from photowalk.stitcher import _compute_draft_resolution
    assert _compute_draft_resolution(1920, 1080) == (1280, 720)


def test_compute_draft_resolution_preserves_small():
    from photowalk.stitcher import _compute_draft_resolution
    assert _compute_draft_resolution(640, 480) == (640, 480)


def test_compute_draft_resolution_preserves_aspect_ratio():
    from photowalk.stitcher import _compute_draft_resolution
    w, h = _compute_draft_resolution(1920, 1080)
    assert w == 1280
    assert h == 720
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stitcher.py::test_compute_draft_resolution_scales_down -v`
Expected: FAIL with `ImportError: cannot import name '_compute_draft_resolution'`

- [ ] **Step 3: Write minimal implementation**

Add the helper at module level in `src/photowalk/stitcher.py`, before `build_concat_list`:

```python
def _compute_draft_resolution(width: int, height: int) -> tuple[int, int]:
    """Scale resolution proportionally so it fits within 1280x720."""
    max_w, max_h = 1280, 720
    scale = min(max_w / width, max_h / height, 1.0)
    return int(width * scale), int(height * scale)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_stitcher.py -k draft_resolution -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/stitcher.py tests/test_stitcher.py
git commit -m "feat: add _compute_draft_resolution helper"
```

---

### Task 2: Add `preset` and `crf` to `_split_video_segment`

**Files:**
- Modify: `src/photowalk/stitcher.py`
- Test: `tests/test_stitcher.py`

- [ ] **Step 1: Write the failing test**

```python
def test_split_video_segment_uses_custom_preset_and_crf():
    from photowalk.stitcher import _split_video_segment
    with patch("photowalk.stitcher.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        _split_video_segment(
            Path("in.mp4"), 0.0, 5.0, Path("out.mp4"), 640, 480,
            preset="ultrafast", crf=28,
        )
    cmd = mock_run.call_args[0][0]
    assert "-preset" in cmd
    preset_idx = cmd.index("-preset")
    assert cmd[preset_idx + 1] == "ultrafast"
    assert "-crf" in cmd
    crf_idx = cmd.index("-crf")
    assert cmd[crf_idx + 1] == "28"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stitcher.py::test_split_video_segment_uses_custom_preset_and_crf -v`
Expected: FAIL with `TypeError: _split_video_segment() got unexpected keyword arguments`

- [ ] **Step 3: Write minimal implementation**

In `src/photowalk/stitcher.py`, update `_split_video_segment` signature and command:

Replace the existing function signature:
```python
def _split_video_segment(
    video_path: Path,
    trim_start: float,
    trim_end: float,
    output_path: Path,
    frame_width: int,
    frame_height: int,
) -> bool:
```

With:
```python
def _split_video_segment(
    video_path: Path,
    trim_start: float,
    trim_end: float,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    preset: str = "fast",
    crf: int = 23,
) -> bool:
```

Then in the command list, change:
```python
        "-preset", "fast",
        "-crf", "23",
```
to:
```python
        "-preset", preset,
        "-crf", str(crf),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_stitcher.py -k split_video_segment -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/stitcher.py tests/test_stitcher.py
git commit -m "feat: add preset and crf params to _split_video_segment"
```

---

### Task 3: Add `preset` and `crf` to `run_concat`

**Files:**
- Modify: `src/photowalk/stitcher.py`
- Test: `tests/test_stitcher.py`

- [ ] **Step 1: Write the failing test**

```python
def test_run_concat_uses_custom_preset_and_crf():
    from photowalk.stitcher import run_concat
    with patch("photowalk.stitcher.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        run_concat(Path("list.txt"), Path("out.mp4"), preset="ultrafast", crf=28)
    cmd = mock_run.call_args[0][0]
    preset_idx = cmd.index("-preset")
    assert cmd[preset_idx + 1] == "ultrafast"
    crf_idx = cmd.index("-crf")
    assert cmd[crf_idx + 1] == "28"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stitcher.py::test_run_concat_uses_custom_preset_and_crf -v`
Expected: FAIL with `TypeError: run_concat() got unexpected keyword arguments`

- [ ] **Step 3: Write minimal implementation**

In `src/photowalk/stitcher.py`, update `run_concat` signature and command:

Replace:
```python
def run_concat(concat_list_path: Path, output_path: Path) -> bool:
```

With:
```python
def run_concat(concat_list_path: Path, output_path: Path, preset: str = "fast", crf: int = 23) -> bool:
```

Then add `-preset` and `-crf` to the command list. The current command in `run_concat` is:
```python
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_path),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]
```

Change it to:
```python
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_path),
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_stitcher.py -k run_concat -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/stitcher.py tests/test_stitcher.py
git commit -m "feat: add preset and crf params to run_concat"
```

---

### Task 4: Add `preset` and `crf` to `generate_image_clip`

**Files:**
- Modify: `src/photowalk/image_clip.py`
- Test: `tests/test_image_clip.py`

- [ ] **Step 1: Write the failing test**

```python
def test_generate_image_clip_uses_custom_preset_and_crf():
    with patch("photowalk.image_clip.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_img.size = (1920, 1080)
        mock_open.return_value.__enter__.return_value = mock_img

        with patch("photowalk.image_clip.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = generate_image_clip(
                Path("photo.jpg"), Path("clip.mp4"), 1920, 1080,
                preset="ultrafast", crf=28,
            )

    assert result is True
    cmd = mock_run.call_args[0][0]
    preset_idx = cmd.index("-preset")
    assert cmd[preset_idx + 1] == "ultrafast"
    crf_idx = cmd.index("-crf")
    assert cmd[crf_idx + 1] == "28"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_image_clip.py::test_generate_image_clip_uses_custom_preset_and_crf -v`
Expected: FAIL with `TypeError: generate_image_clip() got unexpected keyword arguments`

- [ ] **Step 3: Write minimal implementation**

In `src/photowalk/image_clip.py`, update the function signature and command.

Replace:
```python
def generate_image_clip(
    image_path: Path,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    duration: float = 3.5,
) -> bool:
```

With:
```python
def generate_image_clip(
    image_path: Path,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    duration: float = 3.5,
    preset: str = "fast",
    crf: int = 23,
) -> bool:
```

In the `cmd` list, change:
```python
        "-c:v", "libx264",
        "-c:a", "aac",
```

to:
```python
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-c:a", "aac",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_image_clip.py -k preset_and_crf -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/image_clip.py tests/test_image_clip.py
git commit -m "feat: add preset and crf params to generate_image_clip"
```

---

### Task 5: Wire `draft` Through `stitch()`

**Files:**
- Modify: `src/photowalk/stitcher.py`
- Test: `tests/test_stitcher.py`

- [ ] **Step 1: Write the failing test**

```python
def test_stitch_draft_mode_uses_draft_params():
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
            result = stitch(timeline, Path("out.mp4"), 1920, 1080, draft=True, keep_temp=True)

    assert result is True
    mock_clip.assert_called_once()
    _, kwargs = mock_clip.call_args
    assert kwargs["preset"] == "ultrafast"
    assert kwargs["crf"] == 28

    # Check resolution passed to generate_image_clip is reduced
    args = mock_clip.call_args[0]
    assert args[2] == 1280  # frame_width
    assert args[3] == 720   # frame_height
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_stitcher.py::test_stitch_draft_mode_uses_draft_params -v`
Expected: FAIL with `TypeError: stitch() got unexpected keyword argument 'draft'`

- [ ] **Step 3: Write minimal implementation**

In `src/photowalk/stitcher.py`, update `stitch` signature and body.

Replace:
```python
def stitch(
    timeline_map: TimelineMap,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    image_duration: float = 3.5,
    keep_temp: bool = False,
) -> bool:
```

With:
```python
def stitch(
    timeline_map: TimelineMap,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    image_duration: float = 3.5,
    keep_temp: bool = False,
    draft: bool = False,
) -> bool:
```

At the top of the function body (after `temp_dir = ...`), add:
```python
    if draft:
        frame_width, frame_height = _compute_draft_resolution(frame_width, frame_height)
        preset = "ultrafast"
        crf = 28
    else:
        preset = "fast"
        crf = 23
```

Then update the `generate_image_clip` call inside the loop:
```python
                ok = generate_image_clip(
                    entry.source_path,
                    clip_path,
                    frame_width,
                    frame_height,
                    image_duration,
                    preset=preset,
                    crf=crf,
                )
```

Update the `_split_video_segment` call:
```python
                ok = _split_video_segment(
                    entry.source_path,
                    entry.trim_start or 0.0,
                    entry.trim_end or 0.0,
                    seg_path,
                    frame_width,
                    frame_height,
                    preset=preset,
                    crf=crf,
                )
```

Update the `run_concat` call:
```python
        ok = run_concat(concat_list_path, output_path, preset=preset, crf=crf)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_stitcher.py -k draft -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/stitcher.py tests/test_stitcher.py
git commit -m "feat: wire draft mode through stitch()"
```

---

### Task 6: Add `--draft` Flag to CLI

**Files:**
- Modify: `src/photowalk/cli.py`
- Test: `tests/test_cli_stitch.py`

- [ ] **Step 1: Write the failing test**

```python
def test_stitch_draft_flag():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("video.mp4").touch()
        Path("photo.jpg").touch()

        mock_timeline = _make_mock_timeline()

        with patch("photowalk.cli.build_timeline", return_value=mock_timeline):
            with patch("photowalk.cli.stitch") as mock_stitch:
                result = runner.invoke(main, [
                    "stitch", ".", "--output", "out.mp4", "--draft"
                ])

    assert result.exit_code == 0
    mock_stitch.assert_called_once()
    _, kwargs = mock_stitch.call_args
    assert kwargs["draft"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_stitch.py::test_stitch_draft_flag -v`
Expected: FAIL with `AssertionError: Expected draft=True but got False or key missing`

- [ ] **Step 3: Write minimal implementation**

In `src/photowalk/cli.py`, update `stitch_cmd`.

Add the option after `--recursive`:
```python
@click.option("--draft", is_flag=True, help="Render a low-quality draft for faster preview")
```

Add `draft` to the function signature:
```python
def stitch_cmd(path, output, fmt, image_duration, keep_temp, dry_run, recursive, draft):
```

Pass it to `stitch`:
```python
    ok = stitch(timeline, output, frame_width, frame_height, image_duration, keep_temp, draft)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_stitch.py -k draft -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/cli.py tests/test_cli_stitch.py
git commit -m "feat: add --draft flag to stitch CLI command"
```

---

### Task 7: Full Test Suite Verification

- [ ] **Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 2: Commit if everything is green**

```bash
git commit --allow-empty -m "chore: verify full suite passes with --draft flag"
```

---

## Spec Self-Review

**Spec coverage:**
- ✅ CLI `--draft` flag — Task 6
- ✅ Draft resolution capped at 1280×720 with aspect ratio preserved — Task 1, Task 5
- ✅ Encoder preset `ultrafast` and CRF 28 in draft mode — Tasks 2–5
- ✅ Timing preserved (no duration changes) — verified by not touching `-t`, `-ss`, or image_duration
- ✅ Backwards compatibility (default `draft=False`) — all default params set accordingly

**Placeholder scan:** None found.

**Type consistency:** `draft: bool = False` everywhere. `preset: str`, `crf: int` consistent across `_split_video_segment`, `run_concat`, `generate_image_clip`, and `stitch`.
