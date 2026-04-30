"""Click CLI for photowalk."""

import json
from pathlib import Path

import click
from click.exceptions import Exit

from photowalk.catalog import MediaCatalog
from photowalk.constants import VIDEO_EXTENSIONS
from photowalk.formatters import (
    format_csv,
    format_sync_preview,
    format_table,
    format_timeline,
)
from photowalk.offset import compute_offset, OffsetError
from photowalk.stitcher import compute_draft_resolution
from photowalk.use_cases import (
    BatchUseCase,
    FixTrimUseCase,
    StitchUseCase,
    SyncUseCase,
    UseCaseError,
)
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
    from photowalk.api import extract_metadata
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
    catalog = MediaCatalog.scan(
        list(paths),
        recursive=recursive,
        include_photos=include_photos,
        include_videos=include_videos,
    )

    if not catalog.pairs:
        click.echo("No media files found.")
        return

    result = BatchUseCase().run(catalog, output)
    click.echo(result.formatted_output)


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

    catalog = MediaCatalog.scan(
        list(paths),
        recursive=recursive,
        include_photos=include_photos,
        include_videos=include_videos,
    )

    if not catalog.pairs:
        click.echo("No media files found.")
        return

    use_case = SyncUseCase()
    preview = use_case.build_cli_preview(catalog, delta)
    click.echo(format_sync_preview(preview, delta))

    if dry_run:
        return

    writable = [item for item in preview if item.skip_reason is None]
    if not writable:
        click.echo("No files to update.")
        return

    if not yes:
        prompt = f"Apply timestamp offset to {len(writable)} file(s)? [y/N]: "
        response = click.prompt(prompt, default="n", show_default=False)
        if response.lower() not in ("y", "yes"):
            click.echo("Cancelled.")
            return

    deltas = {str(item.path): delta.total_seconds() for item in writable}
    result = use_case.execute(
        catalog,
        deltas,
        write_photo=write_photo_timestamp,
        write_video=write_video_timestamp,
    )

    skipped_count = len(preview) - len(writable)
    fail_count = len(writable) - len(result.applied)
    msg = f"Updated {len(result.applied)} of {len(writable)} file(s)."
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

    try:
        result = FixTrimUseCase().run(original, trimmed, output=output, dry_run=dry_run)
    except UseCaseError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        raise Exit(1)

    if dry_run:
        click.echo(f"Detected offset: {result.offset_seconds:.3f}s")
        click.echo(f"Original start:  {result.original_start.isoformat()}")
        click.echo(f"Adjusted start:  {result.adjusted_start.isoformat()}")
        if result.adjusted_end:
            click.echo(f"Adjusted end:    {result.adjusted_end.isoformat()}")
        return

    click.echo(f"Updated {result.target_path}")


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
    catalog = MediaCatalog.scan([path], recursive=recursive)

    if not catalog.pairs:
        click.echo("No media files found.")
        return

    use_case = StitchUseCase()
    timeline = catalog.timeline()
    all_entries = timeline.all_entries

    if not all_entries:
        click.echo("No usable media found (all files missing timestamps).")
        return

    if plan:
        try:
            plan_data = use_case.generate_plan(
                catalog,
                output,
                resolution=fmt,
                image_duration=image_duration,
                draft=draft,
                margin=margin,
            )
        except UseCaseError as e:
            click.echo(click.style(f"Error: {e}", fg="red"), err=True)
            raise Exit(1)
        plan.write_text(json.dumps(plan_data, indent=2))
        click.echo(f"Plan written to {plan}")
        return

    click.echo(format_timeline(all_entries, image_duration))

    if dry_run:
        return

    try:
        frame_width, frame_height = use_case.resolve_resolution(catalog, fmt)
    except UseCaseError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        raise Exit(1)

    if draft:
        frame_width, frame_height = compute_draft_resolution(frame_width, frame_height)

    click.echo(f"\nOutput: {output}")
    click.echo(f"Resolution: {frame_width}x{frame_height}")
    click.echo("Generating clips and stitching...")

    ok = use_case.execute(
        catalog,
        output,
        frame_width=frame_width,
        frame_height=frame_height,
        image_duration=image_duration,
        keep_temp=keep_temp,
        draft=draft,
        margin=margin,
    )
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
