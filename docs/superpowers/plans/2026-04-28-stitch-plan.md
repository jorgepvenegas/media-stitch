# Stitch Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--plan` flag to the stitch command that writes a JSON file describing the full stitching pipeline (timeline, temp paths, ffmpeg commands) and exits without generating video.

**Architecture:** Add a `generate_plan()` function to `stitcher.py` that mirrors the logic of `stitch()` but returns a dict instead of executing ffmpeg. Wire it into `cli.py` with a new `--plan` option on `stitch_cmd`.

**Tech Stack:** Python 3.10+, click, pytest, tempfile

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/photowalk/stitcher.py` | Modify | Add `generate_plan()` function |
| `tests/test_stitcher.py` | Modify | Add tests for `generate_plan()` |
| `src/photowalk/cli.py` | Modify | Add `--plan` option to `stitch_cmd` |
| `tests/test_cli_stitch.py` | Modify | Add tests for `--plan` flag |

---

### Task 1: Add `generate_plan` to stitcher.py

**Files:**
- Modify: `src/photowalk/stitcher.py`
- Modify: `tests/test_stitcher.py`

- [ ] **Step 1: Write failing test for generate_plan with image entry**

```python
def test_generate_plan_image_entry():
    entry = TimelineEntry(
        start_time=datetime(2024, 7, 15, 12, 0, 0),
        duration_seconds=3.5,
        kind="image",
        source_path=Path("/photos/pic.jpg"),
    )
    timeline = TimelineMap(all_entries=[entry])

    plan = generate_plan(timeline, Path("out.mp4"), 1920, 1080, image_duration=3.5)

    assert plan["settings"]["output"] == "out.mp4"
    assert plan["settings"]["resolution"] == [1920, 1080]
    assert plan["settings"]["image_duration"] == 3.5
    assert plan["settings"]["draft"] is False
    assert len(plan["timeline"]) == 1
    assert plan["timeline"][0]["kind"] == "image"
    assert plan["timeline"][0]["source"] == "/photos/pic.jpg"
    assert plan["timeline"][0]["duration"] == 3.5
    assert len(plan["ffmpeg_commands"]) == 2  # image_clip + concat
    assert plan["ffmpeg_commands"][0]["step"] == "image_clip"
    assert plan["ffmpeg_commands"][1]["step"] == "concat"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/jorge/code/photo-walk && uv run pytest tests/test_stitcher.py::test_generate_plan_image_entry -v`
Expected: FAIL with "generate_plan not defined"

- [ ] **Step 3: Write failing test for generate_plan with video segment**

```python
def test_generate_plan_video_segment():
    entry = TimelineEntry(
        start_time=datetime(2024, 7, 15, 12, 0, 0),
        duration_seconds=10.0,
        kind="video_segment",
        source_path=Path("/videos/clip.mp4"),
        original_video=Path("/videos/clip.mp4"),
        trim_start=5.0,
        trim_end=15.0,
    )
    timeline = TimelineMap(all_entries=[entry])

    plan = generate_plan(timeline, Path("out.mp4"), 1920, 1080)

    assert len(plan["timeline"]) == 1
    t = plan["timeline"][0]
    assert t["kind"] == "video_segment"
    assert t["source"] == "/videos/clip.mp4"
    assert t["original_video"] == "/videos/clip.mp4"
    assert t["trim_start"] == 5.0
    assert t["trim_end"] == 15.0
    assert len(plan["ffmpeg_commands"]) == 2  # split + concat
    assert plan["ffmpeg_commands"][0]["step"] == "video_segment"
    assert "-ss" in plan["ffmpeg_commands"][0]["command"]
    assert "5.0" in plan["ffmpeg_commands"][0]["command"]
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd /Users/jorge/code/photo-walk && uv run pytest tests/test_stitcher.py::test_generate_plan_video_segment -v`
Expected: FAIL

- [ ] **Step 5: Write failing test for generate_plan with draft mode**

```python
def test_generate_plan_draft_mode():
    entry = TimelineEntry(
        start_time=datetime(2024, 7, 15, 12, 0, 0),
        duration_seconds=3.5,
        kind="image",
        source_path=Path("/photos/pic.jpg"),
    )
    timeline = TimelineMap(all_entries=[entry])

    plan = generate_plan(timeline, Path("out.mp4"), 1920, 1080, draft=True)

    assert plan["settings"]["draft"] is True
    assert plan["settings"]["resolution"] == [1280, 720]
    cmd = plan["ffmpeg_commands"][0]["command"]
    assert "ultrafast" in cmd
    assert "28" in cmd
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd /Users/jorge/code/photo-walk && uv run pytest tests/test_stitcher.py::test_generate_plan_draft_mode -v`
Expected: FAIL

- [ ] **Step 7: Implement generate_plan function**

Add to `src/photowalk/stitcher.py`:

```python
def generate_plan(
    timeline_map: TimelineMap,
    output_path: Path,
    frame_width: int,
    frame_height: int,
    image_duration: float = 3.5,
    draft: bool = False,
) -> dict:
    """Generate a plan dict describing how stitch() would process the timeline."""
    if draft:
        frame_width, frame_height = compute_draft_resolution(frame_width, frame_height)
        preset = "ultrafast"
        crf = 28
    else:
        preset = "fast"
        crf = 23

    temp_dir = Path(tempfile.mkdtemp(prefix="photowalk_stitch_"))
    timeline_entries = []
    ffmpeg_commands = []

    for entry in timeline_map.all_entries:
        if entry.kind == "image":
            clip_path = temp_dir / f"img_{entry.source_path.stem}.mp4"
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", str(entry.source_path.resolve()),
                "-t", str(image_duration),
                "-vf", f"scale={frame_width}:{frame_height}:force_original_aspect_ratio=decrease,pad={frame_width}:{frame_height}:(ow-iw)/2:(oh-ih)/2:white",
                "-c:v", "libx264",
                "-preset", preset,
                "-crf", str(crf),
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(clip_path),
            ]
            ffmpeg_commands.append({
                "step": "image_clip",
                "source": str(entry.source_path),
                "output": str(clip_path),
                "command": cmd,
            })
            timeline_entries.append({
                "start_time": entry.start_time.isoformat(),
                "duration": image_duration,
                "kind": "image",
                "source": str(entry.source_path),
                "original_video": None,
                "trim_start": None,
                "trim_end": None,
            })

        elif entry.kind == "video_segment":
            seg_path = temp_dir / f"seg_{entry.trim_start:.3f}_{entry.source_path.stem}.mp4"
            duration = (entry.trim_end or 0) - (entry.trim_start or 0)
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(entry.trim_start or 0.0),
                "-i", str(entry.source_path.resolve()),
                "-t", str(duration),
                "-vf", f"scale={frame_width}:{frame_height}:force_original_aspect_ratio=decrease,pad={frame_width}:{frame_height}:(ow-iw)/2:(oh-ih)/2:white",
                "-c:v", "libx264",
                "-preset", preset,
                "-crf", str(crf),
                "-c:a", "aac",
                "-b:a", "128k",
                "-ar", "48000",
                "-r", "30",
                "-video_track_timescale", "15360",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(seg_path),
            ]
            ffmpeg_commands.append({
                "step": "video_segment",
                "source": str(entry.source_path),
                "output": str(seg_path),
                "command": cmd,
            })
            timeline_entries.append({
                "start_time": entry.start_time.isoformat(),
                "duration": entry.duration_seconds,
                "kind": "video_segment",
                "source": str(entry.source_path),
                "original_video": str(entry.original_video) if entry.original_video else None,
                "trim_start": entry.trim_start,
                "trim_end": entry.trim_end,
            })

    # Build concat command
    concat_list_path = temp_dir / "concat_list.txt"
    concat_cmd = [
        "ffmpeg", "-y",
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
    ffmpeg_commands.append({
        "step": "concat",
        "input": str(concat_list_path),
        "output": str(output_path),
        "command": concat_cmd,
    })

    return {
        "settings": {
            "output": str(output_path),
            "resolution": [frame_width, frame_height],
            "image_duration": image_duration,
            "draft": draft,
        },
        "timeline": timeline_entries,
        "temp_dir": str(temp_dir),
        "ffmpeg_commands": ffmpeg_commands,
    }
```

- [ ] **Step 8: Run all three new tests**

Run: `cd /Users/jorge/code/photo-walk && uv run pytest tests/test_stitcher.py::test_generate_plan_image_entry tests/test_stitcher.py::test_generate_plan_video_segment tests/test_stitcher.py::test_generate_plan_draft_mode -v`
Expected: All PASS

- [ ] **Step 9: Run full stitcher test suite to verify no regressions**

Run: `cd /Users/jorge/code/photo-walk && uv run pytest tests/test_stitcher.py -v`
Expected: All PASS

- [ ] **Step 10: Commit**

```bash
git add src/photowalk/stitcher.py tests/test_stitcher.py
git commit -m "feat: add generate_plan() to stitcher module"
```

---

### Task 2: Wire --plan into CLI

**Files:**
- Modify: `src/photowalk/cli.py`
- Modify: `tests/test_cli_stitch.py`

- [ ] **Step 1: Write failing test for --plan flag**

```python
def test_stitch_plan_writes_json():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("video.mp4").touch()
        Path("photo.jpg").touch()

        mock_timeline = _make_mock_timeline()

        with patch("photowalk.cli.build_timeline", return_value=mock_timeline):
            result = runner.invoke(main, [
                "stitch", ".", "--output", "out.mp4", "--plan", "plan.json"
            ])

    assert result.exit_code == 0
    assert Path("plan.json").exists()

    import json
    plan = json.loads(Path("plan.json").read_text())
    assert plan["settings"]["output"] == "out.mp4"
    assert "timeline" in plan
    assert "ffmpeg_commands" in plan
    assert "temp_dir" in plan
```

- [ ] **Step 2: Write failing test for --plan does not generate video**

```python
def test_stitch_plan_no_video_generation():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("video.mp4").touch()

        mock_timeline = _make_mock_timeline()

        with patch("photowalk.cli.build_timeline", return_value=mock_timeline):
            with patch("photowalk.cli.stitch") as mock_stitch:
                result = runner.invoke(main, [
                    "stitch", ".", "--output", "out.mp4", "--plan", "plan.json"
                ])

    assert result.exit_code == 0
    mock_stitch.assert_not_called()
    assert not Path("out.mp4").exists()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/jorge/code/photo-walk && uv run pytest tests/test_cli_stitch.py::test_stitch_plan_writes_json tests/test_cli_stitch.py::test_stitch_plan_no_video_generation -v`
Expected: FAIL

- [ ] **Step 4: Add --plan option and implement in stitch_cmd**

In `src/photowalk/cli.py`, update the `stitch_cmd` function:

Add the option:
```python
@click.option("--plan", type=click.Path(path_type=Path), help="Write stitch plan as JSON and exit")
```

Update the function signature to include `plan`.

After the resolution determination block and before the timeline preview section, add:

```python
    if plan:
        import json
        from photowalk.stitcher import generate_plan

        plan_data = generate_plan(timeline, output, frame_width, frame_height, image_duration, draft)
        plan.write_text(json.dumps(plan_data, indent=2))
        click.echo(f"Plan written to {plan}")
        return
```

- [ ] **Step 5: Run the new tests**

Run: `cd /Users/jorge/code/photo-walk && uv run pytest tests/test_cli_stitch.py::test_stitch_plan_writes_json tests/test_cli_stitch.py::test_stitch_plan_no_video_generation -v`
Expected: PASS

- [ ] **Step 6: Run full CLI stitch test suite to verify no regressions**

Run: `cd /Users/jorge/code/photo-walk && uv run pytest tests/test_cli_stitch.py -v`
Expected: All PASS

- [ ] **Step 7: Run full test suite**

Run: `cd /Users/jorge/code/photo-walk && uv run pytest`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/photowalk/cli.py tests/test_cli_stitch.py
git commit -m "feat: add --plan flag to stitch command"
```
