# Video Trim Timestamp Sync — Design Spec

## Overview

A new `photowalk fix-trim` CLI command that automatically detects how much a trimmed video was cut from its original (by comparing audio waveforms via cross-correlation), then computes and writes the correct `start_timestamp` into the trimmed video's metadata.

## Motivation

When a video is trimmed in an external editor, the resulting file loses its original creation time context. The trimmed video's metadata typically reflects export time, not when the remaining frames were actually filmed. Users need a way to restore the correct "filmed at" timestamp without manually calculating offsets.

## CLI Interface

```
photowalk fix-trim ORIGINAL TRIMMED [-o OUTPUT] [--dry-run]
```

**Arguments:**
- `ORIGINAL` — path to the original, untrimmed video
- `TRIMMED` — path to the trimmed video

**Options:**
- `-o, --output PATH` — write result to a new file instead of updating `TRIMMED` in place
- `--dry-run` — detect offset and report computed timestamps without writing

**Exit codes:**
- `0` — success
- `1` — detection failed, missing file, or write error

## Workflow

1. Validate both files exist and are supported video formats
2. Extract audio from both videos as mono 16kHz WAV via ffmpeg
3. Compute cross-correlation between the two audio tracks
4. Detect the lag (seconds into the original where the trimmed audio starts)
5. Read `start_timestamp` from the original video's metadata
6. Compute: `trimmed_start = original_start + lag_seconds`
7. Compute: `trimmed_end = trimmed_start + trimmed_duration`
8. Write new timestamps into the trimmed video (or output file)
9. Clean up temporary WAV files

## Architecture

### New Module: `offset_detector.py`

**`extract_audio(path: Path) -> Path`**
- Uses ffmpeg to extract the first audio track to a temporary mono 16kHz WAV
- Returns the temp file path
- Caller is responsible for cleanup

**`find_audio_offset(original_wav: Path, trimmed_wav: Path) -> float`**
- Loads both WAV files as numpy arrays
- Uses `scipy.signal.correlate(method="fft")` to compute cross-correlation
- Finds the peak correlation index and converts to seconds
- Returns the offset (always non-negative, since trimmed video must be a subset)
- Raises `OffsetDetectionError` if peak correlation is below confidence threshold (0.5)

**`detect_trim_offset(original_path: Path, trimmed_path: Path) -> float`**
- Orchestrates `extract_audio` for both files
- Calls `find_audio_offset`
- Cleans up temp files in a `finally` block
- Returns offset in seconds

### Integration with Existing Code

- `api.extract_metadata()` — reads `VideoMetadata` from both original and trimmed videos
- `writers.write_video_timestamp()` — writes the adjusted timestamp into the output video
- CLI follows existing patterns: `click.Path(exists=True, path_type=Path)`, `click.echo(click.style(...))`, `raise click.Exit(1)`

### Data Flow

```
original.mp4 ──┬──► extract_audio ──► original.wav ──┐
               │                                      ├──► cross-correlate ──► offset_seconds
trimmed.mp4  ──┴──► extract_audio ──► trimmed.wav  ──┘
                                                           │
original.mp4 ──► extract_metadata ──► start_timestamp ─────┼──► adjusted_start
                                                           │
                                                           ▼
                                                   write_video_timestamp(output, adjusted_start)
```

## Error Handling

**OffsetDetectionError** — raised for all detection failures:
- No audio track in either file
- ffmpeg audio extraction failure
- Correlation peak below 0.5 confidence threshold
- Computed offset exceeds original video duration (sanity check)

**CLI behavior:**
- Catch `OffsetDetectionError`, print red error message, exit 1
- Dry-run mode never writes; prints detected offset and computed timestamps

## Edge Cases

| Case | Behavior |
|------|----------|
| Silent video | `OffsetDetectionError`: "cannot detect trim offset: no audio track" |
| Re-encoded with different codec | Audio waveform shape preserved; works correctly |
| Multiple audio tracks | Use first track; document as known limitation |
| Trimmed from both start and end | Start offset detected correctly; end derived from trimmed duration |
| Very long videos (hours) | Downsample to 4kHz if needed; FFT correlation remains fast |
| Trimmed video has different frame rate | Audio timing is independent of frame rate; unaffected |

## Dependencies

- `scipy` — `scipy.signal.correlate` for cross-correlation
- `numpy` — array operations (pulled in by scipy)
- `ffmpeg` — already required by the project

## Testing

**Unit tests (`tests/test_offset_detector.py`):**
- `test_extract_audio_calls_ffmpeg_correctly` — mock subprocess, verify ffmpeg args
- `test_find_audio_offset_with_synthetic_signals` — generate two sine waves with known lag, assert detected offset
- `test_find_audio_offset_low_confidence_raises` — random noise inputs, assert `OffsetDetectionError`
- `test_detect_trim_offset_cleans_up_temps` — mock helpers, verify temp deletion in finally block

**CLI tests (`tests/test_cli_fix_trim.py`):**
- `test_fix_trim_success` — mock `detect_trim_offset` and `write_video_timestamp`, verify output
- `test_fix_trim_dry_run` — verify no write occurs, computed timestamps printed
- `test_fix_trim_no_audio` — mock `detect_trim_offset` to raise, verify error exit
- `test_fix_trim_output_option` — verify `-o` writes to different file

**Integration test:**
- Create two short silent MP4s with ffmpeg, verify `OffsetDetectionError` on no-audio path

## Files Changed

- **New:** `src/photowalk/offset_detector.py`
- **New:** `tests/test_offset_detector.py`
- **New:** `tests/test_cli_fix_trim.py`
- **Modified:** `src/photowalk/cli.py` — add `fix-trim` command
- **Modified:** `pyproject.toml` — add `scipy` dependency
