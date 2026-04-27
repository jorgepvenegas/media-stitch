"""Photo Walk — Media metadata extraction using ffprobe."""

__version__ = "0.1.0"

from photowalk.api import extract_metadata
from photowalk.models import PhotoMetadata, VideoMetadata

__all__ = ["extract_metadata", "PhotoMetadata", "VideoMetadata"]
