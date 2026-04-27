"""Extract EXIF metadata from photos using Pillow."""

from pathlib import Path
from typing import Optional

from PIL import Image, ExifTags


# EXIF tag name → our field name mapping
_TAG_MAP = {
    "DateTimeOriginal": "timestamp",
    "DateTime": "timestamp",
    "Make": "make",
    "Model": "model",
    "ExposureTime": "shutter_speed",
    "ISOSpeedRatings": "iso",
    "PhotographicSensitivity": "iso",
    "FocalLength": "focal_length",
}


def _format_exposure_time(value) -> str:
    """Format ExposureTime as human-readable string."""
    if isinstance(value, tuple) and len(value) == 2:
        num, den = value
        if num == 1:
            return f"1/{den}"
        return f"{num}/{den}"
    return str(value)


def _format_focal_length(value) -> str:
    """Format FocalLength with mm suffix."""
    if isinstance(value, tuple) and len(value) == 2:
        num, den = value
        mm = num / den if den else num
        return f"{mm:.0f}mm" if mm == int(mm) else f"{mm:.1f}mm"
    if isinstance(value, (int, float)):
        return f"{value:.0f}mm" if value == int(value) else f"{value:.1f}mm"
    return str(value)


def extract_photo_exif(path: Path) -> dict:
    """Extract EXIF tags from a photo file using Pillow.

    Returns a dict with keys: timestamp, make, model, shutter_speed, iso, focal_length.
    Missing fields are omitted from the dict.
    """
    result = {}
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if exif is None:
                return result

            for tag_id, value in exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                field = _TAG_MAP.get(tag_name)
                if field is None:
                    continue

                if field == "timestamp":
                    # EXIF DateTime format: "2024:07:15 14:32:10"
                    if isinstance(value, str):
                        result[field] = value.replace(":", "-", 2)
                elif field == "make":
                    result[field] = str(value).strip()
                elif field == "model":
                    result[field] = str(value).strip()
                elif field == "shutter_speed":
                    result[field] = _format_exposure_time(value)
                elif field == "iso":
                    try:
                        result[field] = int(value)
                    except (ValueError, TypeError):
                        pass
                elif field == "focal_length":
                    result[field] = _format_focal_length(value)
    except Exception:
        pass

    return result
