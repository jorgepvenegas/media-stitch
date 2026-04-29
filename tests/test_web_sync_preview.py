from datetime import datetime, timedelta
from pathlib import Path

from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.web.sync_models import OffsetEntry
from photowalk.web.sync_preview import compute_net_deltas, shift_pairs


def _entry(delta: float, paths: list[str]) -> OffsetEntry:
    return OffsetEntry(
        id="x",
        delta_seconds=delta,
        source={"kind": "duration", "text": "0s"},
        target_paths=paths,
    )


def test_compute_net_deltas_empty_stack():
    assert compute_net_deltas([]) == {}


def test_compute_net_deltas_single_entry():
    deltas = compute_net_deltas([_entry(60.0, ["/a", "/b"])])
    assert deltas == {"/a": 60.0, "/b": 60.0}


def test_compute_net_deltas_compose_same_path():
    stack = [_entry(3600.0, ["/a"]), _entry(-1800.0, ["/a"])]
    assert compute_net_deltas(stack) == {"/a": 1800.0}


def test_compute_net_deltas_disjoint_paths():
    stack = [_entry(60.0, ["/a"]), _entry(120.0, ["/b"])]
    assert compute_net_deltas(stack) == {"/a": 60.0, "/b": 120.0}


def test_compute_net_deltas_excludes_zero_net():
    stack = [_entry(60.0, ["/a"]), _entry(-60.0, ["/a"])]
    assert "/a" not in compute_net_deltas(stack)


def _photo(path: str, ts: datetime | None) -> tuple[Path, PhotoMetadata]:
    return Path(path), PhotoMetadata(source_path=Path(path), timestamp=ts)


def _video(path: str, start: datetime | None, dur: float | None) -> tuple[Path, VideoMetadata]:
    end = start + timedelta(seconds=dur) if (start and dur) else None
    return Path(path), VideoMetadata(
        source_path=Path(path),
        start_timestamp=start,
        end_timestamp=end,
        duration_seconds=dur,
    )


def test_shift_pairs_no_deltas_returns_equivalent():
    pairs = [_photo("/a.jpg", datetime(2024, 1, 1, 12, 0, 0))]
    out, shifted = shift_pairs(pairs, {})
    assert out[0][1].timestamp == datetime(2024, 1, 1, 12, 0, 0)
    assert shifted == set()


def test_shift_pairs_shifts_targeted_photo():
    pairs = [
        _photo("/a.jpg", datetime(2024, 1, 1, 12, 0, 0)),
        _photo("/b.jpg", datetime(2024, 1, 1, 13, 0, 0)),
    ]
    out, shifted = shift_pairs(pairs, {"/a.jpg": 3600.0})
    out_map = {str(p): m for p, m in out}
    assert out_map["/a.jpg"].timestamp == datetime(2024, 1, 1, 13, 0, 0)
    assert out_map["/b.jpg"].timestamp == datetime(2024, 1, 1, 13, 0, 0)
    assert shifted == {"/a.jpg"}


def test_shift_pairs_shifts_video_start_and_end():
    start = datetime(2024, 1, 1, 12, 0, 0)
    pairs = [_video("/v.mp4", start, 60.0)]
    out, shifted = shift_pairs(pairs, {"/v.mp4": 600.0})
    _, meta = out[0]
    assert meta.start_timestamp == datetime(2024, 1, 1, 12, 10, 0)
    assert meta.end_timestamp == datetime(2024, 1, 1, 12, 11, 0)
    assert meta.duration_seconds == 60.0
    assert shifted == {"/v.mp4"}


def test_shift_pairs_skips_files_without_timestamp():
    pairs = [
        _photo("/a.jpg", None),
        _video("/v.mp4", None, None),
    ]
    out, shifted = shift_pairs(pairs, {"/a.jpg": 60.0, "/v.mp4": 60.0})
    assert out[0][1].timestamp is None
    assert out[1][1].start_timestamp is None
    assert shifted == set()


def test_shift_pairs_does_not_mutate_inputs():
    original = _photo("/a.jpg", datetime(2024, 1, 1, 12, 0, 0))
    pairs = [original]
    shift_pairs(pairs, {"/a.jpg": 3600.0})
    assert pairs[0][1].timestamp == datetime(2024, 1, 1, 12, 0, 0)
