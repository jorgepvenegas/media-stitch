// src/types/index.ts

// ─── File Record (matches metadata_to_file_entry in file_entry.py) ───

export interface FileRecord {
  path: string
  type: 'video' | 'photo'
  timestamp: string | null
  duration_seconds: number | null
  has_timestamp: boolean
  shifted: boolean
  // video-only
  end_timestamp?: string | null
  // photo-only (EXIF)
  camera_model?: string | null
  shutter_speed?: string | null
  iso?: number | null
  focal_length?: string | null
  // runtime fields
  trim_start?: number
  trim_end?: number
}

// ─── Timeline Entry (matches session.get_timeline() response) ───

export interface TimelineEntry {
  kind: 'image' | 'video' | 'video_segment'
  source_path: string
  start_time: string | null
  duration_seconds: number
  trim_start?: number
  trim_end?: number
}

// ─── Timeline Settings ───

export interface TimelineSettings {
  image_duration: number
}

// ─── Offset Entry (matches sync_models.py OffsetEntry) ───

export type DurationSource = { kind: 'duration'; text: string }
export type OffsetSource = DurationSource

export interface OffsetEntry {
  id: string
  delta_seconds: number
  source: OffsetSource
  target_paths: string[]
}

// ─── Render Status (matches stitch_models.py StitchStatus) ───

export type RenderState = 'idle' | 'running' | 'done' | 'cancelled' | 'error'

export interface RenderStatus {
  state: RenderState
  message: string
  output_path?: string | null
}

// ─── API Response Types ───

export interface TimelineResponse {
  entries: TimelineEntry[]
  settings: TimelineSettings
  scan_path?: string
}

export interface FilesResponse {
  files: FileRecord[]
}

export interface ParseResponse {
  delta_seconds?: number
  error?: string
}

export interface PreviewResponse {
  entries: TimelineEntry[]
  settings: TimelineSettings
  files: FileRecord[]
}

export interface ApplyResponse {
  applied: { path: string; original_timestamp?: string; new_timestamp: string }[]
  failed: { path: string; error: string }[]
  files: FileRecord[]
  timeline: TimelineResponse
}

export interface StitchRequestBody {
  output: string
  format: string
  draft: boolean
  image_duration: number
  margin: number
  open_folder: boolean
}

// ─── Composable Return Types ───

export interface TimelinePosition {
  entry: TimelineEntry
  x: number
  width: number
  effectiveDuration: number
}

export interface AxisTick {
  seconds: number
  x: number
  label: string
}
