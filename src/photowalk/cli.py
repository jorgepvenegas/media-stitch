"""Click CLI for photowalk."""

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click
from click.exceptions import Exit

from photowalk.api import extract_metadata
from photowalk.collector import collect_files
from photowalk.constants import PHOTO_EXTENSIONS, VIDEO_EXTENSIONS
from photowalk.extractors import run_ffprobe
from photowalk.formatters import (
    format_csv,
    format_sync_preview,
    format_table,
    format_timeline,
)
from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.offset import compute_offset, OffsetError
from photowalk.offset_detector import detect_trim_offset, OffsetDetectionError
from photowalk.stitcher import stitch, compute_draft_resolution, generate_plan
from photowalk.timeline import build_timeline_from_files
from photowalk.writers import write_photo_timestamp, write_video_timestamp

try:
    from photowalk.web.server import build_app_from_path
    HAS_WEB = True
except ImportError:
    HAS_WEB = False


@click.group()
@click.version_option(version="0.1.0")
def main():
    """Extract metadata from photos and videos using ffprobe."""
    pass


@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def info(path: Path):
    """Show metadata for a single file."""
    try:
        result = extract_metadata(path)
    except RuntimeError as e:
        click.echo(click.style(str(e), fg="red"), err=True)
        raise Exit(1)

    if result is None:
        click.echo("Unsupported file type.")
        return

    click.echo(json.dumps(result.to_dict(), indent=2))


@main.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Choice(["json", "table", "csv"]), default="table")
@click.option("--recursive", "-r", is_flag=True)
@click.option("--include-photos/--no-include-photos", default=True)
@click.option("--include-videos/--no-include-videos", default=True)
def batch(paths, output, recursive, include_photos, include_videos):
    """Process multiple files or directories."""
    try:
        files = collect_files(list(paths), recursive, include_photos, include_videos)
    except RuntimeError as e:
        click.echo(click.style(str(e), fg="red"), err=True)
        raise Exit(1)

    if not files:
        click.echo("No media files found.")
        return

    results = []
    for f in files:
        result = extract_metadata(f)
        if result is not None:
            results.append(result)

    if output == "json":
        click.echo(json.dumps([r.to_dict() for r in results], indent=2))
    elif output == "csv":
        click.echo(format_csv(results))
    else:
        click.echo(format_table(results))


@main.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--offset", help="Duration offset like '-8h23m5s' or '+2h'")
@click.option("--reference", help="Reference timestamp pair like 'wrong=correct'")
@click.option("--recursive", "-r", is_flag=True)
@click.option("--dry-run", is_flag=True, help="Preview changes without writing")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--include-photos/--no-include-photos", default=True)
@click.option("--include-videos/--no-include-videos", default=True)
def sync(paths, offset, reference, recursive, dry_run, yes, include_photos, include_videos):
    """Adjust timestamps in media files by an offset."""
    try:
        delta = compute_offset(offset, reference)
    except OffsetError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        raise Exit(1)

    try:
        files = collect_files(list(paths), recursive, include_photos, include_videos)
    except RuntimeError as e:
        click.echo(click.style(str(e), fg="red"), err=True)
        raise Exit(1)

    if not files:
        click.echo("No media files found.")
        return

    # Build preview list
    preview = []  # list of (path, current, new, skipped_reason)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)

    for f in files:
        result = extract_metadata(f)
        if result is None:
            preview.append((f, None, None, "Unsupported file type"))
            continue

        if isinstance(result, PhotoMetadata):
            current = result.timestamp
        else:
            current = result.start_timestamp

        if current is None:
            preview.append((f, None, None, "No timestamp found"))
            continue

        new_time = current + delta
        # Check for pre-1970 (EXIF doesn't support it)
        if new_time.tzinfo is None:
            new_time_aware = new_time.replace(tzinfo=timezone.utc)
        else:
            new_time_aware = new_time
        if new_time_aware < epoch:
            preview.append((f, current, None, "Result would be before 1970"))
            continue

        preview.append((f, current, new_time, None))

    click.echo(format_sync_preview(preview, delta))

    if dry_run:
        return

    # Count writable files
    writable = [item for item in preview if item[3] is None]
    if not writable:
        click.echo("No files to update.")
        return

    # Confirmation
    if not yes:
        prompt = f"Apply timestamp offset to {len(writable)} file(s)? [y/N]: "
        response = click.prompt(prompt, default="n", show_default=False)
        if response.lower() not in ("y", "yes"):
            click.echo("Cancelled.")
            return

    # Write
    success_count = 0
    for f, current, new_time, reason in writable:
        ext = f.suffix.lower()
        if ext in PHOTO_EXTENSIONS:
            ok = write_photo_timestamp(f, new_time)
        else:
            ok = write_video_timestamp(f, new_time)

        if ok:
            success_count += 1
        else:
            click.echo(click.style(f"  Failed to update {f}", fg="yellow"))

    skipped_count = len(preview) - len(writable)
    fail_count = len(writable) - success_count
    msg = f"Updated {success_count} of {len(writable)} file(s)."
    if skipped_count:
        msg += f" {skipped_count} skipped."
    if fail_count:
        msg += f" {fail_count} failed."
    click.echo(msg)


@main.command("fix-trim")
@click.argument("original", type=click.Path(exists=True, path_type=Path))
@click.argument("trimmed", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    help="Output path instead of updating in place",
)
@click.option("--dry-run", is_flag=True, help="Preview changes without writing")
def fix_trim(original, trimmed, output, dry_run):
    """Detect trim offset between ORIGINAL and TRIMMED videos, then sync the timestamp."""
    for path, label in [(original, "ORIGINAL"), (trimmed, "TRIMMED")]:
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            click.echo(
                click.style(f"Error: {label} must be a video file", fg="red"),
                err=True,
            )
            raise Exit(1)

    original_meta = extract_metadata(original)
    if not isinstance(original_meta, VideoMetadata) or original_meta.start_timestamp is None:
        click.echo(
            click.style("Error: Could not read start timestamp from original video", fg="red"),
            err=True,
        )
        raise Exit(1)

    try:
        offset_seconds = detect_trim_offset(original, trimmed)
    except OffsetDetectionError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        raise Exit(1)

    adjusted_start = original_meta.start_timestamp + timedelta(seconds=offset_seconds)

    trimmed_meta = extract_metadata(trimmed)
    duration = trimmed_meta.duration_seconds if isinstance(trimmed_meta, VideoMetadata) else None
    adjusted_end = adjusted_start + timedelta(seconds=duration) if duration else None

    if dry_run:
        click.echo(f"Detected offset: {offset_seconds:.3f}s")
        click.echo(f"Original start:  {original_meta.start_timestamp.isoformat()}")
        click.echo(f"Adjusted start:  {adjusted_start.isoformat()}")
        if adjusted_end:
            click.echo(f"Adjusted end:    {adjusted_end.isoformat()}")
        return

    target_path = output if output else trimmed
    if output:
        shutil.copy2(trimmed, output)

    ok = write_video_timestamp(target_path, adjusted_start)
    if not ok:
        click.echo(
            click.style(f"Error: Failed to write timestamp to {target_path}", fg="red"),
            err=True,
        )
        raise Exit(1)

    click.echo(f"Updated {target_path}")


@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", required=True, type=click.Path(path_type=Path))
@click.option("--format", "fmt", help="Output resolution like 1920x1080")
@click.option("--image-duration", default=3.5, type=float, help="Seconds to show each image")
@click.option("--keep-temp", is_flag=True, help="Preserve temporary files")
@click.option("--dry-run", is_flag=True, help="Preview timeline without generating output")
@click.option("--recursive", "-r", is_flag=True, help="Scan directories recursively")
@click.option("--draft", is_flag=True, help="Render a low-quality draft for faster preview")
@click.option("--plan", type=click.Path(path_type=Path), help="Write stitch plan as JSON and exit")
@click.option("--margin", default=15.0, type=float, help="White space margin percentage on each side (default: 15)")
def stitch_cmd(path, output, fmt, image_duration, keep_temp, dry_run, recursive, draft, plan, margin):
    """Stitch photos and videos into a single chronological video."""
    files = collect_files([path], recursive)

    if not files:
        click.echo("No media files found.")
        return

    timeline = build_timeline_from_files(files)
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

    if plan:
        plan_data = generate_plan(timeline, output, frame_width, frame_height, image_duration, draft, margin)
        plan.write_text(json.dumps(plan_data, indent=2))
        click.echo(f"Plan written to {plan}")
        return

    click.echo(format_timeline(all_entries, image_duration))

    if dry_run:
        return

    if draft:
        frame_width, frame_height = compute_draft_resolution(frame_width, frame_height)

    click.echo(f"\nOutput: {output}")
    click.echo(f"Resolution: {frame_width}x{frame_height}")
    click.echo("Generating clips and stitching...")

    ok = stitch(timeline, output, frame_width, frame_height, image_duration, keep_temp, draft=draft, margin=margin)
    if ok:
        click.echo(click.style("Done!", fg="green"))
    else:
        click.echo(click.style("Error: Stitching failed.", fg="red"), err=True)
        raise Exit(1)


@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--port", default=8080, type=int, help="Server port")
@click.option("--recursive", "-r", is_flag=True)
@click.option("--image-duration", default=3.5, type=float)
def web(path, port, recursive, image_duration):
    """Start a local web server for timeline preview."""
    if not HAS_WEB:
        click.echo(
            click.style(
                "Error: Web dependencies not installed. Run: uv pip install -e '.[web]'",
                fg="red",
            ),
            err=True,
        )
        raise Exit(1)

    app = build_app_from_path(path, recursive=recursive, image_duration=image_duration)
    if not app.state.media_count:
        click.echo("No media files found.")
        return
    click.echo(click.style(f"Starting server at http://127.0.0.1:{port}", fg="green"))
    click.echo("Press Ctrl+C to stop")

    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
