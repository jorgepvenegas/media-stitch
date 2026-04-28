# Video Trim Timestamp Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `photowalk fix-trim` CLI command that auto-detects the temporal offset between an original and trimmed video via audio cross-correlation, then writes the corrected creation-time timestamp into the trimmed video.

**Architecture:** A new `offset_detector.py` module extracts audio from both videos (ffmpeg → 16kHz mono WAV), loads the WAV data, and uses `scipy.signal.correlate` to find the lag. The CLI command orchestrates detection, computes the adjusted timestamp from the original's metadata, and writes it via the existing `write_video_timestamp`.

**Tech Stack:** Python 3.10+, click, ffmpeg, scipy/numpy, pytest

---

## Files

| File | Action | Responsibility |
|------|--------|----------------|
| `pyproject.toml` | Modify | Add `scipy` dependency |
| `src/photowalk/offset_detector.py` | Create | Audio extraction, cross-correlation, offset detection |
| `tests/test_offset_detector.py` | Create | Unit tests for all offset_detector functions |
| `src/photowalk/cli.py` | Modify | Add `fix-trim` command |
| `tests/test_cli_fix_trim.py` | Create | CLI tests for dry-run, success, error paths |

---

## Task 1: Add scipy dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add scipy to dependencies**

```toml
# In pyproject.toml [project] dependencies array, add:
"scipy>=1.10.0",
```

- [ ] **Step 2: Sync dependencies**

Run: `uv add scipy`
Expected: `pyproject.toml` updated, `uv.lock` updated (or created).

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: add scipy for audio cross-correlation"
```

---

## Task 2: Implement `extract_audio`

**Files:**
- Create: `src/photowalk/offset_detector.py`
- Test: `tests/test_offset_detector.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_offset_detector.py
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from photowalk.offset_detector import extract_audio, OffsetDetectionError


class TestExtractAudio:
    def test_calls_ffmpeg_correctly(self, tmp_path):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        expected_path = tmp_path / "audio.wav"

        with patch("photowalk.offset_detector.subprocess.run", return_value=mock_result) as mock_run:
            with patch("photowalk.offset_detector.tempfile.NamedTemporaryFile") as mock_ntf:
                mock_file = MagicMock()
                mock_file.name = str(expected_path)
                mock_file.close = MagicMock()
                mock_ntf.return_value = mock_file

                result = extract_audio(Path("/tmp/video.mp4"))

        assert result == expected_path
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        assert "-vn" in cmd
        assert "pcm_s16le" in cmd
        assert "-ar" in cmd
        assert "16000" in cmd
        assert "-ac" in cmd
        assert "1" in cmd
        assert str(expected_path) in cmd

    def test_ffmpeg_failure_raises_and_cleans_up(self, tmp_path):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "audio extract failed"

        expected_path = tmp_path / "audio.wav"

        with patch("photowalk.offset_detector.subprocess.run", return_value=mock_result):
            with patch("photowalk.offset_detector.tempfile.NamedTemporaryFile") as mock_ntf:
                mock_file = MagicMock()
                mock_file.name = str(expected_path)
                mock_file.close = MagicMock()
                mock_ntf.return_value = mock_file

                with pytest.raises(OffsetDetectionError, match="audio extract failed"):
                    extract_audio(Path("/tmp/video.mp4"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_offset_detector.py -v`
Expected: FAIL — `OffsetDetectionError` and `extract_audio` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# src/photowalk/offset_detector.py
"""Detect temporal offset between original and trimmed videos via audio cross-correlation."""

import subprocess
import tempfile
from pathlib import Path


class OffsetDetectionError(Exception):
    """Raised when offset detection fails for any reason."""


def extract_audio(path: Path) -> Path:
    """Extract the first audio track to a temporary 16kHz mono WAV file via ffmpeg.

    Returns the path to the temporary WAV. The caller is responsible for cleanup.
    Raises OffsetDetectionError on ffmpeg failure.
    """
    temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp.close()
    temp_path = Path(temp.name)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(temp_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        temp_path.unlink(missing_ok=True)
        raise OffsetDetectionError(
            f"Failed to extract audio from {path}: {result.stderr}"
        )

    return temp_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_offset_detector.py::TestExtractAudio -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/offset_detector.py tests/test_offset_detector.py
git commit -m "feat: add audio extraction for offset detection"
```

---

## Task 3: Implement `_load_audio`

**Files:**
- Modify: `src/photowalk/offset_detector.py`
- Test: `tests/test_offset_detector.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_offset_detector.py
import wave
import struct

import numpy as np

from photowalk.offset_detector import _load_audio


class TestLoadAudio:
    def test_load_mono_16bit_wav(self, tmp_path):
        wav_path = tmp_path / "test.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            samples = struct.pack("<" + "h" * 3, 100, -200, 300)
            wf.writeframes(samples)

        arr, sr = _load_audio(wav_path)
        assert sr == 16000
        assert len(arr) == 3
        assert arr.dtype == np.float32
        assert arr[0] == 100.0
        assert arr[1] == -200.0
        assert arr[2] == 300.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_offset_detector.py::TestLoadAudio -v`
Expected: FAIL — `_load_audio` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# Add to src/photowalk/offset_detector.py
import wave

import numpy as np


def _load_audio(path: Path) -> tuple[np.ndarray, int]:
    """Load a WAV file as a mono float32 numpy array and return (array, sample_rate)."""
    with wave.open(str(path), "rb") as wf:
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        nframes = wf.getnframes()
        data = wf.readframes(nframes)

        if sampwidth == 2:
            arr = np.frombuffer(data, dtype=np.int16)
        else:
            raise OffsetDetectionError(f"Unsupported sample width: {sampwidth}")

        if nchannels > 1:
            arr = arr.reshape(-1, nchannels).mean(axis=1)

        return arr.astype(np.float32), framerate
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_offset_detector.py::TestLoadAudio -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/offset_detector.py tests/test_offset_detector.py
git commit -m "feat: add WAV loader for offset detection"
```

---

## Task 4: Implement `find_audio_offset`

**Files:**
- Modify: `src/photowalk/offset_detector.py`
- Test: `tests/test_offset_detector.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_offset_detector.py
from photowalk.offset_detector import find_audio_offset


class TestFindAudioOffset:
    def test_detects_known_offset_with_sine_wave(self):
        sample_rate = 16000
        duration = 2
        t = np.linspace(0, duration, duration * sample_rate, endpoint=False)
        original = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        start_sample = int(0.5 * sample_rate)
        trim_duration = 1
        trimmed = original[start_sample : start_sample + trim_duration * sample_rate]

        offset = find_audio_offset(original, trimmed, sample_rate)
        assert abs(offset - 0.5) < 0.01

    def test_low_confidence_raises(self):
        rng = np.random.default_rng(42)
        original = rng.standard_normal(16000).astype(np.float32)
        trimmed = rng.standard_normal(8000).astype(np.float32)

        with pytest.raises(OffsetDetectionError, match="confidence"):
            find_audio_offset(original, trimmed, 16000)

    def test_trimmed_longer_than_original_raises(self):
        original = np.ones(1000, dtype=np.float32)
        trimmed = np.ones(2000, dtype=np.float32)

        with pytest.raises(OffsetDetectionError, match="longer than original"):
            find_audio_offset(original, trimmed, 16000)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_offset_detector.py::TestFindAudioOffset -v`
Expected: FAIL — `find_audio_offset` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# Add to src/photowalk/offset_detector.py
from scipy import signal


def find_audio_offset(original: np.ndarray, trimmed: np.ndarray, sample_rate: int) -> float:
    """Find the temporal offset (in seconds) of trimmed audio within original audio via cross-correlation.

    Raises OffsetDetectionError if the correlation confidence is below 0.5 or if
    trimmed is longer than original.
    """
    if len(trimmed) > len(original):
        raise OffsetDetectionError("Trimmed audio is longer than original")

    original_norm = (original - original.mean()) / (original.std() + 1e-10)
    trimmed_norm = (trimmed - trimmed.mean()) / (trimmed.std() + 1e-10)

    correlation = signal.correlate(original_norm, trimmed_norm, mode="valid", method="fft")
    peak_idx = int(np.argmax(correlation))
    peak_val = float(correlation[peak_idx])

    confidence = peak_val / len(trimmed_norm)
    if confidence < 0.5:
        raise OffsetDetectionError(
            f"Could not reliably detect trim point (confidence: {confidence:.2f}). "
            "Videos may be too different."
        )

    return float(peak_idx / sample_rate)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_offset_detector.py::TestFindAudioOffset -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/offset_detector.py tests/test_offset_detector.py
git commit -m "feat: add audio cross-correlation offset detection"
```

---

## Task 5: Implement `detect_trim_offset`

**Files:**
- Modify: `src/photowalk/offset_detector.py`
- Test: `tests/test_offset_detector.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_offset_detector.py
from unittest.mock import patch

from photowalk.offset_detector import detect_trim_offset


class TestDetectTrimOffset:
    def test_orchestrates_extraction_and_finds_offset(self, tmp_path):
        orig_wav = tmp_path / "orig.wav"
        trim_wav = tmp_path / "trim.wav"
        orig_wav.write_text("dummy")
        trim_wav.write_text("dummy")

        with patch("photowalk.offset_detector.extract_audio", side_effect=[orig_wav, trim_wav]) as mock_extract:
            with patch(
                "photowalk.offset_detector._load_audio",
                side_effect=[
                    (np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32), 16000),
                    (np.array([2.0, 3.0], dtype=np.float32), 16000),
                ],
            ) as mock_load:
                result = detect_trim_offset(Path("orig.mp4"), Path("trim.mp4"))

        assert abs(result - (1 / 16000)) < 0.001
        assert mock_extract.call_count == 2
        mock_load.assert_called()

    def test_cleans_up_temp_files(self, tmp_path):
        orig_wav = tmp_path / "orig.wav"
        trim_wav = tmp_path / "trim.wav"
        orig_wav.write_text("dummy")
        trim_wav.write_text("dummy")

        with patch("photowalk.offset_detector.extract_audio", side_effect=[orig_wav, trim_wav]):
            with patch(
                "photowalk.offset_detector._load_audio",
                side_effect=[
                    (np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32), 16000),
                    (np.array([2.0, 3.0], dtype=np.float32), 16000),
                ],
            ):
                detect_trim_offset(Path("orig.mp4"), Path("trim.mp4"))

        assert not orig_wav.exists()
        assert not trim_wav.exists()

    def test_sample_rate_mismatch_raises(self, tmp_path):
        orig_wav = tmp_path / "orig.wav"
        trim_wav = tmp_path / "trim.wav"
        orig_wav.write_text("dummy")
        trim_wav.write_text("dummy")

        with patch("photowalk.offset_detector.extract_audio", side_effect=[orig_wav, trim_wav]):
            with patch(
                "photowalk.offset_detector._load_audio",
                side_effect=[
                    (np.array([1.0, 2.0], dtype=np.float32), 16000),
                    (np.array([1.0, 2.0], dtype=np.float32), 22050),
                ],
            ):
                with pytest.raises(OffsetDetectionError, match="Sample rate mismatch"):
                    detect_trim_offset(Path("orig.mp4"), Path("trim.mp4"))

        assert not orig_wav.exists()
        assert not trim_wav.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_offset_detector.py::TestDetectTrimOffset -v`
Expected: FAIL — `detect_trim_offset` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# Add to src/photowalk/offset_detector.py

def detect_trim_offset(original_path: Path, trimmed_path: Path) -> float:
    """Detect the temporal offset (in seconds) of a trimmed video relative to its original.

    Extracts audio from both videos, loads the WAV data, and runs cross-correlation.
    Cleans up temporary files regardless of success or failure.
    Raises OffsetDetectionError on any failure.
    """
    original_wav: Path | None = None
    trimmed_wav: Path | None = None

    try:
        original_wav = extract_audio(original_path)
        trimmed_wav = extract_audio(trimmed_path)

        original_audio, original_sr = _load_audio(original_wav)
        trimmed_audio, trimmed_sr = _load_audio(trimmed_wav)

        if original_sr != trimmed_sr:
            raise OffsetDetectionError(
                f"Sample rate mismatch: {original_sr} vs {trimmed_sr}"
            )

        offset = find_audio_offset(original_audio, trimmed_audio, original_sr)

        original_duration = len(original_audio) / original_sr
        if offset > original_duration:
            raise OffsetDetectionError(
                f"Detected offset ({offset:.2f}s) exceeds original duration"
            )

        return offset
    finally:
        if original_wav is not None:
            original_wav.unlink(missing_ok=True)
        if trimmed_wav is not None:
            trimmed_wav.unlink(missing_ok=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_offset_detector.py::TestDetectTrimOffset -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/offset_detector.py tests/test_offset_detector.py
git commit -m "feat: add detect_trim_offset orchestration with cleanup"
```

---

## Task 6: Implement `fix-trim` CLI command

**Files:**
- Modify: `src/photowalk/cli.py`
- Create: `tests/test_cli_fix_trim.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli_fix_trim.py
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from photowalk.cli import main
from photowalk.models import VideoMetadata
from photowalk.offset_detector import OffsetDetectionError


class TestFixTrimDryRun:
    def test_dry_run_shows_computed_timestamps(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("orig.mp4").touch()
            Path("trim.mp4").touch()
            with patch("photowalk.cli.extract_metadata") as mock_meta:
                with patch("photowalk.cli.detect_trim_offset", return_value=5.0):
                    mock_meta.side_effect = [
                        VideoMetadata(
                            source_path=Path("orig.mp4"),
                            start_timestamp=datetime(2024, 7, 15, 14, 0, 0, tzinfo=timezone.utc),
                            duration_seconds=120.0,
                        ),
                        VideoMetadata(
                            source_path=Path("trim.mp4"),
                            start_timestamp=None,
                            duration_seconds=60.0,
                        ),
                    ]
                    result = runner.invoke(main, ["fix-trim", "orig.mp4", "trim.mp4", "--dry-run"])

        assert result.exit_code == 0
        assert "5.000" in result.output
        assert "2024-07-15T14:00:00" in result.output
        assert "2024-07-15T14:00:05" in result.output


class TestFixTrimWrite:
    def test_success_updates_trimmed_in_place(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("orig.mp4").touch()
            Path("trim.mp4").touch()
            with patch("photowalk.cli.extract_metadata") as mock_meta:
                with patch("photowalk.cli.detect_trim_offset", return_value=5.0):
                    with patch("photowalk.cli.write_video_timestamp", return_value=True) as mock_write:
                        mock_meta.side_effect = [
                            VideoMetadata(
                                source_path=Path("orig.mp4"),
                                start_timestamp=datetime(2024, 7, 15, 14, 0, 0, tzinfo=timezone.utc),
                                duration_seconds=120.0,
                            ),
                            VideoMetadata(
                                source_path=Path("trim.mp4"),
                                start_timestamp=None,
                                duration_seconds=60.0,
                            ),
                        ]
                        result = runner.invoke(main, ["fix-trim", "orig.mp4", "trim.mp4"])

        assert result.exit_code == 0
        mock_write.assert_called_once()
        args = mock_write.call_args[0]
        assert args[0] == Path("trim.mp4")
        assert args[1] == datetime(2024, 7, 15, 14, 0, 5, tzinfo=timezone.utc)

    def test_output_option_copies_then_updates(self):
        from unittest.mock import patch as unittest_patch

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("orig.mp4").write_text("original")
            Path("trim.mp4").write_text("trimmed")
            with patch("photowalk.cli.extract_metadata") as mock_meta:
                with patch("photowalk.cli.detect_trim_offset", return_value=5.0):
                    with patch("photowalk.cli.write_video_timestamp", return_value=True) as mock_write:
                        with unittest_patch("photowalk.cli.shutil.copy2") as mock_copy:
                            mock_meta.side_effect = [
                                VideoMetadata(
                                    source_path=Path("orig.mp4"),
                                    start_timestamp=datetime(2024, 7, 15, 14, 0, 0, tzinfo=timezone.utc),
                                    duration_seconds=120.0,
                                ),
                                VideoMetadata(
                                    source_path=Path("trim.mp4"),
                                    start_timestamp=None,
                                    duration_seconds=60.0,
                                ),
                            ]
                            result = runner.invoke(
                                main, ["fix-trim", "orig.mp4", "trim.mp4", "-o", "out.mp4"]
                            )

        assert result.exit_code == 0
        mock_copy.assert_called_once_with(Path("trim.mp4"), Path("out.mp4"))
        mock_write.assert_called_once()
        assert mock_write.call_args[0][0] == Path("out.mp4")

    def test_detection_error_exits_with_message(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("orig.mp4").touch()
            Path("trim.mp4").touch()
            with patch("photowalk.cli.extract_metadata") as mock_meta:
                with patch(
                    "photowalk.cli.detect_trim_offset",
                    side_effect=OffsetDetectionError("no audio track"),
                ):
                    mock_meta.return_value = VideoMetadata(
                        source_path=Path("orig.mp4"),
                        start_timestamp=datetime(2024, 7, 15, 14, 0, 0, tzinfo=timezone.utc),
                        duration_seconds=120.0,
                    )
                    result = runner.invoke(main, ["fix-trim", "orig.mp4", "trim.mp4"])

        assert result.exit_code == 1
        assert "no audio track" in result.output

    def test_non_video_file_rejected(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("orig.jpg").touch()
            Path("trim.mp4").touch()
            result = runner.invoke(main, ["fix-trim", "orig.jpg", "trim.mp4"])

        assert result.exit_code == 1
        assert "must be a video file" in result.output

    def test_missing_original_timestamp_rejected(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("orig.mp4").touch()
            Path("trim.mp4").touch()
            with patch("photowalk.cli.extract_metadata") as mock_meta:
                mock_meta.return_value = VideoMetadata(
                    source_path=Path("orig.mp4"),
                    start_timestamp=None,
                    duration_seconds=120.0,
                )
                result = runner.invoke(main, ["fix-trim", "orig.mp4", "trim.mp4"])

        assert result.exit_code == 1
        assert "start timestamp" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_fix_trim.py -v`
Expected: FAIL — `fix-trim` command not defined, imports may fail.

- [ ] **Step 3: Write minimal implementation**

```python
# Add to src/photowalk/cli.py, after the sync command

@main.command("fix-trim")
@click.argument("original", type=click.Path(exists=True, path_type=Path))
@click.argument("trimmed", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    help="Output path instead of updating in place",
)
@click.option("--dry-run", is_flag=True, help="Preview changes without writing")
def fix_trim(original, trimmed, output, dry_run):
    """Detect trim offset between ORIGINAL and TRIMMED videos, then sync the timestamp."""
    from photowalk.offset_detector import detect_trim_offset, OffsetDetectionError

    for path, label in [(original, "ORIGINAL"), (trimmed, "TRIMMED")]:
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            click.echo(
                click.style(f"Error: {label} must be a video file", fg="red"),
                err=True,
            )
            raise click.Exit(1)

    original_meta = extract_metadata(original)
    if not isinstance(original_meta, VideoMetadata) or original_meta.start_timestamp is None:
        click.echo(
            click.style("Error: Could not read start timestamp from original video", fg="red"),
            err=True,
        )
        raise click.Exit(1)

    try:
        offset_seconds = detect_trim_offset(original, trimmed)
    except OffsetDetectionError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        raise click.Exit(1)

    adjusted_start = original_meta.start_timestamp + timedelta(seconds=offset_seconds)

    trimmed_meta = extract_metadata(trimmed)
    duration = trimmed_meta.duration_seconds if isinstance(trimmed_meta, VideoMetadata) else None
    adjusted_end = adjusted_start + timedelta(seconds=duration) if duration else None

    if dry_run:
        click.echo(f"Detected offset: {offset_seconds:.3f}s")
        click.echo(f"Original start:  {original_meta.start_timestamp.isoformat()}")
        click.echo(f"Adjusted start:  {adjusted_start.isoformat()}")
        if adjusted_end:
            click.echo(f"Adjusted end:    {adjusted_end.isoformat()}")
        return

    target_path = output if output else trimmed
    if output:
        import shutil

        shutil.copy2(trimmed, output)

    ok = write_video_timestamp(target_path, adjusted_start)
    if not ok:
        click.echo(
            click.style(f"Error: Failed to write timestamp to {target_path}", fg="red"),
            err=True,
        )
        raise click.Exit(1)

    click.echo(f"Updated {target_path}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_fix_trim.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/cli.py tests/test_cli_fix_trim.py
git commit -m "feat: add fix-trim CLI command"
```

---

## Task 7: Full test suite verification

**Files:** All modified/created files.

- [ ] **Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass.

- [ ] **Step 2: Run linter/type-checker if available**

Run: `uv run ruff check src/ tests/` (or `uv run pyright` if configured)
Expected: No errors.

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "test: verify full suite passes for fix-trim feature"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- ✅ Audio extraction via ffmpeg → Task 2
- ✅ Cross-correlation with scipy → Task 4
- ✅ Offset detection orchestration → Task 5
- ✅ CLI command with dry-run and -o → Task 6
- ✅ Error handling (no audio, low confidence, mismatched rates) → Tasks 4, 5, 6
- ✅ Temp file cleanup → Task 5
- ✅ Tests for all new code → Tasks 2-6

**2. Placeholder scan:**
- ✅ No TBD, TODO, or vague instructions
- ✅ Every step shows exact code or exact commands
- ✅ Every test has complete assertions

**3. Type consistency:**
- ✅ `OffsetDetectionError` used consistently across all modules
- ✅ `detect_trim_offset` returns `float` (seconds) consistently
- ✅ `find_audio_offset` signature matches usage in `detect_trim_offset`
- ✅ CLI uses `timedelta(seconds=offset_seconds)` consistently
