"""Parse duration strings and reference timestamps into timedelta offsets."""

import re
from datetime import datetime, timedelta, timezone


class OffsetError(Exception):
    """Raised when a duration or reference string cannot be parsed."""


_DURATION_RE = re.compile(r"^([+-]?)(\d+h)?(\d+m)?(\d+s)?$")


def parse_duration(value: str) -> timedelta:
    """Parse a duration string like '-8h23m5s' or '+2h' into a timedelta.

    Format: [+/-][Nh][Nm][Ns] — at least one component required.
    """
    value = value.strip()
    if not value:
        raise OffsetError("Duration string cannot be empty")

    match = _DURATION_RE.match(value)
    if not match:
        raise OffsetError(f"Invalid duration format: {value!r}. Expected format: [-][Nh][Nm][Ns]")

    sign_str, hours_str, minutes_str, seconds_str = match.groups()

    if not any((hours_str, minutes_str, seconds_str)):
        raise OffsetError(f"Invalid duration format: {value!r}. Expected format: [-][Nh][Nm][Ns]")

    sign = -1 if sign_str == "-" else 1

    def _parse_component(s: str | None, suffix: str) -> int:
        if s is None:
            return 0
        return int(s[:-1])  # strip suffix

    hours = _parse_component(hours_str, "h")
    minutes = _parse_component(minutes_str, "m")
    seconds = _parse_component(seconds_str, "s")

    return sign * timedelta(hours=hours, minutes=minutes, seconds=seconds)


def _normalize_for_subtraction(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware for subtraction.

    Naive datetimes are assumed to be UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def parse_reference(value: str) -> timedelta:
    """Parse a reference timestamp pair like 'wrong=correct' into a timedelta.

    Delta = correct - wrong (the amount to add to wrong timestamps).
    """
    if "=" not in value:
        raise OffsetError(f"Invalid reference format: {value!r}. Expected: wrong=correct")

    wrong_str, correct_str = value.split("=", 1)

    try:
        wrong = datetime.fromisoformat(wrong_str.strip())
    except ValueError as e:
        raise OffsetError(f"Cannot parse 'wrong' timestamp: {wrong_str!r}") from e

    try:
        correct = datetime.fromisoformat(correct_str.strip())
    except ValueError as e:
        raise OffsetError(f"Cannot parse 'correct' timestamp: {correct_str!r}") from e

    wrong = _normalize_for_subtraction(wrong)
    correct = _normalize_for_subtraction(correct)

    return correct - wrong


def compute_offset(offset: str | None, reference: str | None) -> timedelta:
    """Compute a timedelta from either --offset or --reference.

    Exactly one must be provided.
    """
    if offset is not None and reference is not None:
        raise OffsetError("Specify either --offset or --reference, not both")

    if offset is None and reference is None:
        raise OffsetError("Specify either --offset or --reference")

    if offset is not None:
        return parse_duration(offset)

    return parse_reference(reference)
