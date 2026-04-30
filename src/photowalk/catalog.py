"""MediaCatalog — shared seam behind collect + extract + refresh."""

from dataclasses import dataclass
from pathlib import Path

from photowalk.api import extract_metadata
from photowalk.collector import collect_files
from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.timeline import MediaInput, build_timeline, TimelineMap


@dataclass(frozen=True)
class MediaCatalog:
    pairs: list[MediaInput]

    @classmethod
    def scan(
        cls,
        paths: list[Path],
        *,
        recursive: bool = False,
        include_photos: bool = True,
        include_videos: bool = True,
    ) -> "MediaCatalog":
        files = collect_files(paths, recursive, include_photos, include_videos)
        pairs: list[MediaInput] = []
        for f in files:
            meta = extract_metadata(f)
            if meta is not None:
                pairs.append((f, meta))
        return cls(pairs)

    def refresh(self) -> "MediaCatalog":
        pairs: list[MediaInput] = []
        for path, _ in self.pairs:
            meta = extract_metadata(path)
            if meta is not None:
                pairs.append((path, meta))
        return MediaCatalog(pairs)

    def filter(
        self,
        *,
        photos: bool = True,
        videos: bool = True,
    ) -> "MediaCatalog":
        if photos and videos:
            return self
        filtered: list[MediaInput] = []
        for path, meta in self.pairs:
            if isinstance(meta, PhotoMetadata) and photos:
                filtered.append((path, meta))
            elif isinstance(meta, VideoMetadata) and videos:
                filtered.append((path, meta))
        return MediaCatalog(filtered)

    def timeline(self, image_duration: float = 3.5) -> TimelineMap:
        return build_timeline(self.pairs)
