# Web UI Timestamp Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a sync feature to the photo-walk web UI: queue timestamp offsets against multi-selected photos/videos, preview the resulting timeline live, then write changes to disk via a confirmation modal.

**Architecture:** Browser-owned pending offset stack; stateless FastAPI server with three new endpoints (`/api/offset/parse`, `/api/timeline/preview`, `/api/sync/apply`) that reuse existing `offset.py`, `timeline.py`, and `writers.py`. Preview logic lives in `web/sync_preview.py` (pure, no I/O); apply logic in `web/sync_apply.py` (calls writers, re-extracts after).

**Tech Stack:** Python 3.10+, FastAPI, Pydantic, piexif, ffmpeg subprocess, vanilla JS in the browser.

**Spec:** `docs/superpowers/specs/2026-04-29-web-ui-sync-design.md`

---

## Conventions

- Tests live flat in `tests/`, matching existing convention (e.g. `test_web_server.py`).
- All new modules and tests follow existing style: `from __future__ import annotations` not used, type hints use `list[X]` / `dict[K,V]` syntax (Python 3.10+), no docstrings on trivial helpers.
- Run a single test: `uv run pytest tests/test_web_sync_preview.py::test_name -v`
- Run the whole suite: `uv run pytest`
- Dev server: `uv run photowalk web /path/to/sample/dir`. The repo has fixtures at `tests/fixtures/` you can point it at for manual checks.

## Domain Glossary

- **Offset entry**: one queued sync operation (`{ delta_seconds, source, target_paths }`).
- **Pending stack**: ordered list of offset entries; effects compose in order.
- **Net delta**: cumulative `delta_seconds` for a single path across the whole stack.
- **`MediaInput`**: `tuple[Path, PhotoMetadata | VideoMetadata]` — defined in `photowalk/timeline.py`.
- **Shifted file**: a file whose net delta ≠ 0 in the current preview response.

---

## Task 1: Pydantic request models

**Files:**
- Create: `src/photowalk/web/sync_models.py`
- Test: `tests/test_web_sync_endpoints.py` (will be expanded in later tasks)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_web_sync_endpoints.py
from pydantic import ValidationError
import pytest

from photowalk.web.sync_models import (
    DurationSource,
    ReferenceSource,
    OffsetEntry,
    ParseRequest,
    PreviewRequest,
    ApplyRequest,
)


def test_duration_source_parses():
    src = DurationSource(kind="duration", text="-8h23m5s")
    assert src.text == "-8h23m5s"


def test_reference_source_parses():
    src = ReferenceSource(
        kind="reference",
        wrong="2026-04-27T23:28:01+00:00",
        correct="2026-04-27T07:05:00",
    )
    assert src.wrong.startswith("2026")


def test_offset_entry_with_duration_source():
    entry = OffsetEntry(
        id="abc",
        delta_seconds=-30185.0,
        source={"kind": "duration", "text": "-8h23m5s"},
        target_paths=["/tmp/a.jpg", "/tmp/b.mp4"],
    )
    assert entry.delta_seconds == -30185.0
    assert len(entry.target_paths) == 2


def test_parse_request_duration():
    req = ParseRequest.model_validate(
        {"kind": "duration", "text": "+2h"}
    )
    assert req.root.kind == "duration"


def test_parse_request_reference():
    req = ParseRequest.model_validate(
        {"kind": "reference", "wrong": "2026-04-27T23:28:01", "correct": "2026-04-27T07:05:00"}
    )
    assert req.root.kind == "reference"


def test_preview_request_accepts_empty_stack():
    req = PreviewRequest(offsets=[])
    assert req.offsets == []


def test_preview_request_rejects_missing_field():
    with pytest.raises(ValidationError):
        PreviewRequest.model_validate({})


def test_apply_request_same_shape_as_preview():
    req = ApplyRequest(offsets=[])
    assert req.offsets == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_web_sync_endpoints.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'photowalk.web.sync_models'`

- [ ] **Step 3: Write the module**

```python
# src/photowalk/web/sync_models.py
from typing import Literal, Union

from pydantic import BaseModel, Field, RootModel


class DurationSource(BaseModel):
    kind: Literal["duration"]
    text: str


class ReferenceSource(BaseModel):
    kind: Literal["reference"]
    wrong: str
    correct: str


OffsetSource = Union[DurationSource, ReferenceSource]


class OffsetEntry(BaseModel):
    id: str
    delta_seconds: float
    source: OffsetSource = Field(discriminator="kind")
    target_paths: list[str]


class ParseRequest(RootModel[OffsetSource]):
    pass


class PreviewRequest(BaseModel):
    offsets: list[OffsetEntry]


class ApplyRequest(BaseModel):
    offsets: list[OffsetEntry]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_web_sync_endpoints.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/web/sync_models.py tests/test_web_sync_endpoints.py
git commit -m "feat(web): add pydantic models for sync endpoints"
```

---

## Task 2: Pure helper — `compute_net_deltas`

Computes per-path cumulative delta from a list of offset entries. Pure function, used by both preview and apply.

**Files:**
- Create: `src/photowalk/web/sync_preview.py`
- Test: `tests/test_web_sync_preview.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_web_sync_preview.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_web_sync_preview.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'photowalk.web.sync_preview'`

- [ ] **Step 3: Write the module**

```python
# src/photowalk/web/sync_preview.py
"""Preview-side logic: compute shifted timelines without touching disk."""

from photowalk.web.sync_models import OffsetEntry


def compute_net_deltas(offsets: list[OffsetEntry]) -> dict[str, float]:
    """Sum delta_seconds per path across the offset stack.

    Paths with a zero net delta are omitted from the result.
    """
    totals: dict[str, float] = {}
    for entry in offsets:
        for path in entry.target_paths:
            totals[path] = totals.get(path, 0.0) + entry.delta_seconds
    return {p: d for p, d in totals.items() if d != 0.0}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_web_sync_preview.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/web/sync_preview.py tests/test_web_sync_preview.py
git commit -m "feat(web): add compute_net_deltas helper for sync stack"
```

---

## Task 3: Pure helper — `shift_pairs`

Applies a per-path delta map to a list of `(path, meta)` pairs, returning new pairs with shifted timestamps. Original pairs are not mutated.

**Files:**
- Modify: `src/photowalk/web/sync_preview.py`
- Test: `tests/test_web_sync_preview.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_web_sync_preview.py`:

```python
from datetime import datetime, timedelta
from pathlib import Path

from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.web.sync_preview import shift_pairs


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_web_sync_preview.py -v`
Expected: FAIL with `ImportError: cannot import name 'shift_pairs'`

- [ ] **Step 3: Implement `shift_pairs`**

Append to `src/photowalk/web/sync_preview.py`:

```python
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.timeline import MediaInput


def shift_pairs(
    pairs: list[MediaInput],
    deltas_by_path: dict[str, float],
) -> tuple[list[MediaInput], set[str]]:
    """Return new (path, meta) pairs with timestamps shifted per delta map.

    Files with no timestamp, or paths absent from the delta map, are
    returned with their metadata unchanged.  The original pairs and
    metadata objects are not mutated (PhotoMetadata / VideoMetadata are
    frozen dataclasses; we use dataclasses.replace).

    Returns the new pairs list plus the set of path strings that were
    actually shifted (non-zero delta and a usable timestamp).
    """
    new_pairs: list[MediaInput] = []
    shifted: set[str] = set()

    for path, meta in pairs:
        delta = deltas_by_path.get(str(path), 0.0)

        if delta == 0.0:
            new_pairs.append((path, meta))
            continue

        td = timedelta(seconds=delta)

        if isinstance(meta, PhotoMetadata):
            if meta.timestamp is None:
                new_pairs.append((path, meta))
                continue
            new_meta = replace(meta, timestamp=meta.timestamp + td)
            new_pairs.append((path, new_meta))
            shifted.add(str(path))

        elif isinstance(meta, VideoMetadata):
            if meta.start_timestamp is None:
                new_pairs.append((path, meta))
                continue
            new_start = meta.start_timestamp + td
            new_end = meta.end_timestamp + td if meta.end_timestamp else None
            new_meta = replace(
                meta,
                start_timestamp=new_start,
                end_timestamp=new_end,
            )
            new_pairs.append((path, new_meta))
            shifted.add(str(path))
        else:
            new_pairs.append((path, meta))

    return new_pairs, shifted
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_web_sync_preview.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/web/sync_preview.py tests/test_web_sync_preview.py
git commit -m "feat(web): add shift_pairs helper for preview"
```

---

## Task 4: Preview response builder — `build_preview`

Combines `compute_net_deltas`, `shift_pairs`, and `build_timeline` into a single function returning the response shape the endpoint will serialize.

**Files:**
- Modify: `src/photowalk/web/sync_preview.py`
- Test: `tests/test_web_sync_preview.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_web_sync_preview.py`:

```python
from photowalk.web.sync_preview import build_preview


def test_build_preview_empty_stack_returns_unshifted():
    pairs = [_photo("/a.jpg", datetime(2024, 1, 1, 12, 0, 0))]
    result = build_preview(pairs, [], image_duration=3.5)
    assert result["settings"]["image_duration"] == 3.5
    assert len(result["entries"]) == 1
    assert result["files"][0]["shifted"] is False
    assert result["files"][0]["timestamp"] == "2024-01-01T12:00:00"


def test_build_preview_with_offset_marks_shifted_file():
    pairs = [
        _photo("/a.jpg", datetime(2024, 1, 1, 12, 0, 0)),
        _photo("/b.jpg", datetime(2024, 1, 1, 13, 0, 0)),
    ]
    offsets = [_entry(3600.0, ["/a.jpg"])]
    result = build_preview(pairs, offsets, image_duration=3.5)
    files_by_path = {f["path"]: f for f in result["files"]}
    assert files_by_path["/a.jpg"]["shifted"] is True
    assert files_by_path["/a.jpg"]["timestamp"] == "2024-01-01T13:00:00"
    assert files_by_path["/b.jpg"]["shifted"] is False


def test_build_preview_files_sorted_by_path():
    pairs = [
        _photo("/b.jpg", datetime(2024, 1, 1, 13, 0, 0)),
        _photo("/a.jpg", datetime(2024, 1, 1, 12, 0, 0)),
    ]
    result = build_preview(pairs, [], image_duration=3.5)
    paths = [f["path"] for f in result["files"]]
    assert paths == ["/a.jpg", "/b.jpg"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_web_sync_preview.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_preview'`

- [ ] **Step 3: Implement `build_preview`**

Append to `src/photowalk/web/sync_preview.py`:

```python
from photowalk.timeline import build_timeline


def _serialize_entry(entry) -> dict:
    """Mirror the serialization in server.api_timeline."""
    data = {
        "kind": entry.kind,
        "source_path": str(entry.source_path),
        "start_time": entry.start_time.isoformat() if entry.start_time else None,
        "duration_seconds": entry.duration_seconds,
    }
    if entry.kind == "video_segment":
        data["trim_start"] = entry.trim_start
        data["trim_end"] = entry.trim_end
        data["original_video"] = (
            str(entry.original_video) if entry.original_video else None
        )
    return data


def _serialize_file(path: Path, meta, shifted: bool) -> dict:
    """Match _metadata_to_file_entry from server.py, plus a shifted flag."""
    if isinstance(meta, PhotoMetadata):
        return {
            "path": str(path),
            "type": "photo",
            "timestamp": meta.timestamp.isoformat() if meta.timestamp else None,
            "duration_seconds": None,
            "has_timestamp": meta.timestamp is not None,
            "shifted": shifted,
        }
    return {
        "path": str(path),
        "type": "video",
        "timestamp": (
            meta.start_timestamp.isoformat() if meta.start_timestamp else None
        ),
        "duration_seconds": meta.duration_seconds,
        "has_timestamp": meta.start_timestamp is not None,
        "shifted": shifted,
    }


def build_preview(
    pairs: list[MediaInput],
    offsets: list[OffsetEntry],
    *,
    image_duration: float,
) -> dict:
    """Return the response shape for POST /api/timeline/preview."""
    deltas = compute_net_deltas(offsets)
    shifted_pairs, shifted_paths = shift_pairs(pairs, deltas)

    timeline = build_timeline(shifted_pairs)
    entries = [_serialize_entry(e) for e in timeline.all_entries]
    files = [
        _serialize_file(p, m, str(p) in shifted_paths)
        for p, m in sorted(shifted_pairs, key=lambda pm: str(pm[0]))
    ]
    return {
        "entries": entries,
        "settings": {"image_duration": image_duration},
        "files": files,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_web_sync_preview.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/web/sync_preview.py tests/test_web_sync_preview.py
git commit -m "feat(web): add build_preview combining shift and timeline build"
```

---

## Task 5: Apply orchestrator — `apply_offsets`

Computes net deltas, dispatches to writers per path/type, collects per-file results. Writer functions are injected so tests can mock them without touching disk.

**Files:**
- Create: `src/photowalk/web/sync_apply.py`
- Test: `tests/test_web_sync_apply.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_web_sync_apply.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_web_sync_apply.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'photowalk.web.sync_apply'`

- [ ] **Step 3: Write the module**

```python
# src/photowalk/web/sync_apply.py
"""Apply pending offsets by writing new timestamps to disk."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from photowalk.models import PhotoMetadata, VideoMetadata
from photowalk.timeline import MediaInput
from photowalk.web.sync_models import OffsetEntry
from photowalk.web.sync_preview import compute_net_deltas


WriterFn = Callable[[Path, datetime], bool]


def _current_timestamp(meta) -> datetime | None:
    if isinstance(meta, PhotoMetadata):
        return meta.timestamp
    if isinstance(meta, VideoMetadata):
        return meta.start_timestamp
    return None


def apply_offsets(
    pairs: list[MediaInput],
    offsets: list[OffsetEntry],
    *,
    write_photo: WriterFn,
    write_video: WriterFn,
) -> dict:
    """Write shifted timestamps to disk, one path at a time.

    Returns { "applied": [...], "failed": [...] }.  Per-file errors do
    not abort the batch.
    """
    deltas = compute_net_deltas(offsets)
    pairs_by_path = {str(p): (p, m) for p, m in pairs}

    applied: list[dict] = []
    failed: list[dict] = []

    for path_str, delta in deltas.items():
        if path_str not in pairs_by_path:
            failed.append({"path": path_str, "error": "Path not in scan set"})
            continue

        path, meta = pairs_by_path[path_str]
        old_ts = _current_timestamp(meta)
        if old_ts is None:
            continue  # silently skip — UI shouldn't allow selecting these

        new_ts = old_ts + timedelta(seconds=delta)
        writer = write_photo if isinstance(meta, PhotoMetadata) else write_video

        try:
            ok = writer(path, new_ts)
        except Exception as e:
            failed.append({"path": path_str, "error": str(e)})
            continue

        if ok:
            applied.append({
                "path": path_str,
                "old_ts": old_ts.isoformat(),
                "new_ts": new_ts.isoformat(),
            })
        else:
            failed.append({"path": path_str, "error": "Writer returned False"})

    return {"applied": applied, "failed": failed}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_web_sync_apply.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/web/sync_apply.py tests/test_web_sync_apply.py
git commit -m "feat(web): add apply_offsets orchestrator"
```

---

## Task 6: Store metadata pairs on `app.state` for endpoint use

The current `create_app` accepts a pre-built timeline and a pre-serialized `file_list`, but does NOT keep the underlying `(path, meta)` pairs. Preview/apply both need those pairs. This task threads them through.

**Files:**
- Modify: `src/photowalk/web/server.py`
- Test: `tests/test_web_server.py` (existing tests must still pass; add one assertion)

- [ ] **Step 1: Read current server.py**

(Already read in context — `create_app` signature is `(scan_files, timeline, image_duration=3.5, *, file_list=None)`.)

- [ ] **Step 2: Write a failing test**

Append to `tests/test_web_server.py`:

```python
from photowalk.models import PhotoMetadata


def test_app_state_holds_metadata_pairs():
    img = Path("/tmp/photo.jpg")
    meta = PhotoMetadata(source_path=img, timestamp=datetime(2024, 1, 1, 12, 0, 0))
    timeline = TimelineMap()
    app = create_app({img}, timeline, metadata_pairs=[(img, meta)])
    assert app.state.metadata_pairs == [(img, meta)]
    assert app.state.image_duration == 3.5
```

- [ ] **Step 3: Run the new test to verify it fails**

Run: `uv run pytest tests/test_web_server.py::test_app_state_holds_metadata_pairs -v`
Expected: FAIL with `TypeError: create_app() got an unexpected keyword argument 'metadata_pairs'` or similar

- [ ] **Step 4: Modify `create_app` signature**

In `src/photowalk/web/server.py`, change `create_app`:

```python
def create_app(
    scan_files: Set[Path],
    timeline: TimelineMap,
    image_duration: float = 3.5,
    *,
    file_list: "list[dict] | None" = None,
    metadata_pairs: "list[tuple[Path, object]] | None" = None,
) -> FastAPI:
    app = FastAPI()
    app.state.metadata_pairs = metadata_pairs or []
    app.state.image_duration = image_duration
    app.state.scan_files = scan_files

    # ... existing route definitions unchanged ...
```

In `build_app_from_path`, pass `metadata_pairs=pairs` through to `create_app`:

```python
app = create_app(
    scan_files,
    timeline,
    image_duration,
    file_list=prebuilt_file_list,
    metadata_pairs=pairs,
)
```

- [ ] **Step 5: Run all server tests**

Run: `uv run pytest tests/test_web_server.py -v`
Expected: all pass (including the new one)

- [ ] **Step 6: Commit**

```bash
git add src/photowalk/web/server.py tests/test_web_server.py
git commit -m "feat(web): expose metadata_pairs on app.state"
```

---

## Task 7: `POST /api/offset/parse` endpoint

Validates a duration or reference-pair input via existing `offset.py` parsers. Reference pair with zero delta is rejected as a parse error.

**Files:**
- Modify: `src/photowalk/web/server.py`
- Test: `tests/test_web_sync_endpoints.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_web_sync_endpoints.py`:

```python
from fastapi.testclient import TestClient

from photowalk.timeline import TimelineMap
from photowalk.web.server import create_app


def _client():
    return TestClient(create_app(set(), TimelineMap()))


def test_parse_duration_ok():
    r = _client().post(
        "/api/offset/parse",
        json={"kind": "duration", "text": "+2h"},
    )
    assert r.status_code == 200
    assert r.json()["delta_seconds"] == 7200.0


def test_parse_duration_negative():
    r = _client().post(
        "/api/offset/parse",
        json={"kind": "duration", "text": "-30m"},
    )
    assert r.status_code == 200
    assert r.json()["delta_seconds"] == -1800.0


def test_parse_duration_invalid_returns_error():
    r = _client().post(
        "/api/offset/parse",
        json={"kind": "duration", "text": "not-a-duration"},
    )
    assert r.status_code == 200
    assert "error" in r.json()


def test_parse_reference_ok():
    r = _client().post(
        "/api/offset/parse",
        json={
            "kind": "reference",
            "wrong": "2026-04-27T23:28:01+00:00",
            "correct": "2026-04-27T07:05:00+00:00",
        },
    )
    assert r.status_code == 200
    assert r.json()["delta_seconds"] == -58981.0


def test_parse_reference_zero_delta_is_error():
    r = _client().post(
        "/api/offset/parse",
        json={
            "kind": "reference",
            "wrong": "2026-04-27T07:05:00+00:00",
            "correct": "2026-04-27T07:05:00+00:00",
        },
    )
    assert r.status_code == 200
    assert "error" in r.json()


def test_parse_reference_invalid_timestamp_returns_error():
    r = _client().post(
        "/api/offset/parse",
        json={
            "kind": "reference",
            "wrong": "garbage",
            "correct": "2026-04-27T07:05:00",
        },
    )
    assert r.status_code == 200
    assert "error" in r.json()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_web_sync_endpoints.py -v -k parse_`
Expected: 6 tests fail with 404 or 422

- [ ] **Step 3: Add the endpoint**

In `src/photowalk/web/server.py`, add inside `create_app`:

```python
from photowalk.offset import parse_duration, parse_reference, OffsetError
from photowalk.web.sync_models import ParseRequest


@app.post("/api/offset/parse")
async def api_offset_parse(req: ParseRequest):
    src = req.root
    try:
        if src.kind == "duration":
            td = parse_duration(src.text)
        else:
            td = parse_reference(f"{src.wrong}={src.correct}")
    except OffsetError as e:
        return {"error": str(e)}

    delta = td.total_seconds()
    if delta == 0.0:
        return {"error": "Offset is zero — nothing to apply"}
    return {"delta_seconds": delta}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_web_sync_endpoints.py -v -k parse_`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/web/server.py tests/test_web_sync_endpoints.py
git commit -m "feat(web): add POST /api/offset/parse endpoint"
```

---

## Task 8: `POST /api/timeline/preview` endpoint

Accepts the offset stack, returns the recomputed timeline + files list with `shifted` flags. Reads `app.state.metadata_pairs`.

**Files:**
- Modify: `src/photowalk/web/server.py`
- Test: `tests/test_web_sync_endpoints.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_web_sync_endpoints.py`:

```python
from datetime import datetime
from pathlib import Path

from photowalk.models import PhotoMetadata


def _client_with_pairs(pairs):
    timeline = TimelineMap()
    app = create_app(
        {p for p, _ in pairs},
        timeline,
        metadata_pairs=pairs,
    )
    return TestClient(app)


def test_preview_empty_stack_returns_unshifted():
    img = Path("/tmp/a.jpg")
    pairs = [(img, PhotoMetadata(source_path=img, timestamp=datetime(2024, 1, 1, 12, 0, 0)))]
    r = _client_with_pairs(pairs).post("/api/timeline/preview", json={"offsets": []})
    assert r.status_code == 200
    body = r.json()
    assert body["files"][0]["shifted"] is False
    assert body["files"][0]["timestamp"] == "2024-01-01T12:00:00"


def test_preview_with_offset_shifts_file():
    img = Path("/tmp/a.jpg")
    pairs = [(img, PhotoMetadata(source_path=img, timestamp=datetime(2024, 1, 1, 12, 0, 0)))]
    r = _client_with_pairs(pairs).post(
        "/api/timeline/preview",
        json={
            "offsets": [{
                "id": "1",
                "delta_seconds": 3600.0,
                "source": {"kind": "duration", "text": "+1h"},
                "target_paths": ["/tmp/a.jpg"],
            }]
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["files"][0]["shifted"] is True
    assert body["files"][0]["timestamp"] == "2024-01-01T13:00:00"


def test_preview_multi_entry_composes():
    img = Path("/tmp/a.jpg")
    pairs = [(img, PhotoMetadata(source_path=img, timestamp=datetime(2024, 1, 1, 12, 0, 0)))]
    r = _client_with_pairs(pairs).post(
        "/api/timeline/preview",
        json={
            "offsets": [
                {
                    "id": "1",
                    "delta_seconds": 3600.0,
                    "source": {"kind": "duration", "text": "+1h"},
                    "target_paths": ["/tmp/a.jpg"],
                },
                {
                    "id": "2",
                    "delta_seconds": -1800.0,
                    "source": {"kind": "duration", "text": "-30m"},
                    "target_paths": ["/tmp/a.jpg"],
                },
            ]
        },
    )
    assert r.json()["files"][0]["timestamp"] == "2024-01-01T12:30:00"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_web_sync_endpoints.py -v -k preview`
Expected: 3 tests fail with 404

- [ ] **Step 3: Add the endpoint**

In `src/photowalk/web/server.py`, add:

```python
from photowalk.web.sync_models import PreviewRequest
from photowalk.web.sync_preview import build_preview


@app.post("/api/timeline/preview")
async def api_timeline_preview(req: PreviewRequest):
    return build_preview(
        app.state.metadata_pairs,
        req.offsets,
        image_duration=app.state.image_duration,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_web_sync_endpoints.py -v -k preview`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/web/server.py tests/test_web_sync_endpoints.py
git commit -m "feat(web): add POST /api/timeline/preview endpoint"
```

---

## Task 9: `POST /api/sync/apply` endpoint

Calls `apply_offsets`, then re-extracts metadata from disk for every path in the scan set, rebuilds the timeline, updates `app.state`, and returns refreshed state alongside the applied/failed lists.

**Files:**
- Modify: `src/photowalk/web/server.py`
- Test: `tests/test_web_sync_endpoints.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_web_sync_endpoints.py`:

```python
from unittest.mock import patch


def test_apply_calls_writers_and_refreshes_state(monkeypatch):
    img = Path("/tmp/a.jpg")
    initial = PhotoMetadata(source_path=img, timestamp=datetime(2024, 1, 1, 12, 0, 0))
    refreshed = PhotoMetadata(source_path=img, timestamp=datetime(2024, 1, 1, 13, 0, 0))
    pairs = [(img, initial)]

    timeline = TimelineMap()
    app = create_app({img}, timeline, metadata_pairs=pairs)

    photo_calls: list = []

    def fake_write_photo(path, dt):
        photo_calls.append((str(path), dt))
        return True

    def fake_extract(path):
        return refreshed

    monkeypatch.setattr("photowalk.web.server.write_photo_timestamp", fake_write_photo)
    monkeypatch.setattr("photowalk.web.server.write_video_timestamp", lambda p, d: True)
    monkeypatch.setattr("photowalk.web.server.extract_metadata", fake_extract)

    client = TestClient(app)
    r = client.post(
        "/api/sync/apply",
        json={
            "offsets": [{
                "id": "1",
                "delta_seconds": 3600.0,
                "source": {"kind": "duration", "text": "+1h"},
                "target_paths": [str(img)],
            }]
        },
    )

    assert r.status_code == 200
    body = r.json()
    assert photo_calls == [(str(img), datetime(2024, 1, 1, 13, 0, 0))]
    assert len(body["applied"]) == 1
    assert body["applied"][0]["new_ts"] == "2024-01-01T13:00:00"
    assert body["failed"] == []
    # Refreshed state reflects the new timestamp from extract_metadata
    assert body["files"][0]["timestamp"] == "2024-01-01T13:00:00"
    # app.state has been updated
    assert app.state.metadata_pairs[0][1].timestamp == datetime(2024, 1, 1, 13, 0, 0)


def test_apply_partial_failure_returns_both_lists(monkeypatch):
    a = Path("/tmp/a.jpg")
    b = Path("/tmp/b.jpg")
    pairs = [
        (a, PhotoMetadata(source_path=a, timestamp=datetime(2024, 1, 1, 12, 0, 0))),
        (b, PhotoMetadata(source_path=b, timestamp=datetime(2024, 1, 1, 13, 0, 0))),
    ]
    app = create_app({a, b}, TimelineMap(), metadata_pairs=pairs)

    def fake_write_photo(path, dt):
        return str(path) != "/tmp/a.jpg"  # /a.jpg fails

    def fake_extract(path):
        # Pretend disk reflects the attempted change for /b.jpg only
        if str(path) == "/tmp/a.jpg":
            return PhotoMetadata(source_path=a, timestamp=datetime(2024, 1, 1, 12, 0, 0))
        return PhotoMetadata(source_path=b, timestamp=datetime(2024, 1, 1, 14, 0, 0))

    monkeypatch.setattr("photowalk.web.server.write_photo_timestamp", fake_write_photo)
    monkeypatch.setattr("photowalk.web.server.write_video_timestamp", lambda p, d: True)
    monkeypatch.setattr("photowalk.web.server.extract_metadata", fake_extract)

    r = TestClient(app).post(
        "/api/sync/apply",
        json={
            "offsets": [{
                "id": "1",
                "delta_seconds": 3600.0,
                "source": {"kind": "duration", "text": "+1h"},
                "target_paths": ["/tmp/a.jpg", "/tmp/b.jpg"],
            }]
        },
    )

    body = r.json()
    failed_paths = [f["path"] for f in body["failed"]]
    applied_paths = [a_["path"] for a_ in body["applied"]]
    assert failed_paths == ["/tmp/a.jpg"]
    assert applied_paths == ["/tmp/b.jpg"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_web_sync_endpoints.py -v -k apply`
Expected: 2 tests fail with 404

- [ ] **Step 3: Add the endpoint and refresh logic**

In `src/photowalk/web/server.py`, add at module level:

```python
from photowalk.api import extract_metadata
from photowalk.web.sync_apply import apply_offsets
from photowalk.web.sync_models import ApplyRequest
from photowalk.writers import write_photo_timestamp, write_video_timestamp
```

Inside `create_app`, add:

```python
@app.post("/api/sync/apply")
async def api_sync_apply(req: ApplyRequest):
    result = apply_offsets(
        app.state.metadata_pairs,
        req.offsets,
        write_photo=write_photo_timestamp,
        write_video=write_video_timestamp,
    )

    # Re-extract every scanned file from disk; build fresh state.
    refreshed_pairs: list = []
    for path in sorted(app.state.scan_files):
        meta = extract_metadata(path)
        if meta is not None:
            refreshed_pairs.append((path, meta))
    app.state.metadata_pairs = refreshed_pairs

    preview = build_preview(refreshed_pairs, [], image_duration=app.state.image_duration)
    return {
        "applied": result["applied"],
        "failed": result["failed"],
        "files": preview["files"],
        "timeline": {"entries": preview["entries"], "settings": preview["settings"]},
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_web_sync_endpoints.py -v -k apply`
Expected: 2 passed

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest`
Expected: all pass (no regressions)

- [ ] **Step 6: Commit**

```bash
git add src/photowalk/web/server.py tests/test_web_sync_endpoints.py
git commit -m "feat(web): add POST /api/sync/apply endpoint"
```

---

## Task 10: HTML — sync panel + sidebar checkboxes + apply modal

Adds the sync panel above the timeline, checkboxes in each sidebar row, and a hidden modal element for the apply diff.

**Files:**
- Modify: `src/photowalk/web/assets/index.html`

- [ ] **Step 1: Add the sync panel and modal markup**

Replace the body of `index.html` with:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Photo Walk — Timeline Preview</title>
  <link rel="stylesheet" href="/assets/style.css">
</head>
<body>
  <div id="app">
    <div id="preview">
      <video id="preview-video" controls style="display:none;"></video>
      <img id="preview-image" style="display:none;">
      <div id="preview-placeholder">Select an item to preview</div>
    </div>

    <div id="sync-panel">
      <h3>Sync</h3>
      <div class="sync-row">
        <label><input type="radio" name="sync-mode" value="duration" checked> Duration</label>
        <label><input type="radio" name="sync-mode" value="reference"> Reference pair</label>
      </div>
      <div id="sync-duration" class="sync-row">
        <input type="text" id="sync-duration-input" placeholder="-8h23m5s">
      </div>
      <div id="sync-reference" class="sync-row" style="display:none;">
        <input type="text" id="sync-ref-wrong" placeholder="wrong: 2026-04-27T23:28:01+00:00">
        <input type="text" id="sync-ref-correct" placeholder="correct: 2026-04-27T07:05:00">
      </div>
      <div id="sync-error" class="sync-error"></div>
      <div class="sync-row">
        <button id="btn-all-videos" type="button">All videos</button>
        <button id="btn-all-photos" type="button">All photos</button>
        <button id="btn-clear-selection" type="button">Clear</button>
        <span id="sync-selection-count">0 of 0 files selected</span>
      </div>
      <div class="sync-row">
        <button id="btn-add-to-queue" type="button">Add to queue</button>
      </div>
      <div id="sync-queue"></div>
      <div class="sync-row">
        <button id="btn-update-timeline" type="button" disabled>Update timeline</button>
        <button id="btn-apply" type="button" disabled>Apply</button>
      </div>
    </div>

    <div id="bottom">
      <div id="sidebar">
        <h3>Source Files</h3>
        <div id="sidebar-list"></div>
      </div>
      <div id="timeline">
        <h3>Timeline</h3>
        <div id="timeline-scroll">
          <svg id="timeline-svg"></svg>
        </div>
        <div id="timeline-axis"></div>
      </div>
    </div>
  </div>

  <div id="apply-modal" class="modal" style="display:none;">
    <div class="modal-content">
      <h3>Confirm apply</h3>
      <div id="apply-diff"></div>
      <div class="modal-actions">
        <button id="btn-modal-cancel" type="button">Cancel</button>
        <button id="btn-modal-confirm" type="button">Apply to disk</button>
      </div>
    </div>
  </div>

  <div id="toast" class="toast" style="display:none;"></div>

  <script src="/assets/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Manual smoke test**

Run: `uv run photowalk web tests/fixtures/` (or any directory with media)
Expected: page loads with the sync panel visible above the existing layout. Functional behavior comes in later tasks.

- [ ] **Step 3: Commit**

```bash
git add src/photowalk/web/assets/index.html
git commit -m "feat(web): add sync panel and modal markup"
```

---

## Task 11: CSS — sync panel, checkboxes, badge, modal

**Files:**
- Modify: `src/photowalk/web/assets/style.css`

- [ ] **Step 1: Append the new styles**

Append to `style.css`:

```css
/* Sync panel */
#sync-panel {
  background: #16213e;
  border-bottom: 1px solid #333;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
#sync-panel h3 { font-size: 0.9rem; }
.sync-row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.sync-row input[type="text"] {
  background: #0f0f1a;
  border: 1px solid #333;
  color: #e0e0e0;
  padding: 4px 8px;
  font-family: monospace;
  flex: 1;
  min-width: 200px;
}
.sync-row button {
  background: #2a3a5a;
  color: #e0e0e0;
  border: 1px solid #444;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 0.85rem;
}
.sync-row button:hover:not(:disabled) { background: #3a4a6a; }
.sync-row button:disabled { opacity: 0.4; cursor: not-allowed; }
.sync-error { color: #e74c3c; font-size: 0.8rem; min-height: 1em; }
#sync-selection-count { color: #888; font-size: 0.8rem; }
#sync-queue {
  background: #0f0f1a;
  border: 1px solid #333;
  padding: 6px;
  font-size: 0.8rem;
  max-height: 120px;
  overflow-y: auto;
}
#sync-queue:empty::before {
  content: "No pending offsets";
  color: #666;
  font-style: italic;
}
.queue-entry {
  display: flex;
  justify-content: space-between;
  padding: 2px 4px;
}
.queue-entry button {
  background: transparent;
  border: none;
  color: #e74c3c;
  cursor: pointer;
}

/* Sidebar checkbox + shifted badge */
.sidebar-item { display: flex; align-items: flex-start; gap: 8px; }
.sidebar-item input[type="checkbox"] { margin-top: 2px; cursor: pointer; }
.sidebar-item input[type="checkbox"]:disabled { cursor: not-allowed; }
.sidebar-item .filename-block { flex: 1; min-width: 0; }
.shifted-badge {
  display: inline-block;
  background: #d9a04a;
  color: #1a1a2e;
  font-size: 0.65rem;
  padding: 1px 4px;
  border-radius: 3px;
  margin-left: 6px;
}
.sidebar-item.shifted .meta { font-style: italic; }

/* Modal */
.modal {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal-content {
  background: #16213e;
  border: 1px solid #444;
  padding: 20px;
  min-width: 480px;
  max-width: 80vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}
.modal-content h3 { margin-bottom: 12px; }
#apply-diff {
  flex: 1;
  overflow-y: auto;
  font-family: monospace;
  font-size: 0.85rem;
  background: #0f0f1a;
  padding: 8px;
  border: 1px solid #333;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}
.modal-actions button {
  background: #2a3a5a;
  color: #e0e0e0;
  border: 1px solid #444;
  padding: 6px 14px;
  cursor: pointer;
}
#btn-modal-confirm { background: #4a90d9; }

/* Toast */
.toast {
  position: fixed;
  bottom: 20px;
  right: 20px;
  background: #16213e;
  border: 1px solid #444;
  padding: 12px 16px;
  z-index: 101;
  max-width: 400px;
}
.toast.error { border-color: #e74c3c; }
```

- [ ] **Step 2: Manual smoke test**

Run: `uv run photowalk web tests/fixtures/`
Expected: sync panel has visible inputs/buttons; layout doesn't break the timeline below.

- [ ] **Step 3: Commit**

```bash
git add src/photowalk/web/assets/style.css
git commit -m "feat(web): add styles for sync panel, checkboxes, modal"
```

---

## Task 12: JS — selection state and sidebar checkboxes

Refactor `renderSidebar` to include checkboxes; track selection in a `Set` of paths; wire the All-Videos / All-Photos / Clear buttons; update the selection counter; expose helpers used by later tasks.

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Rewrite the IIFE to include selection state**

Replace `app.js` entirely with the version below. (The old code was small enough to be reproduced inline.)

```js
(async function() {
  // ----- State -----
  const selection = new Set();      // checked file paths
  const pendingStack = [];          // offset entries
  let allFiles = [];                // most recent files response
  let lastPreviewFiles = [];        // files from last preview, for diff modal
  let previewIsCurrent = false;     // false if stack changed since last preview

  // ----- Initial load -----
  const [timelineRes, filesRes] = await Promise.all([
    fetch('/api/timeline'),
    fetch('/api/files'),
  ]);
  const timelineData = await timelineRes.json();
  const filesData = await filesRes.json();

  allFiles = filesData.files;
  renderSidebar(allFiles);
  renderTimelineFromData(timelineData);

  bindSyncPanel();
  updateButtons();

  function renderTimelineFromData(td) {
    const entries = td.entries;
    if (entries.length > 0) {
      renderTimeline(entries, td.settings.image_duration);
    } else {
      document.getElementById('timeline-scroll').innerHTML =
        '<div style="padding:20px;color:#666;">No timeline entries.</div>';
    }
  }

  // ----- Sidebar -----
  function renderSidebar(files) {
    const container = document.getElementById('sidebar-list');
    container.innerHTML = '';

    const hasTs = files.filter(f => f.has_timestamp);
    const noTs = files.filter(f => !f.has_timestamp);

    [...hasTs, ...noTs].forEach(f => {
      const el = document.createElement('div');
      el.className = 'sidebar-item' + (f.has_timestamp ? '' : ' warning') + (f.shifted ? ' shifted' : '');
      el.dataset.path = f.path;

      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.disabled = !f.has_timestamp;
      checkbox.checked = selection.has(f.path);
      checkbox.addEventListener('change', () => {
        if (checkbox.checked) selection.add(f.path);
        else selection.delete(f.path);
        updateSelectionCount();
        updateButtons();
      });
      el.appendChild(checkbox);

      const block = document.createElement('div');
      block.className = 'filename-block';

      const icon = f.type === 'video' ? '🎬' : '📷';
      const ts = f.timestamp ? new Date(f.timestamp).toLocaleString() : 'No timestamp';
      const dur = f.duration_seconds ? ` • ${f.duration_seconds.toFixed(1)}s` : '';

      const filenameDiv = document.createElement('div');
      filenameDiv.className = 'filename';
      filenameDiv.textContent = `${icon} ${f.path.split('/').pop()}`;
      if (f.shifted) {
        const badge = document.createElement('span');
        badge.className = 'shifted-badge';
        badge.textContent = 'shifted';
        filenameDiv.appendChild(badge);
      }
      const metaDiv = document.createElement('div');
      metaDiv.className = 'meta';
      metaDiv.textContent = `${ts}${dur}`;

      block.appendChild(filenameDiv);
      block.appendChild(metaDiv);
      block.addEventListener('click', () => selectFile(f.path, f.type, el));
      el.appendChild(block);

      container.appendChild(el);
    });

    updateSelectionCount();
  }

  function updateSelectionCount() {
    const total = allFiles.filter(f => f.has_timestamp).length;
    document.getElementById('sync-selection-count').textContent =
      `${selection.size} of ${total} files selected`;
  }

  // ----- Sync panel wiring -----
  function bindSyncPanel() {
    document.querySelectorAll('input[name="sync-mode"]').forEach(r => {
      r.addEventListener('change', () => {
        const mode = r.value;
        if (!r.checked) return;
        document.getElementById('sync-duration').style.display = mode === 'duration' ? '' : 'none';
        document.getElementById('sync-reference').style.display = mode === 'reference' ? '' : 'none';
        document.getElementById('sync-error').textContent = '';
      });
    });

    document.getElementById('btn-all-videos').addEventListener('click', () => {
      allFiles.filter(f => f.has_timestamp && f.type === 'video').forEach(f => selection.add(f.path));
      renderSidebar(allFiles);
      updateButtons();
    });
    document.getElementById('btn-all-photos').addEventListener('click', () => {
      allFiles.filter(f => f.has_timestamp && f.type === 'photo').forEach(f => selection.add(f.path));
      renderSidebar(allFiles);
      updateButtons();
    });
    document.getElementById('btn-clear-selection').addEventListener('click', () => {
      selection.clear();
      renderSidebar(allFiles);
      updateButtons();
    });
  }

  function updateButtons() {
    document.getElementById('btn-add-to-queue').disabled = selection.size === 0;
    document.getElementById('btn-update-timeline').disabled = pendingStack.length === 0;
    document.getElementById('btn-apply').disabled = pendingStack.length === 0 || !previewIsCurrent;
  }

  // (Stub functions filled in by later tasks)
  function selectFile(path, type, el) {
    document.querySelectorAll('.sidebar-item.selected').forEach(e => e.classList.remove('selected'));
    document.querySelectorAll('.timeline-bar.selected').forEach(e => e.classList.remove('selected'));
    el.classList.add('selected');
    document.querySelectorAll(`.timeline-bar[data-path="${CSS.escape(path)}"]`).forEach(b => b.classList.add('selected'));

    const video = document.getElementById('preview-video');
    const img = document.getElementById('preview-image');
    const placeholder = document.getElementById('preview-placeholder');
    placeholder.style.display = 'none';

    if (type === 'video') {
      let src = '/media/' + path;
      const trimStart = el.dataset.trimStart;
      const trimEnd = el.dataset.trimEnd;
      if (trimStart !== undefined && trimEnd !== undefined) {
        src += '#t=' + parseFloat(trimStart) + ',' + parseFloat(trimEnd);
      }
      video.src = src;
      video.style.display = 'block';
      img.style.display = 'none';
      video.load();
    } else {
      img.src = '/media/' + path;
      img.style.display = 'block';
      video.style.display = 'none';
      video.pause();
      video.src = '';
    }
  }

  function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  function renderTimeline(entries, imageDuration) {
    const svg = document.getElementById('timeline-svg');
    const scroll = document.getElementById('timeline-scroll');
    const barHeight = 40;
    const padding = 20;
    const gap = 4;
    const svgHeight = barHeight + padding * 2;
    const scale = 50;

    const sorted = [...entries].sort((a, b) =>
      new Date(a.start_time) - new Date(b.start_time)
    );

    let currentX = padding;
    const positions = sorted.map(entry => {
      const effectiveDuration = entry.kind === 'image' ? imageDuration : entry.duration_seconds;
      const width = Math.max(2, effectiveDuration * scale);
      const x = currentX;
      currentX += width + gap;
      return { entry, x, width, effectiveDuration };
    });

    const svgWidth = Math.max(scroll.clientWidth, currentX + padding);
    svg.setAttribute('width', svgWidth);
    svg.setAttribute('height', svgHeight);
    svg.innerHTML = '';

    positions.forEach(({ entry, x, width }) => {
      const y = padding;
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', x);
      rect.setAttribute('y', y);
      rect.setAttribute('width', width);
      rect.setAttribute('height', barHeight);
      rect.setAttribute('rx', 3);
      rect.setAttribute('class', `timeline-bar ${entry.kind === 'image' ? 'image' : 'video'}`);
      rect.dataset.path = entry.source_path;
      rect.dataset.kind = entry.kind === 'image' ? 'photo' : 'video';
      if (entry.kind === 'video_segment') {
        rect.dataset.trimStart = entry.trim_start;
        rect.dataset.trimEnd = entry.trim_end;
      }
      rect.addEventListener('click', () => {
        document.querySelectorAll('.sidebar-item.selected').forEach(e => e.classList.remove('selected'));
        document.querySelectorAll('.timeline-bar.selected').forEach(e => e.classList.remove('selected'));
        rect.classList.add('selected');
        document.querySelectorAll(`.sidebar-item[data-path="${CSS.escape(entry.source_path)}"]`).forEach(b => b.classList.add('selected'));
      });
      svg.appendChild(rect);

      if (width > 40) {
        const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        label.setAttribute('x', x + 4);
        label.setAttribute('y', y + barHeight / 2);
        label.setAttribute('class', 'timeline-label');
        let name = entry.source_path.split('/').pop();
        if (entry.kind === 'video_segment' && entry.trim_start != null && entry.trim_end != null) {
          name = `${name} [${formatTime(entry.trim_start)}–${formatTime(entry.trim_end)}]`;
        }
        label.textContent = name.length > 30 ? name.slice(0, 28) + '…' : name;
        svg.appendChild(label);
      }
    });

    renderAxis(positions, scale, padding, gap);
  }

  function renderAxis(positions, scale, padding, gap) {
    const axis = document.getElementById('timeline-axis');
    axis.innerHTML = '';
    if (positions.length === 0) return;

    const totalOutputSeconds = positions.reduce((sum, p) => sum + p.effectiveDuration, 0);
    const containerWidth = axis.clientWidth;
    const tickInterval = totalOutputSeconds > 600 ? 60 : (totalOutputSeconds > 120 ? 30 : 10);
    const numTicks = Math.floor(totalOutputSeconds / tickInterval);

    for (let i = 0; i <= numTicks; i++) {
      const sec = i * tickInterval;
      let accumulated = 0;
      let x = padding;
      for (const p of positions) {
        if (accumulated + p.effectiveDuration >= sec) {
          const intoBlock = sec - accumulated;
          x = p.x + intoBlock * scale;
          break;
        }
        accumulated += p.effectiveDuration;
        x = p.x + p.width + gap;
      }
      if (x > containerWidth) break;

      const tick = document.createElement('div');
      tick.style.position = 'absolute';
      tick.style.left = x + 'px';
      tick.style.top = '0';
      tick.style.fontSize = '11px';
      tick.style.color = '#888';
      tick.style.paddingLeft = '4px';
      tick.style.borderLeft = '1px solid #444';
      tick.style.height = '100%';
      tick.style.whiteSpace = 'nowrap';

      const minutes = Math.floor(sec / 60);
      const seconds = Math.floor(sec % 60);
      tick.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
      axis.appendChild(tick);
    }
  }

  // Stubs filled in by later tasks
  function renderQueue() { /* Task 13 */ }
  async function addToQueue() { /* Task 13 */ }
  async function updateTimeline() { /* Task 14 */ }
  async function openApplyModal() { /* Task 15 */ }

  // Expose nothing globally — each task wires its own button handler.
})();
```

- [ ] **Step 2: Manual smoke test**

Run: `uv run photowalk web tests/fixtures/`
Expected: every sidebar row has a checkbox; "All photos" / "All videos" / "Clear" populate and clear it; the count next to selection updates; greyed (no-timestamp) rows have disabled checkboxes; the existing preview-on-click behavior still works.

- [ ] **Step 3: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat(web): add selection state and sidebar checkboxes"
```

---

## Task 13: JS — "Add to queue" flow

Wire the `Add to queue` button: validate the offset via `/api/offset/parse`, snapshot the current selection into a stack entry, render the queue, mark the preview as stale, refresh button states.

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Implement `addToQueue` and `renderQueue`**

In `app.js`, replace the `renderQueue` and `addToQueue` stubs and add a button handler in `bindSyncPanel`:

```js
function renderQueue() {
  const container = document.getElementById('sync-queue');
  container.innerHTML = '';
  pendingStack.forEach((entry, idx) => {
    const row = document.createElement('div');
    row.className = 'queue-entry';

    const left = document.createElement('span');
    const sign = entry.delta_seconds >= 0 ? '+' : '';
    const label = entry.source.kind === 'duration'
      ? entry.source.text
      : `ref ${sign}${Math.round(entry.delta_seconds)}s`;
    const target = entry.target_paths.length === 1
      ? entry.target_paths[0].split('/').pop()
      : `${entry.target_paths.length} files`;
    left.textContent = `${idx + 1}. ${label} → ${target}`;

    const remove = document.createElement('button');
    remove.textContent = '×';
    remove.addEventListener('click', () => {
      pendingStack.splice(idx, 1);
      previewIsCurrent = false;
      renderQueue();
      updateButtons();
    });

    row.appendChild(left);
    row.appendChild(remove);
    container.appendChild(row);
  });
}

async function addToQueue() {
  const errEl = document.getElementById('sync-error');
  errEl.textContent = '';

  const mode = document.querySelector('input[name="sync-mode"]:checked').value;
  let body;
  if (mode === 'duration') {
    const text = document.getElementById('sync-duration-input').value.trim();
    if (!text) { errEl.textContent = 'Enter a duration'; return; }
    body = { kind: 'duration', text };
  } else {
    const wrong = document.getElementById('sync-ref-wrong').value.trim();
    const correct = document.getElementById('sync-ref-correct').value.trim();
    if (!wrong || !correct) { errEl.textContent = 'Enter both timestamps'; return; }
    body = { kind: 'reference', wrong, correct };
  }

  let parseRes;
  try {
    parseRes = await fetch('/api/offset/parse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(r => r.json());
  } catch (e) {
    errEl.textContent = 'Network error contacting server';
    return;
  }

  if (parseRes.error) { errEl.textContent = parseRes.error; return; }

  pendingStack.push({
    id: crypto.randomUUID(),
    delta_seconds: parseRes.delta_seconds,
    source: body,
    target_paths: [...selection],
  });

  previewIsCurrent = false;
  renderQueue();
  updateButtons();
}
```

In `bindSyncPanel`, append:

```js
document.getElementById('btn-add-to-queue').addEventListener('click', addToQueue);
```

- [ ] **Step 2: Manual smoke test**

Run: `uv run photowalk web tests/fixtures/`
Expected:
1. Type `+1h` in duration mode, click All Photos, click Add to queue → entry appears with `+1h → N files`.
2. Type bogus text → inline red error, queue not mutated.
3. Switch to reference mode, enter two timestamps with the same value → error "Offset is zero".
4. Click × on a queue entry → it disappears.
5. After at least one entry, the "Update timeline" button becomes enabled; "Apply" stays disabled.

- [ ] **Step 3: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat(web): wire add-to-queue flow"
```

---

## Task 14: JS — "Update timeline" preview flow

Wire the `Update timeline` button: POST the stack to `/api/timeline/preview`, replace the timeline render and sidebar files (with shifted markers), set `previewIsCurrent = true`, refresh button states.

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Implement `updateTimeline` and bind the button**

Replace the `updateTimeline` stub:

```js
async function updateTimeline() {
  let res;
  try {
    res = await fetch('/api/timeline/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ offsets: pendingStack }),
    }).then(r => r.json());
  } catch (e) {
    showToast('Could not update timeline', { error: true });
    return;
  }

  allFiles = res.files;
  lastPreviewFiles = res.files;
  renderSidebar(allFiles);
  renderTimelineFromData({ entries: res.entries, settings: res.settings });
  previewIsCurrent = true;
  updateButtons();
}

function showToast(msg, opts = {}) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast' + (opts.error ? ' error' : '');
  t.style.display = '';
  if (!opts.sticky) {
    setTimeout(() => { t.style.display = 'none'; }, 4000);
  }
}
```

In `bindSyncPanel`, append:

```js
document.getElementById('btn-update-timeline').addEventListener('click', updateTimeline);
```

- [ ] **Step 2: Manual smoke test**

Run: `uv run photowalk web tests/fixtures/`
Expected:
1. Queue a `+1h` shift on All Photos.
2. Click Update timeline.
3. Sidebar timestamps for shifted photos render in italic with a "shifted" badge.
4. Timeline re-renders with photos in their new positions.
5. The "Apply" button is now enabled.
6. Removing an entry disables Apply until you click Update timeline again.

- [ ] **Step 3: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat(web): wire update-timeline preview flow"
```

---

## Task 15: JS — Apply diff modal + apply call

Wire the `Apply` button: build the per-file diff from `lastPreviewFiles` against the original `allFiles` snapshot at start, show the modal, on confirm POST `/api/sync/apply`, render results, refresh state, clear stack.

We need access to the **pre-preview** timestamps to show old → new in the diff. Snapshot them when a preview is requested.

**Files:**
- Modify: `src/photowalk/web/assets/app.js`

- [ ] **Step 1: Snapshot original timestamps before preview**

In `app.js`, near the top, add another state variable:

```js
let originalTimestamps = {};   // path -> ISO string at app load (or after apply)
```

After the initial load, populate it:

```js
allFiles.forEach(f => { originalTimestamps[f.path] = f.timestamp; });
```

After a successful apply (in the apply handler below), refresh the snapshot from the new files response.

- [ ] **Step 2: Implement `openApplyModal` and the modal handlers**

Replace the `openApplyModal` stub:

```js
async function openApplyModal() {
  const diffEl = document.getElementById('apply-diff');
  diffEl.innerHTML = '';

  const shiftedFiles = lastPreviewFiles.filter(f => f.shifted);
  if (shiftedFiles.length === 0) {
    showToast('No files would change');
    return;
  }

  shiftedFiles.forEach(f => {
    const row = document.createElement('div');
    const oldTs = originalTimestamps[f.path] || '(none)';
    row.textContent = `${f.path.split('/').pop()}  ${oldTs}  →  ${f.timestamp}`;
    diffEl.appendChild(row);
  });

  const modal = document.getElementById('apply-modal');
  modal.style.display = '';
}

function closeApplyModal() {
  document.getElementById('apply-modal').style.display = 'none';
}

async function confirmApply() {
  let res;
  try {
    res = await fetch('/api/sync/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ offsets: pendingStack }),
    }).then(r => r.json());
  } catch (e) {
    showToast('Apply failed — no changes confirmed', { error: true, sticky: true });
    closeApplyModal();
    return;
  }

  // Refresh state from response
  allFiles = res.files;
  lastPreviewFiles = res.files;
  originalTimestamps = {};
  allFiles.forEach(f => { originalTimestamps[f.path] = f.timestamp; });
  renderSidebar(allFiles);
  renderTimelineFromData(res.timeline);

  // Clear pending state
  pendingStack.length = 0;
  selection.clear();
  previewIsCurrent = false;
  renderQueue();
  renderSidebar(allFiles);
  updateButtons();
  closeApplyModal();

  if (res.failed && res.failed.length > 0) {
    const lines = res.failed.map(f => `${f.path.split('/').pop()}: ${f.error}`).join('\n');
    showToast(
      `Applied ${res.applied.length} of ${res.applied.length + res.failed.length}.\n${lines}`,
      { error: true, sticky: true },
    );
  } else {
    showToast(`Applied ${res.applied.length} files`);
  }
}
```

In `bindSyncPanel`, append:

```js
document.getElementById('btn-apply').addEventListener('click', openApplyModal);
document.getElementById('btn-modal-cancel').addEventListener('click', closeApplyModal);
document.getElementById('btn-modal-confirm').addEventListener('click', confirmApply);
```

- [ ] **Step 3: Manual smoke test (read-only)**

Run: `uv run photowalk web tests/fixtures/`
Expected:
1. Queue a `+0s` (won't be allowed — try `+1s`) shift on a single test photo from `tests/fixtures/`.

   Actually, before clicking confirm, **make a copy of the test photo somewhere safe** — Apply is destructive.

   Or use a throwaway directory:
   ```bash
   mkdir -p /tmp/photowalk-smoke && cp tests/fixtures/<sample>.jpg /tmp/photowalk-smoke/
   uv run photowalk web /tmp/photowalk-smoke
   ```
2. Click Apply → modal shows `<filename>  <old ts>  →  <new ts>`.
3. Cancel → modal closes, state unchanged.
4. Apply again, confirm → modal closes, sidebar refreshes, queue clears, "Applied 1 files" toast appears.
5. Verify on disk: `uv run photowalk info /tmp/photowalk-smoke/<sample>.jpg` shows the shifted timestamp.

- [ ] **Step 4: Commit**

```bash
git add src/photowalk/web/assets/app.js
git commit -m "feat(web): wire apply diff modal and disk-write flow"
```

---

## Task 16: README + AGENTS update

**Files:**
- Modify: `README.md`
- Modify: `agents.md`

- [ ] **Step 1: Document the new feature in README**

In `README.md`, under "Web timeline preview", append a section:

```markdown
#### Sync timestamps from the UI

The web preview includes a Sync panel that shifts photo/video timestamps without leaving the browser:

1. Pick the affected files (checkboxes in the sidebar, or "All videos" / "All photos").
2. Enter an offset — duration string (`-8h23m5s`) or reference pair (`wrong=correct`).
3. Click "Add to queue" — repeat to layer multiple offsets.
4. Click "Update timeline" to preview the resulting timeline. Shifted files are marked with a badge.
5. Click "Apply" to write the new timestamps to disk after a confirmation modal showing each `old → new` change.

Apply is destructive: there is no undo, and the original timestamps are gone after the write.
```

- [ ] **Step 2: Update AGENTS.md if needed**

If `agents.md` lists web endpoints or capabilities, append the three new endpoints (`POST /api/offset/parse`, `POST /api/timeline/preview`, `POST /api/sync/apply`).

- [ ] **Step 3: Run the full test suite once more**

Run: `uv run pytest`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add README.md agents.md
git commit -m "docs: document web UI sync feature"
```

---

## Definition of Done

- [ ] All backend tests pass: `uv run pytest`
- [ ] `tests/test_web_sync_preview.py`, `tests/test_web_sync_apply.py`, `tests/test_web_sync_endpoints.py` exist and contain the tests listed in this plan.
- [ ] Manual smoke checklist from the spec all green:
  - [ ] Sync panel renders; mode toggle works.
  - [ ] Sidebar checkboxes; "All videos" / "All photos" work; greyed rows can't be checked.
  - [ ] Bad offset string → inline error; queue not mutated.
  - [ ] "Add to queue" → entry appears with correct target count.
  - [ ] "Update timeline" → timeline re-renders; shifted files show badge.
  - [ ] Removing a queue entry (×) → next "Update timeline" reflects removal.
  - [ ] "Apply" → diff modal shows old → new per file; cancel does nothing.
  - [ ] Apply confirm → files on disk actually shift (verify via `photowalk info`).
  - [ ] Apply with one un-writable file → partial-failure toast; written files reflect new times; sidebar refreshes.
- [ ] README and AGENTS.md updated.
