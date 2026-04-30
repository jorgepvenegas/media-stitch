"""Stitch use-case: plan generation and execution."""

from pathlib import Path
from typing import Optional

from photowalk.catalog import MediaCatalog
from photowalk.extractors import run_ffprobe
from photowalk.stitcher import compute_draft_resolution, generate_plan, stitch
from photowalk.use_cases.errors import UseCaseError


class StitchUseCase:
    def resolve_resolution(
        self,
        catalog: MediaCatalog,
        fmt: Optional[str],
    ) -> tuple[int, int]:
        """Determine output resolution from explicit format or first video."""
        if fmt:
            try:
                width, height = map(int, fmt.split("x"))
                return width, height
            except ValueError:
                raise UseCaseError('Format must be WIDTHxHEIGHT (e.g. 1920x1080)')

        frame_width, frame_height = 1920, 1080
        timeline = catalog.timeline()
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
        return frame_width, frame_height

    def generate_plan(
        self,
        catalog: MediaCatalog,
        output: Path,
        *,
        resolution: Optional[str] = None,
        image_duration: float = 3.5,
        draft: bool = False,
        margin: float = 15.0,
    ) -> dict:
        """Generate a plan dict describing how execution would process the timeline."""
        timeline = catalog.timeline()
        frame_width, frame_height = self.resolve_resolution(catalog, resolution)
        if draft:
            frame_width, frame_height = compute_draft_resolution(frame_width, frame_height)
        return generate_plan(timeline, output, frame_width, frame_height, image_duration, draft, margin)

    def execute(
        self,
        catalog: MediaCatalog,
        output: Path,
        *,
        frame_width: int = 1920,
        frame_height: int = 1080,
        image_duration: float = 3.5,
        keep_temp: bool = False,
        draft: bool = False,
        margin: float = 15.0,
    ) -> bool:
        """Stitch all segments into a single output video."""
        timeline = catalog.timeline()
        return stitch(
            timeline,
            output,
            frame_width,
            frame_height,
            image_duration=image_duration,
            keep_temp=keep_temp,
            draft=draft,
            margin=margin,
        )
