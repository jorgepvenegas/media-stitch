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
    "ShutterSpeedValue": "shutter_speed_apex",  # fallback only
    "ISOSpeedRatings": "iso",
    "PhotographicSensitivity": "iso",
    "FocalLength": "focal_length",
}


def _format_exposure_time(value) -> Optional[str]:
    """Format ExposureTime as human-readable string like '1/250'."""
    if isinstance(value, tuple) and len(value) == 2:
        num, den = value
        if num == 1:
            return f"1/{den}"
        return f"{num}/{den}"
    # Try to convert to float (handles IFDRational, float, int)
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if seconds == 0:
        return None
    if seconds >= 1:
        return f"{seconds:g}s"
    # Convert to fraction: 0.004 -> 1/250
    den = round(1 / seconds)
    return f"1/{den}"


def _format_focal_length(value) -> Optional[str]:
    """Format FocalLength with mm suffix."""
    if isinstance(value, tuple) and len(value) == 2:
        num, den = value
        mm = num / den if den else num
        return f"{mm:.0f}mm" if mm == int(mm) else f"{mm:.1f}mm"
    if isinstance(value, (int, float)):
        return f"{value:.0f}mm" if value == int(value) else f"{value:.1f}mm"
    return str(value)


def _extract_ifd(exif_dict) -> dict:
    """Extract mapped fields from a single EXIF IFD dictionary."""
    result = {}
    for tag_id, value in exif_dict.items():
        tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
        field = _TAG_MAP.get(tag_name)
        if field is None:
            continue

        if field == "timestamp":
            if isinstance(value, str):
                # EXIF DateTime format: "2024:07:15 14:32:10"
                result[field] = value.replace(":", "-", 2)
        elif field == "make":
            result["make"] = str(value).strip()
        elif field == "model":
            result["model"] = str(value).strip()
        elif field == "shutter_speed":
            formatted = _format_exposure_time(value)
            if formatted:
                result["shutter_speed"] = formatted
        elif field == "iso":
            try:
                result["iso"] = int(value)
            except (ValueError, TypeError):
                pass
        elif field == "focal_length":
            result["focal_length"] = _format_focal_length(value)
    return result


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

            # Primary IFD
            result.update(_extract_ifd(exif))

            # Exif IFD (contains camera settings: ExposureTime, ISO, FocalLength, etc.)
            exif_offset = exif.get(0x8769)
            if exif_offset:
                exif_ifd = exif.get_ifd(0x8769)
                if exif_ifd:
                    result.update(_extract_ifd(exif_ifd))
    except Exception:
        pass

    return result
