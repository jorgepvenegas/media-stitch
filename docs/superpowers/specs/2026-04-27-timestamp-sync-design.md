# Timestamp Sync Feature — Design Spec

**Date:** 2026-04-27  
**Status:** Approved

## Overview

Add a `sync` command to photowalk that reads existing timestamps from photos/videos, applies a computed offset (from a duration string or a reference timestamp pair), and writes the corrected timestamps back to the files. Includes dry-run preview and confirmation prompt before destructive writes.

## Goals

- Adjust photo `DateTimeOriginal` and video `creation_time` timestamps by a computed offset
- Support two ways to specify the offset:
  - Duration string: `--offset "-8h23m5s"`
  - Reference timestamp pair: `--reference "wrong=correct"`
- Preview changes with `--dry-run` before writing
- Require confirmation before writing (bypass with `--yes`)
- Skip files gracefully when no timestamp is present or write fails

## Non-Goals

- Modifying any metadata other than timestamps
- Support for files without readable timestamps
- Batch undo / revert functionality
- Writing to file types not supported by piexif (HEIC with piexif limitations)

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│  CLI sync   │────▶│   offset     │────▶│   extract    │────▶│   writers   │
│  command    │     │   parser     │     │   timestamp  │     │ (piexif/    │
│             │     │              │     │              │     │  ffmpeg)    │
└─────────────┘     └──────────────┘     └──────────────┘     └─────────────┘
                                    │
                                    ▼
                              ┌──────────────┐
                              │ confirmation │
                              │   preview    │
                              └──────────────┘
```

### New Components

| Module | Responsibility |
|--------|---------------|
| `offset.py` | Parse `--offset` duration strings and `--reference` timestamp pairs. Compute `timedelta` offsets. |
| `writers.py` | Write corrected timestamps back to files. `write_photo_timestamp()` via piexif, `write_video_timestamp()` via ffmpeg. |

### Modified Components

| Module | Change |
|--------|--------|
| `cli.py` | Add `sync` subcommand with `--offset`, `--reference`, `--dry-run`, `--yes`, `--recursive` flags. |
| `pyproject.toml` | Add `piexif>=1.1.3` dependency. |

## Offset Specification

### Duration String (`--offset`)

Format: `[-][Nh][Nm][Ns]` — at least one component required.

Examples:
- `-8h23m5s` → subtract 8 hours, 23 minutes, 5 seconds
- `+2h` → add 2 hours
- `-30m` → subtract 30 minutes
- `+1h30m` → add 1 hour 30 minutes
- `+45s` → add 45 seconds

Parsing: regex `^([+-]?)(\d+h)?(\d+m)?(\d+s)?$`, extract numeric parts, build `timedelta`.

### Reference Timestamp Pair (`--reference`)

Format: `wrong=correct` — two ISO-8601 timestamps separated by `=`.

Example:
- `--reference "2026-04-27T23:28:01+00:00=2026-04-27T07:05:00"`

Parsing: split on first `=`. Parse both with `datetime.fromisoformat()`. Delta = `correct - wrong`. Applied uniformly to all files.

### Validation

- Exactly one of `--offset` or `--reference` must be provided.
- If both or neither: error exit with usage hint.
- `--dry-run` and `--yes` are independent; both may be used together (dry-run takes precedence).

## Data Flow

```
1. Collect files from args (single file or directory, optional recursive)
2. For each file:
   a. Extract current timestamp (re-use existing extractors)
   b. If no timestamp → skip with warning
   c. Compute new timestamp = current + offset
   d. If new timestamp < 1970 → skip with warning
   e. Store (file, current, new, offset) in preview list
3. Display preview table (all files)
4. If --dry-run → exit 0
5. If not --yes → prompt for confirmation
6. For each file in preview list:
   a. Write new timestamp back
   b. On failure → print warning, continue
7. Print summary: "Updated N of M files"
```

## Writers

### Photo Writer (`write_photo_timestamp`)

```python
def write_photo_timestamp(path: Path, new_timestamp: datetime) -> bool:
    """Write DateTimeOriginal EXIF tag via piexif. Returns True on success."""
```

Steps:
1. Load existing EXIF via `piexif.load(str(path))`
2. Format `new_timestamp` as EXIF DateTime string: `"2024:07:15 14:32:10"`
3. Set `ExifIFD.DateTimeOriginal` (tag 0x9003)
4. Set `IFD0.DateTime` (tag 0x0132) as fallback
5. Dump and insert: `piexif.insert(piexif.dump(exif_dict), str(path))`
6. Return `True` on success, `False` on exception

### Video Writer (`write_video_timestamp`)

```python
def write_video_timestamp(path: Path, new_timestamp: datetime) -> bool:
    """Write creation_time metadata via ffmpeg -c copy. Returns True on success."""
```

Steps:
1. Compute temp file path: `path.with_suffix(path.suffix + ".tmp")`
2. Run ffmpeg:
   ```
   ffmpeg -y -i <path> -c copy -metadata creation_time="<iso8601>" <temp_path>
   ```
3. If returncode == 0: `os.replace(temp_path, path)` (atomic swap)
4. Else: delete temp file if exists, return `False`
5. Return `True` on success

## CLI Design

### Command

```bash
photowalk sync <paths>... [options]
```

### Options

| Flag | Required | Description |
|------|----------|-------------|
| `--offset` | XOR with `--reference` | Duration string: `[-][Nh][Nm][Ns]` |
| `--reference` | XOR with `--offset` | `wrong=correct` timestamp pair |
| `--recursive`, `-r` | no | Scan directories recursively |
| `--dry-run` | no | Preview changes, do not write |
| `--yes`, `-y` | no | Skip confirmation prompt |
| `--include-photos/--no-include-photos` | no | Default: yes |
| `--include-videos/--no-include-videos` | no | Default: yes |

### Preview Table Output

```
File                        Current Timestamp              New Timestamp                  Delta
----------------------------------------------------------------------------------------------------
IMG_0001.jpg                2026-04-27T15:28:01            2026-04-27T07:05:00            -8h 23m 5s
IMG_0002.jpg                2026-04-27T15:30:00            2026-04-27T07:06:59            -8h 23m 5s
video_001.mp4               2026-04-27T15:00:00+00:00      2026-04-27T06:36:55+00:00      -8h 23m 5s
```

### Confirmation Prompt

If not `--dry-run` and not `--yes`:
```
Apply timestamp offset to 42 files? [y/N]:
```
- `y` or `yes` → proceed
- Anything else → cancel, exit 0 with message "Cancelled."

### Summary Output

After writing:
```
Updated 40 of 42 files. 2 skipped (see warnings above).
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| File has no readable timestamp | Skip with warning, continue |
| Offset results in pre-1970 timestamp | Skip with warning, continue |
| piexif fails to load/insert EXIF | Catch exception, skip with warning, continue |
| ffmpeg returns non-zero | Skip with warning, show stderr snippet, continue |
| Neither `--offset` nor `--reference` provided | Error exit with usage |
| Both `--offset` and `--reference` provided | Error exit with usage |
| Invalid duration string | Error exit with parse error message |
| Invalid reference timestamp | Error exit with parse error message |
| No media files found | Print "No media files found." and exit 0 |
| All files skipped | Print "No files to update." and exit 0 |

## Dependencies

```toml
[project]
dependencies = [
    "click>=8.3.3",
    "piexif>=1.1.3",
]
```

`ffmpeg` remains a user-installed external dependency.

## Testing Strategy

1. **Unit — `offset.py`:**
   - Parse valid duration strings: `+2h`, `-30m`, `+1h30m5s`, `-8h23m5s`
   - Parse invalid duration strings: `abc`, `++2h`, empty
   - Parse valid reference: `"2024-07-15T14:00:00=2024-07-15T16:00:00"`
   - Parse invalid reference: missing `=`, unparseable timestamps
   - Compute deltas from reference pairs

2. **Unit — `writers.py` (mocked):**
   - Mock `piexif.load`/`insert` to verify correct tag values written
   - Mock `subprocess.run` to verify correct ffmpeg arguments
   - Test ffmpeg failure handling (temp file cleanup)

3. **Unit — CLI `sync` command:**
   - `--dry-run` shows preview table, no writes
   - `--yes` skips prompt, proceeds to writes
   - Missing `--offset`/`--reference` → error
   - Both provided → error
   - No media files found → exit 0
   - Mock writers to test success/failure counting

4. **Integration (optional):**
   - Create temp JPEG with Pillow, add EXIF timestamp, run sync, read back EXIF

## File Layout Changes

```
photo-walk/
├── src/photowalk/
│   ├── offset.py              # NEW: duration/reference parsing
│   ├── writers.py             # NEW: piexif + ffmpeg writers
│   └── cli.py                 # MODIFIED: add sync command
├── tests/
│   ├── test_offset.py         # NEW
│   └── test_writers.py        # NEW
└── pyproject.toml             # MODIFIED: add piexif
```

## Open Questions / Future Work

- **Timezones:** Offset is applied as a raw timedelta shift. Timezone-aware datetime arithmetic may need careful handling when current and new timestamps cross DST boundaries.
- **Sub-second precision:** EXIF DateTime does not support sub-seconds. piexif also supports `SubSecTimeOriginal` (tag 0x9291) for fractional seconds — consider adding this in a future enhancement.
- **Maker notes:** Some cameras store timestamps in proprietary maker notes. piexif does not edit these. Future: use exiftool if maker notes need updating.
