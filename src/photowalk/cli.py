"""Click CLI for photowalk."""

import json
from pathlib import Path

import click

from photowalk.api import extract_metadata
from photowalk.constants import PHOTO_EXTENSIONS, VIDEO_EXTENSIONS
from photowalk.extractors import ffprobe_not_found_error, run_ffprobe
from photowalk.models import PhotoMetadata, VideoMetadata


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


if __name__ == "__main__":
    main()
