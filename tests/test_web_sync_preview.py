from photowalk.web.sync_models import OffsetEntry
from photowalk.web.sync_preview import compute_net_deltas


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
