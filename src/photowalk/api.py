"""High-level API: given a file path, return the appropriate metadata model."""

from pathlib import Path
from typing import Optional, Union

from photowalk.constants import PHOTO_EXTENSIONS, VIDEO_EXTENSIONS
from photowalk.extractors import run_ffprobe
from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.parsers import parse_photo_from_exif, parse_video
from photowalk.photo_extractors import extract_photo_exif


MetadataResult = Union[PhotoMetadata, VideoMetadata, None]


def extract_metadata(path: Path) -> MetadataResult:
    """Extract metadata from a single file path.

    Returns None for unsupported file types.
    Returns a metadata model with all fields None if extraction fails.
    """
    ext = path.suffix.lower()

    if ext in PHOTO_EXTENSIONS:
        data = extract_photo_exif(path)
        return parse_photo_from_exif(path, data)

    if ext in VIDEO_EXTENSIONS:
        data = run_ffprobe(path)
        if data is None:
            return VideoMetadata(source_path=path)
        return parse_video(path, data)

    return None
