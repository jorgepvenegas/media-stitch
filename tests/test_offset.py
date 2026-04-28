from datetime import datetime, timedelta, timezone

import pytest

from photowalk.offset import (
    parse_duration,
    parse_reference,
    compute_offset,
    OffsetError,
)


class TestParseDuration:
    def test_positive_hours(self):
        assert parse_duration("+2h") == timedelta(hours=2)

    def test_negative_hours(self):
        assert parse_duration("-2h") == timedelta(hours=-2)

    def test_positive_minutes(self):
        assert parse_duration("+30m") == timedelta(minutes=30)

    def test_negative_minutes(self):
        assert parse_duration("-30m") == timedelta(minutes=-30)

    def test_positive_seconds(self):
        assert parse_duration("+45s") == timedelta(seconds=45)

    def test_negative_seconds(self):
        assert parse_duration("-45s") == timedelta(seconds=-45)

    def test_combined_positive(self):
        assert parse_duration("+1h30m5s") == timedelta(hours=1, minutes=30, seconds=5)

    def test_combined_negative(self):
        assert parse_duration("-8h23m5s") == timedelta(hours=-8, minutes=-23, seconds=-5)

    def test_hours_minutes_only(self):
        assert parse_duration("+2h30m") == timedelta(hours=2, minutes=30)

    def test_no_sign_defaults_positive(self):
        assert parse_duration("2h") == timedelta(hours=2)

    def test_empty_raises(self):
        with pytest.raises(OffsetError):
            parse_duration("")

    def test_invalid_format_raises(self):
        with pytest.raises(OffsetError):
            parse_duration("abc")

    def test_no_components_raises(self):
        with pytest.raises(OffsetError):
            parse_duration("+")

    def test_garbage_after_raises(self):
        with pytest.raises(OffsetError):
            parse_duration("+2hxyz")


class TestParseReference:
    def test_valid_reference(self):
        wrong = "2026-04-27T23:28:01+00:00"
        correct = "2026-04-27T07:05:00"
        result = parse_reference(f"{wrong}={correct}")
        assert result == timedelta(hours=-16, minutes=-23, seconds=-1)

    def test_reference_with_positive_delta(self):
        wrong = "2024-07-15T14:00:00"
        correct = "2024-07-15T16:00:00"
        result = parse_reference(f"{wrong}={correct}")
        assert result == timedelta(hours=2)

    def test_missing_equals_raises(self):
        with pytest.raises(OffsetError):
            parse_reference("2024-07-15T14:00:00")

    def test_unparseable_wrong_raises(self):
        with pytest.raises(OffsetError):
            parse_reference("not-a-date=2024-07-15T14:00:00")

    def test_unparseable_correct_raises(self):
        with pytest.raises(OffsetError):
            parse_reference("2024-07-15T14:00:00=not-a-date")


class TestComputeOffset:
    def test_from_duration(self):
        assert compute_offset(offset="+2h", reference=None) == timedelta(hours=2)

    def test_from_reference(self):
        wrong = "2026-04-27T23:28:01+00:00"
        correct = "2026-04-27T07:05:00"
        result = compute_offset(offset=None, reference=f"{wrong}={correct}")
        assert result == timedelta(hours=-16, minutes=-23, seconds=-1)

    def test_both_raises(self):
        with pytest.raises(OffsetError):
            compute_offset(offset="+2h", reference="a=b")

    def test_neither_raises(self):
        with pytest.raises(OffsetError):
            compute_offset(offset=None, reference=None)
