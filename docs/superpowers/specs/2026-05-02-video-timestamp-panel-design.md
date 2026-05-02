# Video Timestamp Preview Panel — Design Spec

## Context

The web UI's sync feature supports "reference pair" mode, where users enter a wrong timestamp and the correct timestamp to calculate an offset. Currently, finding the exact timestamp to enter requires external tools or guesswork. This feature adds a live timestamp display when a video is selected and paused, making it easy to copy the exact timestamp for reference pairing.

## Layout Change

The `#preview` container changes from a single centered video to a flex row:

```
┌────────────────────────────────────────┬──────────────────┐
│                                        │   TIMESTAMP      │
│            Video Player                │     PANEL        │
│         (native controls)              │   (~220px)       │
│                                        │                  │
└────────────────────────────────────────┴──────────────────┘
```

- **Video container**: Takes remaining width after panel (flex: 1)
- **Timestamp panel**: Fixed width (~220px), styled to match app's dark theme

## Components

### Timestamp Panel

| State | Content |
|-------|---------|
| No video selected | "Select a video to see timestamp" (centered, dimmed) |
| Photo selected | "No playback for photos" (centered, dimmed) |
| Video playing | "Playing..." (centered, dimmed) |
| Video paused | Timestamp display + Copy button |

### Timestamp Display (when paused)

```
Current timestamp
─────────────────
Apr 27, 2026, 7:05:00 AM
2026-04-27T07:05:05+00:00

[ Copy ISO ]
```

- **First line**: Human-readable datetime (localized via `toLocaleString`)
- **Second line**: ISO format with timezone offset
- **Button**: Copies ISO string to clipboard

### Copy Button Behavior

1. Click "Copy ISO"
2. ISO timestamp copied to clipboard
3. Button text changes to "Copied!" for 1.5 seconds
4. Returns to "Copy ISO"

## Implementation Details

### Timestamp Calculation

```
actual_timestamp = file.timestamp + (video.currentTime - trim_start)
```

- `file.timestamp`: Video's capture datetime from metadata (stored in `originalFilesByPath`)
- `video.currentTime`: Current position in seconds from video playback
- `trim_start`: Offset from video start (0 if no trim)

The trim offset accounts for the fact that `currentTime` is relative to the trimmed video's start, not the original capture time.

### Event Handling

- `video.addEventListener('pause', ...)` — show timestamp panel with current timestamp
- `video.addEventListener('play', ...)` — show "Playing..." state
- `video.addEventListener('timeupdate', ...)` — (existing) keep within trim bounds

### Panel Visibility Conditions

Show the timestamp panel when:
- A file is selected (`selectedPath !== null`)
- The selected file is a video (`file.type === 'video'`)

Hide/reset when:
- A photo is selected (show "No playback for photos")
- No file is selected (show "Select a video to see timestamp")
- Video starts playing (show "Playing...")

## Styling

| Element | Value |
|---------|-------|
| Panel background | `#16213e` |
| Border-left | `1px solid #333` |
| Timestamp (human) | `font-size: 1rem`, `#e0e0e0` |
| Timestamp (ISO) | `font-size: 0.85rem`, `#888`, monospace |
| Button | `#2a3a5a` bg, white text, matches other buttons |
| Playing/empty states | `#666`, centered, italic |

## Files to Modify

1. `src/photowalk/web/assets/index.html` — add timestamp panel element
2. `src/photowalk/web/assets/style.css` — add panel styles
3. `src/photowalk/web/assets/app.js` — add panel rendering, event listeners, copy logic

## Testing Checklist

- [ ] Select video → panel shows "Select a video to see timestamp" (video not started yet)
- [ ] Play video → panel shows "Playing..."
- [ ] Pause video → panel shows timestamp + copy button
- [ ] Click Copy ISO → clipboard contains ISO string
- [ ] Copy button shows "Copied!" briefly
- [ ] Select photo → panel shows "No playback for photos"
- [ ] Deselect file → panel shows "Select a video to see timestamp"
- [ ] With trim offsets, timestamp is correct (not starting from 0)