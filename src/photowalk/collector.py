"""Collect media files from paths with type filtering."""

from pathlib import Path

from photowalk.constants import PHOTO_EXTENSIONS, VIDEO_EXTENSIONS


def collect_files(
    paths: list[Path],
    recursive: bool,
    include_photos: bool = True,
    include_videos: bool = True,
) -> list[Path]:
    """Collect media files from a list of paths, with optional type filtering.

    Args:
        paths: File or directory paths to scan.
        recursive: If True, scan directories recursively.
        include_photos: If False, exclude photo files.
        include_videos: If False, exclude video files.

    Returns:
        List of media file paths matching the filters.
    """
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

    if not include_photos:
        files = [f for f in files if f.suffix.lower() not in PHOTO_EXTENSIONS]
    if not include_videos:
        files = [f for f in files if f.suffix.lower() not in VIDEO_EXTENSIONS]

    return files
