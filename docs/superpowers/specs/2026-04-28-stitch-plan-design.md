# Stitch Plan Design

**Date:** 2026-04-28

## Summary

Add a `--plan <file>` flag to the `stitch` command that writes a JSON file describing exactly how the video would be stitched, including all ffmpeg commands, then exits without generating any video.

## Motivation

The `stitch` command already shows a timeline preview in the terminal, but there's no way to inspect the full processing plan — the splits, temp file paths, and exact ffmpeg commands. A JSON plan file enables:
- Debugging complex timelines
- Verifying splits before rendering
- Sharing/documenting the stitch configuration

## Design

### CLI Interface

```bash
uv run photowalk stitch ~/Photos/ --output final.mp4 --plan plan.json
```

- `--plan <path>` writes the plan JSON to the specified file (relative to cwd)
- When `--plan` is present, no video is generated (implies `--dry-run` behavior)
- `--plan` can be combined with all other stitch flags (`--format`, `--image-duration`, `--draft`, `--recursive`)

### JSON Structure

```json
{
  "settings": {
    "output": "final.mp4",
    "resolution": [1920, 1080],
    "image_duration": 3.5,
    "draft": false
  },
  "timeline": [
    {
      "start_time": "2024-01-15T10:00:00",
      "duration": 12.5,
      "kind": "video_segment",
      "source": "video.mp4",
      "original_video": "video.mp4",
      "trim_start": 0.0,
      "trim_end": 12.5
    },
    {
      "start_time": "2024-01-15T10:00:12.5",
      "duration": 3.5,
      "kind": "image",
      "source": "photo.jpg",
      "original_video": null,
      "trim_start": null,
      "trim_end": null
    }
  ],
  "temp_dir": "/tmp/photowalk_stitch_abc123/",
  "ffmpeg_commands": [
    {
      "step": "image_clip",
      "source": "photo.jpg",
      "output": "/tmp/photowalk_stitch_abc123/img_photo.mp4",
      "command": ["ffmpeg", "-y", "-loop", "1", "-i", "photo.jpg", ...]
    },
    {
      "step": "video_segment",
      "source": "video.mp4",
      "output": "/tmp/photowalk_stitch_abc123/seg_0.000_video.mp4",
      "command": ["ffmpeg", "-y", "-ss", "0.0", "-i", "video.mp4", "-t", "12.5", ...]
    },
    {
      "step": "concat",
      "input": "/tmp/photowalk_stitch_abc123/concat_list.txt",
      "output": "final.mp4",
      "command": ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "...", ...]
    }
  ]
}
```

### Field Details

**settings:**
- `output`: Output video path as specified by `--output`
- `resolution`: `[width, height]` — computed from `--format` or first video's resolution
- `image_duration`: From `--image-duration` (default 3.5)
- `draft`: Whether `--draft` flag was set

**timeline entries:**
- `start_time`: ISO 8601 timestamp
- `duration`: Seconds (float)
- `kind`: `"image"`, `"video"`, or `"video_segment"`
- `source`: Source file path
- `original_video`: Parent video path (null for images and standalone videos)
- `trim_start`: Start offset in seconds (null for images)
- `trim_end`: End offset in seconds (null for images)

**temp_dir:**
- Path where temp files would be created (using `tempfile.mkdtemp`)

**ffmpeg_commands:**
- Ordered list of commands that would be executed
- `step`: One of `"image_clip"`, `"video_segment"`, `"concat"`
- `source`: Input file
- `output`: Output file
- `command`: Full argv array as strings

## Implementation

### Changes to `cli.py`

In `stitch_cmd`:
1. Add `--plan` option: `@click.option("--plan", type=click.Path(path_type=Path), help="Write stitch plan as JSON and exit")`
2. After building the timeline and computing resolution, if `--plan` is set:
   - Compute the temp directory path
   - Generate the plan dict with settings, timeline, temp_dir, and ffmpeg_commands
   - Write JSON to the plan path
   - Print confirmation and return (skip video generation)

### Changes to `stitcher.py`

Add a new function `generate_plan(timeline_map, output_path, frame_width, frame_height, image_duration, draft)` that:
1. Creates a temp dir (or uses a deterministic path)
2. Walks the timeline entries and builds the plan dict
3. Constructs the ffmpeg command arrays for each entry (same logic as `stitch` but without executing)
4. Constructs the concat command
5. Returns the plan dict

The existing `stitch` function remains unchanged.

### Testing

- Test that `--plan` writes a valid JSON file
- Test that `--plan` does not generate any video or temp files
- Test the JSON structure matches the spec (settings, timeline, temp_dir, ffmpeg_commands)
- Test combinations with `--draft` and custom `--format`
