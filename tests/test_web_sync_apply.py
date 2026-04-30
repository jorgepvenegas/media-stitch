from datetime import datetime, timedelta
from pathlib import Path

from photowalk.catalog import MediaCatalog
from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.use_cases.sync import SyncUseCase


def _entry(delta: float, paths: list[str]):
    class FakeEntry:
        def __init__(self):
            self.delta_seconds = delta
            self.target_paths = paths
    return FakeEntry()


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
    catalog = MediaCatalog([_photo("/a.jpg", datetime(2024, 1, 1, 12, 0, 0))])
    photo_calls = []
    video_calls = []

    def fake_photo(path, dt):
        photo_calls.append((str(path), dt))
        return True

    def fake_video(path, dt):
        video_calls.append((str(path), dt))
        return True

    deltas = {"/a.jpg": 3600.0}
    result = SyncUseCase().execute(
        catalog,
        deltas,
        write_photo=fake_photo,
        write_video=fake_video,
    )

    assert photo_calls == [("/a.jpg", datetime(2024, 1, 1, 13, 0, 0))]
    assert video_calls == []
    assert len(result.applied) == 1
    assert result.applied[0]["path"] == "/a.jpg"
    assert result.applied[0]["old_ts"] == "2024-01-01T12:00:00"
    assert result.applied[0]["new_ts"] == "2024-01-01T13:00:00"
    assert result.failed == []


def test_apply_offsets_dispatches_video_to_video_writer():
    catalog = MediaCatalog([_video("/v.mp4", datetime(2024, 1, 1, 12, 0, 0), 60.0)])
    video_calls = []

    def fake_video(path, dt):
        video_calls.append((str(path), dt))
        return True

    deltas = {"/v.mp4": 60.0}
    result = SyncUseCase().execute(
        catalog,
        deltas,
        write_photo=lambda p, d: True,
        write_video=fake_video,
    )

    assert video_calls == [("/v.mp4", datetime(2024, 1, 1, 12, 1, 0))]
    assert len(result.applied) == 1


def test_apply_offsets_compose_stack_writes_once_per_file():
    catalog = MediaCatalog([_photo("/a.jpg", datetime(2024, 1, 1, 12, 0, 0))])
    photo_calls = []

    def fake_photo(path, dt):
        photo_calls.append(dt)
        return True

    deltas = {"/a.jpg": 1800.0}
    SyncUseCase().execute(
        catalog,
        deltas,
        write_photo=fake_photo,
        write_video=lambda p, d: True,
    )

    assert photo_calls == [datetime(2024, 1, 1, 12, 30, 0)]


def test_apply_offsets_skips_zero_net_delta():
    catalog = MediaCatalog([_photo("/a.jpg", datetime(2024, 1, 1, 12, 0, 0))])
    photo_calls = []

    def fake_photo(path, dt):
        photo_calls.append(dt)
        return True

    deltas = {}
    result = SyncUseCase().execute(
        catalog,
        deltas,
        write_photo=fake_photo,
        write_video=lambda p, d: True,
    )

    assert photo_calls == []
    assert result.applied == []
    assert result.failed == []


def test_apply_offsets_records_failure_and_continues():
    catalog = MediaCatalog([
        _photo("/a.jpg", datetime(2024, 1, 1, 12, 0, 0)),
        _photo("/b.jpg", datetime(2024, 1, 1, 13, 0, 0)),
    ])

    def fake_photo(path, dt):
        return str(path) != "/a.jpg"

    deltas = {"/a.jpg": 60.0, "/b.jpg": 60.0}
    result = SyncUseCase().execute(
        catalog,
        deltas,
        write_photo=fake_photo,
        write_video=lambda p, d: True,
    )

    failed_paths = [f["path"] for f in result.failed]
    applied_paths = [a["path"] for a in result.applied]
    assert failed_paths == ["/a.jpg"]
    assert applied_paths == ["/b.jpg"]


def test_apply_offsets_skips_files_without_timestamp():
    catalog = MediaCatalog([_photo("/a.jpg", None)])
    photo_calls = []

    deltas = {"/a.jpg": 60.0}
    SyncUseCase().execute(
        catalog,
        deltas,
        write_photo=lambda p, d: photo_calls.append(d) or True,
        write_video=lambda p, d: True,
    )

    assert photo_calls == []


def test_apply_offsets_writer_exception_recorded_as_failure():
    catalog = MediaCatalog([_photo("/a.jpg", datetime(2024, 1, 1, 12, 0, 0))])

    def fake_photo(path, dt):
        raise OSError("permission denied")

    deltas = {"/a.jpg": 60.0}
    result = SyncUseCase().execute(
        catalog,
        deltas,
        write_photo=fake_photo,
        write_video=lambda p, d: True,
    )

    assert result.applied == []
    assert len(result.failed) == 1
    assert "permission denied" in result.failed[0]["error"]
