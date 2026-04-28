# Timestamp Sync Feature — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `sync` command that reads timestamps from photos/videos, applies an offset, and writes corrected timestamps back with dry-run preview and confirmation.

**Architecture:** New `offset.py` parses duration strings and reference timestamps into `timedelta`. New `writers.py` uses `piexif` for photo EXIF and `ffmpeg -c copy` for video metadata. CLI `sync` command orchestrates preview, confirmation, and batch writing.

**Tech Stack:** Python 3.10+, uv, click, piexif, pillow, pytest

---

### Task 1: Add piexif Dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add piexif to dependencies**

Run:
```bash
cd /Users/jorge/code/photo-walk && uv add piexif
```

- [ ] **Step 2: Verify piexif is installed**

Run:
```bash
cd /Users/jorge/code/photo-walk && uv run python -c "import piexif; print(piexif.VERSION)"
```

Expected: Version string printed, no ImportError.

- [ ] **Step 3: Commit**

```bash
cd /Users/jorge/code/photo-walk && git add pyproject.toml uv.lock && git commit -m "chore: add piexif dependency"
```

---

### Task 2: Offset Parser Module

**Files:**
- Create: `src/photowalk/offset.py`
- Test: `tests/test_offset.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_offset.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd /Users/jorge/code/photo-walk && uv run pytest tests/test_offset.py -v
```

Expected: `ModuleNotFoundError: No module named 'photowalk.offset'`

- [ ] **Step 3: Write minimal implementation**

Write `src/photowalk/offset.py`:
```python
"""Parse duration strings and reference timestamps into timedelta offsets."""

import re
from datetime import datetime, timedelta


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd /Users/jorge/code/photo-walk && uv run pytest tests/test_offset.py -v
```

Expected: 16 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/jorge/code/photo-walk && git add tests/test_offset.py src/photowalk/offset.py && git commit -m "feat: add offset parser for duration strings and reference timestamps"
```

---

### Task 3: Writers Module

**Files:**
- Create: `src/photowalk/writers.py`
- Test: `tests/test_writers.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_writers.py`:
```python
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

from photowalk.writers import write_photo_timestamp, write_video_timestamp


class TestWritePhotoTimestamp:
    def test_success(self):
        mock_exif = {"0th": {}, "Exif": {}}

        with patch("photowalk.writers.piexif.load", return_value=mock_exif) as mock_load:
            with patch("photowalk.writers.piexif.dump", return_value=b"exifbytes") as mock_dump:
                with patch("photowalk.writers.piexif.insert") as mock_insert:
                    result = write_photo_timestamp(Path("/tmp/photo.jpg"), datetime(2024, 7, 15, 14, 32, 10))

        assert result is True
        mock_load.assert_called_once_with("/tmp/photo.jpg")
        mock_dump.assert_called_once()
        mock_insert.assert_called_once_with(b"exifbytes", "/tmp/photo.jpg")
        # Verify DateTimeOriginal was set
        assert mock_exif["Exif"][piexif.ExifIFD.DateTimeOriginal] == b"2024:07:15 14:32:10"

    def test_load_failure_returns_false(self):
        with patch("photowalk.writers.piexif.load", side_effect=Exception("bad exif")):
            result = write_photo_timestamp(Path("/tmp/photo.jpg"), datetime(2024, 7, 15, 14, 32, 10))
        assert result is False

    def test_insert_failure_returns_false(self):
        mock_exif = {"0th": {}, "Exif": {}}
        with patch("photowalk.writers.piexif.load", return_value=mock_exif):
            with patch("photowalk.writers.piexif.dump", return_value=b"exifbytes"):
                with patch("photowalk.writers.piexif.insert", side_effect=Exception("write failed")):
                    result = write_photo_timestamp(Path("/tmp/photo.jpg"), datetime(2024, 7, 15, 14, 32, 10))
        assert result is False


class TestWriteVideoTimestamp:
    def test_success(self):
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("photowalk.writers.subprocess.run", return_value=mock_result) as mock_run:
            with patch("photowalk.writers.os.replace") as mock_replace:
                result = write_video_timestamp(Path("/tmp/video.mp4"), datetime(2024, 7, 15, 14, 32, 10, tzinfo=timezone.utc))

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "ffmpeg"
        assert "-y" in call_args
        assert "-i" in call_args
        assert "/tmp/video.mp4" in call_args
        assert "-c" in call_args
        assert "copy" in call_args
        assert "-metadata" in call_args
        assert "creation_time=2024-07-15T14:32:10+00:00" in call_args
        assert "/tmp/video.mp4.tmp" in call_args
        mock_replace.assert_called_once_with("/tmp/video.mp4.tmp", "/tmp/video.mp4")

    def test_ffmpeg_failure_returns_false(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error msg"

        with patch("photowalk.writers.subprocess.run", return_value=mock_result):
            with patch("photowalk.writers.os.path.exists", return_value=True):
                with patch("photowalk.writers.os.remove") as mock_remove:
                    result = write_video_timestamp(Path("/tmp/video.mp4"), datetime(2024, 7, 15, 14, 32, 10))

        assert result is False
        mock_remove.assert_called_once_with("/tmp/video.mp4.tmp")

    def test_ffmpeg_not_found_returns_false(self):
        with patch("photowalk.writers.subprocess.run", side_effect=FileNotFoundError()):
            result = write_video_timestamp(Path("/tmp/video.mp4"), datetime(2024, 7, 15, 14, 32, 10))
        assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd /Users/jorge/code/photo-walk && uv run pytest tests/test_writers.py -v
```

Expected: `ModuleNotFoundError: No module named 'photowalk.writers'`

- [ ] **Step 3: Write minimal implementation**

Write `src/photowalk/writers.py`:
```python
"""Write corrected timestamps back to photo and video files."""

import os
import subprocess
from datetime import datetime
from pathlib import Path

import piexif


def _format_exif_datetime(dt: datetime) -> bytes:
    """Format a datetime as EXIF DateTime string: '2024:07:15 14:32:10'."""
    return dt.strftime("%Y:%m:%d %H:%M:%S").encode("ascii")


def write_photo_timestamp(path: Path, new_timestamp: datetime) -> bool:
    """Write DateTimeOriginal EXIF tag via piexif. Returns True on success."""
    try:
        exif_dict = piexif.load(str(path))
    except Exception:
        return False

    dt_bytes = _format_exif_datetime(new_timestamp)

    # Ensure Exif IFD exists
    if "Exif" not in exif_dict:
        exif_dict["Exif"] = {}

    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = dt_bytes
    exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = dt_bytes

    # Also update IFD0 DateTime as fallback
    if "0th" not in exif_dict:
        exif_dict["0th"] = {}
    exif_dict["0th"][piexif.ImageIFD.DateTime] = dt_bytes

    try:
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, str(path))
        return True
    except Exception:
        return False


def write_video_timestamp(path: Path, new_timestamp: datetime) -> bool:
    """Write creation_time metadata via ffmpeg -c copy. Returns True on success."""
    temp_path = path.with_suffix(path.suffix + ".tmp")
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(path),
        "-c", "copy",
        "-metadata", f'creation_time={new_timestamp.isoformat()}',
        str(temp_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False

    if result.returncode != 0:
        # Clean up temp file if it exists
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False

    # Atomic swap
    os.replace(temp_path, path)
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd /Users/jorge/code/photo-walk && uv run pytest tests/test_writers.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/jorge/code/photo-walk && git add tests/test_writers.py src/photowalk/writers.py && git commit -m "feat: add photo and video timestamp writers"
```

---

### Task 4: CLI Sync Command

**Files:**
- Modify: `src/photowalk/cli.py`
- Test: `tests/test_cli_sync.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_cli_sync.py`:
```python
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from photowalk.cli import main


class TestSyncDryRun:
    def test_sync_dry_run_offset(self):
        mock_photo_exif = {
            "timestamp": "2026:04:27 15:28:01",
            "make": "Canon",
            "model": "EOS R6",
        }

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("photo.jpg").touch()
            with patch("photowalk.photo_extractors.extract_photo_exif", return_value=mock_photo_exif):
                result = runner.invoke(main, ["sync", "photo.jpg", "--offset", "-8h23m5s", "--dry-run"])

        assert result.exit_code == 0
        assert "photo.jpg" in result.output
        assert "2026-04-27T15:28:01" in result.output or "2026-04-27 15:28:01" in result.output
        assert "2026-04-27T07:05:00" in result.output or "2026-04-27 07:05:00" in result.output

    def test_sync_dry_run_reference(self):
        mock_photo_exif = {
            "timestamp": "2026:04:27 15:28:01",
            "make": "Canon",
            "model": "EOS R6",
        }

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("photo.jpg").touch()
            with patch("photowalk.photo_extractors.extract_photo_exif", return_value=mock_photo_exif):
                result = runner.invoke(main, [
                    "sync", "photo.jpg",
                    "--reference", "2026-04-27T23:28:01+00:00=2026-04-27T07:05:00",
                    "--dry-run",
                ])

        assert result.exit_code == 0
        assert "photo.jpg" in result.output

    def test_sync_missing_offset_and_reference(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("photo.jpg").touch()
            result = runner.invoke(main, ["sync", "photo.jpg"])

        assert result.exit_code != 0
        assert "--offset" in result.output or "--reference" in result.output

    def test_sync_both_offset_and_reference(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("photo.jpg").touch()
            result = runner.invoke(main, ["sync", "photo.jpg", "--offset", "+1h", "--reference", "a=b"])

        assert result.exit_code != 0

    def test_sync_no_media_files(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["sync", ".", "--offset", "+1h"])

        assert result.exit_code == 0
        assert "No media files found" in result.output


class TestSyncWrite:
    def test_sync_with_yes_writes_photo(self):
        mock_photo_exif = {
            "timestamp": "2026:04:27 15:28:01",
            "make": "Canon",
            "model": "EOS R6",
        }

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("photo.jpg").touch()
            with patch("photowalk.photo_extractors.extract_photo_exif", return_value=mock_photo_exif):
                with patch("photowalk.cli.write_photo_timestamp", return_value=True) as mock_write:
                    result = runner.invoke(main, ["sync", "photo.jpg", "--offset", "-8h23m5s", "--yes"])

        assert result.exit_code == 0
        mock_write.assert_called_once()

    def test_sync_confirmation_no_cancels(self):
        mock_photo_exif = {
            "timestamp": "2026:04:27 15:28:01",
            "make": "Canon",
            "model": "EOS R6",
        }

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("photo.jpg").touch()
            with patch("photowalk.photo_extractors.extract_photo_exif", return_value=mock_photo_exif):
                with patch("photowalk.cli.write_photo_timestamp") as mock_write:
                    result = runner.invoke(main, ["sync", "photo.jpg", "--offset", "-8h23m5s"], input="n\n")

        assert result.exit_code == 0
        assert "Cancelled" in result.output or "cancelled" in result.output
        mock_write.assert_not_called()

    def test_sync_confirmation_yes_writes(self):
        mock_photo_exif = {
            "timestamp": "2026:04:27 15:28:01",
            "make": "Canon",
            "model": "EOS R6",
        }

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("photo.jpg").touch()
            with patch("photowalk.photo_extractors.extract_photo_exif", return_value=mock_photo_exif):
                with patch("photowalk.cli.write_photo_timestamp", return_value=True) as mock_write:
                    result = runner.invoke(main, ["sync", "photo.jpg", "--offset", "-8h23m5s"], input="y\n")

        assert result.exit_code == 0
        mock_write.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd /Users/jorge/code/photo-walk && uv run pytest tests/test_cli_sync.py -v
```

Expected: `ModuleNotFoundError` or failures because `sync` command doesn't exist.

- [ ] **Step 3: Read current cli.py to know where to insert**

Read `src/photowalk/cli.py` to find the exact location for the new sync command.

- [ ] **Step 4: Write minimal implementation**

Modify `src/photowalk/cli.py` — add imports at top and the sync command at the bottom.

Add these imports at the top of `cli.py`, after existing imports:
```python
from datetime import datetime, timedelta, timezone

from photowalk.offset import compute_offset, OffsetError
from photowalk.writers import write_photo_timestamp, write_video_timestamp
```

Add `_format_timedelta` helper after `_format_csv`:
```python
def _format_timedelta(td: timedelta) -> str:
    """Format a timedelta as a human-readable string like '-8h 23m 5s'."""
    total_seconds = int(td.total_seconds())
    sign = "-" if total_seconds < 0 else "+"
    total_seconds = abs(total_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds:
        parts.append(f"{seconds}s")
    return sign + " ".join(parts) if parts else "0s"
```

Add the `sync` command after the `batch` command (before `if __name__ == "__main__":`):
```python
@main.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--offset", help="Duration offset like '-8h23m5s' or '+2h'")
@click.option("--reference", help="Reference timestamp pair like 'wrong=correct'")
@click.option("--recursive", "-r", is_flag=True)
@click.option("--dry-run", is_flag=True, help="Preview changes without writing")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--include-photos/--no-include-photos", default=True)
@click.option("--include-videos/--no-include-videos", default=True)
def sync(paths, offset, reference, recursive, dry_run, yes, include_photos, include_videos):
    """Adjust timestamps in media files by an offset."""
    try:
        delta = compute_offset(offset, reference)
    except OffsetError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        raise click.Exit(1)

    try:
        files = _collect_files(list(paths), recursive)
    except RuntimeError as e:
        click.echo(click.style(str(e), fg="red"), err=True)
        raise click.Exit(1)

    if not include_photos:
        files = [f for f in files if f.suffix.lower() not in PHOTO_EXTENSIONS]
    if not include_videos:
        files = [f for f in files if f.suffix.lower() not in VIDEO_EXTENSIONS]

    if not files:
        click.echo("No media files found.")
        return

    # Build preview list
    preview = []  # list of (path, current, new, skipped_reason)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)

    for f in files:
        result = extract_metadata(f)
        if result is None:
            preview.append((f, None, None, "Unsupported file type"))
            continue

        if isinstance(result, PhotoMetadata):
            current = result.timestamp
        else:
            current = result.start_timestamp

        if current is None:
            preview.append((f, None, None, "No timestamp found"))
            continue

        new_time = current + delta
        # Check for pre-1970 (EXIF doesn't support it)
        if new_time.tzinfo is None:
            new_time_aware = new_time.replace(tzinfo=timezone.utc)
        else:
            new_time_aware = new_time
        if new_time_aware < epoch:
            preview.append((f, current, None, "Result would be before 1970"))
            continue

        preview.append((f, current, new_time, None))

    # Show preview table
    lines = []
    lines.append(f"{'File':<40} {'Current Timestamp':<30} {'New Timestamp':<30} {'Delta'}")
    lines.append("-" * 120)
    for f, current, new_time, reason in preview:
        name = str(f)[:39]
        if reason:
            lines.append(f"{name:<40} {'N/A':<30} {'N/A':<30} {reason}")
        else:
            cur_str = current.isoformat() if current else "N/A"
            new_str = new_time.isoformat() if new_time else "N/A"
            lines.append(f"{name:<40} {cur_str:<30} {new_str:<30} {_format_timedelta(delta)}")
    click.echo("\n".join(lines))

    if dry_run:
        return

    # Count writable files
    writable = [item for item in preview if item[3] is None]
    if not writable:
        click.echo("No files to update.")
        return

    # Confirmation
    if not yes:
        prompt = f"Apply timestamp offset to {len(writable)} file(s)? [y/N]: "
        response = click.prompt(prompt, default="n", show_default=False)
        if response.lower() not in ("y", "yes"):
            click.echo("Cancelled.")
            return

    # Write
    success_count = 0
    for f, current, new_time, reason in writable:
        ext = f.suffix.lower()
        if ext in PHOTO_EXTENSIONS:
            ok = write_photo_timestamp(f, new_time)
        else:
            ok = write_video_timestamp(f, new_time)

        if ok:
            success_count += 1
        else:
            click.echo(click.style(f"  Failed to update {f}", fg="yellow"))

    skipped_count = len(preview) - len(writable)
    fail_count = len(writable) - success_count
    msg = f"Updated {success_count} of {len(writable)} file(s)."
    if skipped_count:
        msg += f" {skipped_count} skipped."
    if fail_count:
        msg += f" {fail_count} failed."
    click.echo(msg)
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
cd /Users/jorge/code/photo-walk && uv run pytest tests/test_cli_sync.py -v
```

Expected: 8 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/jorge/code/photo-walk && git add tests/test_cli_sync.py src/photowalk/cli.py && git commit -m "feat: add sync CLI command with dry-run and confirmation"
```

---

### Task 5: Final Integration & Verification

**Files:**
- (no new files — verification only)

- [ ] **Step 1: Run full test suite**

Run:
```bash
cd /Users/jorge/code/photo-walk && uv run pytest -v --tb=short
```

Expected: All tests PASS (27 existing + 16 offset + 6 writers + 8 cli_sync = 57 tests)

- [ ] **Step 2: Verify CLI help for sync command**

Run:
```bash
cd /Users/jorge/code/photo-walk && uv run photowalk sync --help
```

Expected: Shows sync command options: `--offset`, `--reference`, `--dry-run`, `--yes`, `--recursive`, `--include-photos`, `--include-videos`.

- [ ] **Step 3: Verify dry-run with a real file (if available)**

If the user has a sample photo/video file, test:
```bash
cd /Users/jorge/code/photo-walk && uv run photowalk sync <path> --offset "-1h" --dry-run
```

Expected: Preview table shows current and new timestamps, no file modification.

- [ ] **Step 4: Update README with sync documentation**

Modify `README.md` — add sync section after batch processing:

```markdown
### Sync timestamps

```bash
# Preview changes with dry-run
photowalk sync ~/Photos/2024/ --offset "-8h23m5s" --recursive --dry-run

# Apply offset with confirmation
photowalk sync ~/Photos/2024/ --offset "-8h23m5s" --recursive

# Use a reference timestamp pair
photowalk sync ~/Photos/2024/ --reference "2026-04-27T23:28:01+00:00=2026-04-27T07:05:00" --recursive

# Skip confirmation prompt
photowalk sync ~/Photos/2024/ --offset "+2h" --recursive --yes
```
```

- [ ] **Step 5: Commit**

```bash
cd /Users/jorge/code/photo-walk && git add README.md && git commit -m "docs: add sync command documentation"
```

- [ ] **Step 6: Final commit**

```bash
cd /Users/jorge/code/photo-walk && git add -A && git commit -m "feat: complete timestamp sync feature" || true
```

---

## Self-Review

### Spec Coverage Check

| Spec Section | Plan Task |
|--------------|-----------|
| piexif dependency | Task 1 |
| Offset parser (duration strings) | Task 2 |
| Offset parser (reference timestamps) | Task 2 |
| Writers (photo via piexif) | Task 3 |
| Writers (video via ffmpeg) | Task 3 |
| CLI sync command | Task 4 |
| Dry-run preview | Task 4 |
| Confirmation prompt | Task 4 |
| Error handling (skip gracefully) | Tasks 3, 4 |
| README update | Task 5 |

**Gap:** None identified.

### Placeholder Scan

- No "TBD", "TODO", or "implement later" found.
- All test code is complete with assertions.
- All implementation code is complete.
- Exact file paths used throughout.

### Type Consistency Check

- `compute_offset(offset: str | None, reference: str | None)` → `timedelta` — consistent in Task 2 and Task 4.
- `write_photo_timestamp(path: Path, new_timestamp: datetime) -> bool` — consistent in Task 3 and Task 4.
- `write_video_timestamp(path: Path, new_timestamp: datetime) -> bool` — consistent in Task 3 and Task 4.
- `_format_timedelta(td: timedelta) -> str` — defined in Task 4, used in preview table.
- `OffsetError` — defined in Task 2, caught in Task 4.

No type inconsistencies found.
