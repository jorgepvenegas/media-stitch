from datetime import datetime, timedelta
from pathlib import Path

from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.web.sync_models import OffsetEntry
from photowalk.web.sync_apply import apply_offsets


def _entry(delta: float, paths: list[str]) -> OffsetEntry:
    return OffsetEntry(
        id="x",
        delta_seconds=delta,
        source={"kind": "duration", "text": "0s"},
        target_paths=paths,
    )


def _photo(path: str, ts):
    return Path(path), PhotoMetadata(source_path=Path(path), timestamp=ts)


def _video(path: str, start, dur):
    end = start + timedelta(seconds=dur) if (start and dur) else None
    return Path(path), VideoMetadata(
        source_path=Path(path),
        start_timestamp=start,
        end_timestamp=end,
        duration_seconds=dur,
    )


def test_apply_offsets_writes_photo_with_shifted_timestamp():
    pairs = [_photo("/a.jpg", datetime(2024, 1, 1, 12, 0, 0))]
    photo_calls = []
    video_calls = []

    def fake_photo(path, dt):
        photo_calls.append((str(path), dt))
        return True

    def fake_video(path, dt):
        video_calls.append((str(path), dt))
        return True

    result = apply_offsets(
        pairs,
        [_entry(3600.0, ["/a.jpg"])],
        write_photo=fake_photo,
        write_video=fake_video,
    )

    assert photo_calls == [("/a.jpg", datetime(2024, 1, 1, 13, 0, 0))]
    assert video_calls == []
    assert len(result["applied"]) == 1
    assert result["applied"][0]["path"] == "/a.jpg"
    assert result["applied"][0]["old_ts"] == "2024-01-01T12:00:00"
    assert result["applied"][0]["new_ts"] == "2024-01-01T13:00:00"
    assert result["failed"] == []


def test_apply_offsets_dispatches_video_to_video_writer():
    pairs = [_video("/v.mp4", datetime(2024, 1, 1, 12, 0, 0), 60.0)]
    video_calls = []

    def fake_video(path, dt):
        video_calls.append((str(path), dt))
        return True

    result = apply_offsets(
        pairs,
        [_entry(60.0, ["/v.mp4"])],
        write_photo=lambda p, d: True,
        write_video=fake_video,
    )

    assert video_calls == [("/v.mp4", datetime(2024, 1, 1, 12, 1, 0))]
    assert len(result["applied"]) == 1


def test_apply_offsets_compose_stack_writes_once_per_file():
    pairs = [_photo("/a.jpg", datetime(2024, 1, 1, 12, 0, 0))]
    photo_calls = []

    def fake_photo(path, dt):
        photo_calls.append(dt)
        return True

    apply_offsets(
        pairs,
        [_entry(3600.0, ["/a.jpg"]), _entry(-1800.0, ["/a.jpg"])],
        write_photo=fake_photo,
        write_video=lambda p, d: True,
    )

    assert photo_calls == [datetime(2024, 1, 1, 12, 30, 0)]


def test_apply_offsets_skips_zero_net_delta():
    pairs = [_photo("/a.jpg", datetime(2024, 1, 1, 12, 0, 0))]
    photo_calls = []

    def fake_photo(path, dt):
        photo_calls.append(dt)
        return True

    result = apply_offsets(
        pairs,
        [_entry(60.0, ["/a.jpg"]), _entry(-60.0, ["/a.jpg"])],
        write_photo=fake_photo,
        write_video=lambda p, d: True,
    )

    assert photo_calls == []
    assert result["applied"] == []
    assert result["failed"] == []


def test_apply_offsets_records_failure_and_continues():
    pairs = [
        _photo("/a.jpg", datetime(2024, 1, 1, 12, 0, 0)),
        _photo("/b.jpg", datetime(2024, 1, 1, 13, 0, 0)),
    ]

    def fake_photo(path, dt):
        if str(path) == "/a.jpg":
            return False
        return True

    result = apply_offsets(
        pairs,
        [_entry(60.0, ["/a.jpg", "/b.jpg"])],
        write_photo=fake_photo,
        write_video=lambda p, d: True,
    )

    failed_paths = [f["path"] for f in result["failed"]]
    applied_paths = [a["path"] for a in result["applied"]]
    assert failed_paths == ["/a.jpg"]
    assert applied_paths == ["/b.jpg"]


def test_apply_offsets_skips_files_without_timestamp():
    pairs = [_photo("/a.jpg", None)]
    photo_calls = []

    apply_offsets(
        pairs,
        [_entry(60.0, ["/a.jpg"])],
        write_photo=lambda p, d: photo_calls.append(d) or True,
        write_video=lambda p, d: True,
    )

    assert photo_calls == []


def test_apply_offsets_writer_exception_recorded_as_failure():
    pairs = [_photo("/a.jpg", datetime(2024, 1, 1, 12, 0, 0))]

    def fake_photo(path, dt):
        raise OSError("permission denied")

    result = apply_offsets(
        pairs,
        [_entry(60.0, ["/a.jpg"])],
        write_photo=fake_photo,
        write_video=lambda p, d: True,
    )

    assert result["applied"] == []
    assert len(result["failed"]) == 1
    assert "permission denied" in result["failed"][0]["error"]
