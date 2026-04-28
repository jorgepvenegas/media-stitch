"""Click CLI for photowalk."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click

from photowalk.api import extract_metadata
from photowalk.constants import PHOTO_EXTENSIONS, VIDEO_EXTENSIONS
from photowalk.extractors import ffprobe_not_found_error, run_ffprobe
from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.offset import compute_offset, OffsetError
from photowalk.writers import write_photo_timestamp, write_video_timestamp


def _collect_files(paths: list[Path], recursive: bool) -> list[Path]:
    """Collect media files from a list of paths."""
    files = []
    for path in paths:
        if path.is_file():
            if path.suffix.lower() in PHOTO_EXTENSIONS | VIDEO_EXTENSIONS:
                files.append(path)
        elif path.is_dir():
            pattern = "**/*" if recursive else "*"
            for child in path.glob(pattern):
                if child.is_file() and child.suffix.lower() in PHOTO_EXTENSIONS | VIDEO_EXTENSIONS:
                    files.append(child)
    return files


def _format_table(results: list[PhotoMetadata | VideoMetadata]) -> str:
    lines = []
    lines.append(f"{'File':<40} {'Type':<8} {'Timestamp':<25} {'Details'}")
    lines.append("-" * 100)
    for r in results:
        name = str(r.source_path)[:39]
        if isinstance(r, PhotoMetadata):
            ts = r.timestamp.isoformat() if r.timestamp else "N/A"
            details = f"{r.camera_model or 'N/A'} | ISO {r.iso or 'N/A'} | {r.focal_length or 'N/A'}"
            lines.append(f"{name:<40} {'photo':<8} {ts:<25} {details}")
        else:
            start = r.start_timestamp.isoformat() if r.start_timestamp else "N/A"
            end = r.end_timestamp.isoformat() if r.end_timestamp else "N/A"
            dur = f"{r.duration_seconds:.1f}s" if r.duration_seconds else "N/A"
            lines.append(f"{name:<40} {'video':<8} {start:<25} end={end} dur={dur}")
    return "\n".join(lines)


def _format_csv(results: list[PhotoMetadata | VideoMetadata]) -> str:
    lines = ["source_path,media_type,timestamp,camera_model,shutter_speed,iso,focal_length,start_timestamp,end_timestamp,duration_seconds"]
    for r in results:
        d = r.to_dict()
        lines.append(
            f'"{d["source_path"]}",{d["media_type"]},'
            f'"{d.get("timestamp") or ""}","{d.get("camera_model") or ""}",'
            f'"{d.get("shutter_speed") or ""}",{d.get("iso") or ""},'
            f'"{d.get("focal_length") or ""}","{d.get("start_timestamp") or ""}",'
            f'"{d.get("end_timestamp") or ""}",{d.get("duration_seconds") or ""}'
        )
    return "\n".join(lines)


def _format_timedelta(td: timedelta) -> str:
    """Format a timedelta as a human-readable string like '-8h 23m 5s'."""
    total_seconds = int(td.total_seconds())
    sign = "-" if total_seconds < 0 else "+"
    total_seconds = abs(total_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds:
        parts.append(f"{seconds}s")
    return sign + " ".join(parts) if parts else "0s"


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
        raise click.Exit(1)

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
        files = _collect_files(list(paths), recursive)
    except RuntimeError as e:
        click.echo(click.style(str(e), fg="red"), err=True)
        raise click.Exit(1)

    if not include_photos:
        files = [f for f in files if f.suffix.lower() not in PHOTO_EXTENSIONS]
    if not include_videos:
        files = [f for f in files if f.suffix.lower() not in VIDEO_EXTENSIONS]

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
        click.echo(_format_csv(results))
    else:
        click.echo(_format_table(results))


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
        raise click.Exit(1)

    try:
        files = _collect_files(list(paths), recursive)
    except RuntimeError as e:
        click.echo(click.style(str(e), fg="red"), err=True)
        raise click.Exit(1)

    if not include_photos:
        files = [f for f in files if f.suffix.lower() not in PHOTO_EXTENSIONS]
    if not include_videos:
        files = [f for f in files if f.suffix.lower() not in VIDEO_EXTENSIONS]

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

    # Show preview table
    lines = []
    lines.append(f"{'File':<40} {'Current Timestamp':<30} {'New Timestamp':<30} {'Delta'}")
    lines.append("-" * 120)
    for f, current, new_time, reason in preview:
        name = str(f)[:39]
        if reason:
            lines.append(f"{name:<40} {'N/A':<30} {'N/A':<30} {reason}")
        else:
            cur_str = current.isoformat() if current else "N/A"
            new_str = new_time.isoformat() if new_time else "N/A"
            lines.append(f"{name:<40} {cur_str:<30} {new_str:<30} {_format_timedelta(delta)}")
    click.echo("\n".join(lines))

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


if __name__ == "__main__":
    main()
