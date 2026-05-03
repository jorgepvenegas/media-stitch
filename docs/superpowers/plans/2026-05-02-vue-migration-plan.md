# Vue Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the vanilla JS web UI (`assets/`) with a Vue 3 + TypeScript SPA built with Vite and served by the existing FastAPI server.

**Architecture:** Vue 3 Composition API with Pinia for global state, composables for API/timeline/render logic, and Tailwind CSS for styling. Three feature-based panels: PreviewPanel, SyncPanel, TimelinePanel.

**Tech Stack:** Vue 3, TypeScript, Vite, Pinia, Tailwind CSS, Vitest

---

### Task 1: Scaffold vue-app project

**Files:**
- Create: `src/photowalk/web/vue-app/package.json`
- Create: `src/photowalk/web/vue-app/vite.config.ts`
- Create: `src/photowalk/web/vue-app/tsconfig.json`
- Create: `src/photowalk/web/vue-app/tailwind.config.js`
- Create: `src/photowalk/web/vue-app/postcss.config.js`
- Create: `src/photowalk/web/vue-app/index.html`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "photowalk-vue-app",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build",
    "preview": "vite preview",
    "test": "vitest",
    "test:run": "vitest run"
  },
  "dependencies": {
    "vue": "^3.5.0",
    "pinia": "^2.2.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^6.0.0",
    "vue-tsc": "^2.1.0",
    "typescript": "^5.6.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0",
    "vitest": "^2.1.0",
    "@vue/test-utils": "^2.4.0",
    "@vue/tsconfig": "^0.5.0"
  }
}
```

- [ ] **Step 2: Create vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: resolve(__dirname, 'dist'),
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8080',
      '/media': 'http://localhost:8080',
    },
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
})
```

- [ ] **Step 3: Create tsconfig.json**

```json
{
  "extends": "@vue/tsconfig/tsconfig.dom.json",
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.vue", "vite.config.ts"],
  "exclude": ["node_modules", "dist"]
}
```

- [ ] **Step 4: Create tailwind.config.js**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts}',
  ],
  theme: {
    extend: {
      colors: {
        'app-bg': '#1a1a2e',
        'panel': '#16213e',
        'surface': '#0f0f1a',
        'video-bar': '#4a90d9',
        'image-bar': '#5cb85c',
        'accent': '#d9a04a',
        'error': '#e74c3c',
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'monospace'],
      },
    },
  },
  plugins: [],
}
```

- [ ] **Step 5: Create postcss.config.js**

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 6: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Photo Walk — Timeline Preview</title>
</head>
<body class="bg-app-bg text-text overflow-hidden h-screen">
  <div id="app" class="h-screen flex flex-col"></div>
  <script type="module" src="/src/main.ts"></script>
</body>
</html>
```

- [ ] **Step 7: Install dependencies**

Run: `cd src/photowalk/web/vue-app && npm install`
Expected: Dependencies installed successfully

- [ ] **Step 8: Commit**

```bash
git add src/photowalk/web/vue-app/
git commit -m "feat: scaffold Vue 3 + Vite + Tailwind project"
```

---

### Task 2: Create directory structure and CSS base

**Files:**
- Create: `src/photowalk/web/vue-app/src/main.ts`
- Create: `src/photowalk/web/vue-app/src/style.css`
- Create directories: `src/components/`, `src/stores/`, `src/composables/`, `src/types/`

- [ ] **Step 1: Create src/style.css**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
}

@layer components {
  .btn {
    @apply bg-panel text-text border border-[#444] px-2.5 py-1 cursor-pointer text-sm hover:bg-[#3a4a6a] disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-panel rounded;
  }
  .btn-primary {
    @apply bg-video-bar border-video-bar text-white;
  }
  .btn-primary:hover:not(:disabled) {
    @apply bg-blue-600 border-blue-600;
  }
  .input-field {
    @apply bg-surface border border-[#333] text-text px-2 py-1 font-mono flex-1 min-w-[200px] rounded focus:border-blue-400 focus:outline-none;
  }
  .panel-section {
    @apply bg-panel border-b border-[#333];
  }
}
```

- [ ] **Step 2: Create src/main.ts**

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.mount('#app')
```

- [ ] **Step 3: Create src/App.vue (minimal stub)**

```vue
<script setup lang="ts">
// Placeholder — will be replaced in Task 6
</script>

<template>
  <div class="flex flex-col h-screen bg-app-bg text-text">
    <div class="flex items-center justify-center h-screen text-muted">
      Vue app loading...
    </div>
  </div>
</template>
```

- [ ] **Step 4: Create directories**

```bash
mkdir -p src/photowalk/web/vue-app/src/{components,stores,composables,types}
```

- [ ] **Step 5: Commit**

```bash
git add src/photowalk/web/vue-app/src/
git commit -m "feat: add main.ts, styles, and directory structure"
```

---

### Task 3: Define TypeScript types

**Files:**
- Create: `src/photowalk/web/vue-app/src/types/index.ts`
- Test: `src/photowalk/web/vue-app/src/types/__tests__/types.test.ts`

- [ ] **Step 1: Write types**

```typescript
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
export type ReferenceSource = { kind: 'reference'; wrong: string; correct: string }
export type OffsetSource = DurationSource | ReferenceSource

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
```

- [ ] **Step 2: Write a basic type test (compile check)**

```typescript
// src/types/__tests__/types.test.ts
import { describe, it, expectTypeOf } from 'vitest'
import type { FileRecord, TimelineEntry, OffsetEntry, RenderStatus } from '@/types'

describe('types', () => {
  it('FileRecord has required fields', () => {
    const f: FileRecord = {
      path: '/test.jpg',
      type: 'photo',
      timestamp: '2026-01-01T00:00:00',
      duration_seconds: null,
      has_timestamp: true,
      shifted: false,
    }
    expectTypeOf(f.path).toBeString()
    expectTypeOf(f.type).toMatchTypeOf<'photo' | 'video'>()
  })

  it('OffsetEntry with duration source', () => {
    const o: OffsetEntry = {
      id: 'test-id',
      delta_seconds: 3600,
      source: { kind: 'duration', text: '+1h' },
      target_paths: ['/test.mp4'],
    }
    expectTypeOf(o.source.kind).toBe<'duration'>()
  })

  it('TimelineEntry supports video_segment with trim fields', () => {
    const e: TimelineEntry = {
      kind: 'video_segment',
      source_path: '/test.mp4',
      start_time: '2026-01-01T00:00:00',
      duration_seconds: 30,
      trim_start: 5,
      trim_end: 35,
    }
    expectTypeOf(e.trim_start).toBeNumber()
    expectTypeOf(e.trim_end).toBeNumber()
  })
})
```

- [ ] **Step 3: Run test to verify types compile**

Run: `cd src/photowalk/web/vue-app && npm run test:run`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add src/photowalk/web/vue-app/src/types/
git commit -m "feat: define TypeScript types matching backend models"
```

---

### Task 4: Implement composables

**Files:**
- Create: `src/photowalk/web/vue-app/src/composables/useApi.ts`
- Create: `src/photowalk/web/vue-app/src/composables/useTimeline.ts`
- Create: `src/photowalk/web/vue-app/src/composables/useToast.ts`
- Test: `src/photowalk/web/vue-app/src/composables/__tests__/useTimeline.test.ts`
- Test: `src/photowalk/web/vue-app/src/composables/__tests__/useApi.test.ts`

- [ ] **Step 1: Write useApi composable**

```typescript
// src/composables/useApi.ts
import type {
  TimelineResponse,
  FilesResponse,
  ParseResponse,
  PreviewResponse,
  ApplyResponse,
  RenderStatus,
  OffsetEntry,
  OffsetSource,
  StitchRequestBody,
} from '@/types'

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export function useApi() {
  async function fetchTimeline(): Promise<TimelineResponse> {
    return apiFetch<TimelineResponse>('/api/timeline')
  }

  async function fetchFiles(): Promise<FilesResponse> {
    return apiFetch<FilesResponse>('/api/files')
  }

  async function parseOffset(source: OffsetSource): Promise<ParseResponse> {
    return apiFetch<ParseResponse>('/api/offset/parse', {
      method: 'POST',
      body: JSON.stringify(source),
    })
  }

  async function previewTimeline(
    offsets: OffsetEntry[],
    imageDuration?: number,
  ): Promise<PreviewResponse> {
    return apiFetch<PreviewResponse>('/api/timeline/preview', {
      method: 'POST',
      body: JSON.stringify({ offsets, image_duration: imageDuration }),
    })
  }

  async function applySync(offsets: OffsetEntry[]): Promise<ApplyResponse> {
    return apiFetch<ApplyResponse>('/api/sync/apply', {
      method: 'POST',
      body: JSON.stringify({ offsets }),
    })
  }

  async function startRender(body: StitchRequestBody): Promise<RenderStatus> {
    return apiFetch<RenderStatus>('/api/stitch', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  }

  async function pollRenderStatus(): Promise<RenderStatus> {
    return apiFetch<RenderStatus>('/api/stitch/status')
  }

  async function cancelRender(): Promise<void> {
    await fetch('/api/stitch/cancel', { method: 'POST' })
  }

  async function openFolder(path: string): Promise<void> {
    await fetch('/api/open-folder', {
      method: 'POST',
      body: JSON.stringify({ path }),
    })
  }

  return {
    fetchTimeline,
    fetchFiles,
    parseOffset,
    previewTimeline,
    applySync,
    startRender,
    pollRenderStatus,
    cancelRender,
    openFolder,
  }
}
```

- [ ] **Step 2: Write useTimeline composable**

```typescript
// src/composables/useTimeline.ts
import type { TimelineEntry, TimelinePosition, AxisTick } from '@/types'

const GAP = 4
const PADDING = 20
const BAR_HEIGHT = 40

export function useTimeline() {
  function computeLayout(
    entries: TimelineEntry[],
    imageDuration: number,
    scale: number,
  ): TimelinePosition[] {
    const sorted = [...entries].sort(
      (a, b) => new Date(a.start_time ?? 0).getTime() - new Date(b.start_time ?? 0).getTime(),
    )

    let currentX = PADDING
    return sorted.map((entry) => {
      const effectiveDuration =
        entry.kind === 'image' ? imageDuration : entry.duration_seconds
      const width = Math.max(2, effectiveDuration * scale)
      const x = currentX
      currentX += width + GAP
      return { entry, x, width, effectiveDuration }
    })
  }

  function computeSvgWidth(positions: TimelinePosition[], containerWidth: number): number {
    if (positions.length === 0) return containerWidth
    const last = positions[positions.length - 1]
    return Math.max(containerWidth, last.x + last.width + PADDING)
  }

  function formatAxisTicks(
    positions: TimelinePosition[],
    scale: number,
    containerWidth: number,
  ): AxisTick[] {
    if (positions.length === 0) return []

    const totalSeconds = positions.reduce((s, p) => s + p.effectiveDuration, 0)
    const tickInterval =
      totalSeconds > 600 ? 60 : totalSeconds > 120 ? 30 : 10
    const numTicks = Math.floor(totalSeconds / tickInterval)
    const ticks: AxisTick[] = []

    for (let i = 0; i <= numTicks; i++) {
      const sec = i * tickInterval
      let accumulated = 0
      let x = PADDING

      for (const p of positions) {
        if (accumulated + p.effectiveDuration >= sec) {
          const intoBlock = sec - accumulated
          x = p.x + intoBlock * scale
          break
        }
        accumulated += p.effectiveDuration
        x = p.x + p.width + GAP
      }

      if (x > containerWidth) break

      const minutes = Math.floor(sec / 60)
      const seconds = Math.floor(sec % 60)
      ticks.push({
        seconds: sec,
        x,
        label: `${minutes}:${seconds.toString().padStart(2, '0')}`,
      })
    }

    return ticks
  }

  return {
    computeLayout,
    computeSvgWidth,
    formatAxisTicks,
    GAP,
    PADDING,
    BAR_HEIGHT,
  }
}
```

- [ ] **Step 3: Write useToast composable**

```typescript
// src/composables/useToast.ts
import { ref, type Ref } from 'vue'

interface Toast {
  message: string
  isError: boolean
  sticky: boolean
}

const toast: Ref<Toast | null> = ref(null)
let timeout: ReturnType<typeof setTimeout> | null = null

export function useToast() {
  function show(message: string, opts?: { error?: boolean; sticky?: boolean }) {
    if (timeout) clearTimeout(timeout)
    toast.value = {
      message,
      isError: opts?.error ?? false,
      sticky: opts?.sticky ?? false,
    }
    if (!opts?.sticky) {
      timeout = setTimeout(() => {
        toast.value = null
      }, 4000)
    }
  }

  function dismiss() {
    if (timeout) clearTimeout(timeout)
    toast.value = null
  }

  return { toast, show, dismiss }
}
```

- [ ] **Step 4: Write useTimeline tests**

```typescript
// src/composables/__tests__/useTimeline.test.ts
import { describe, it, expect } from 'vitest'
import { useTimeline } from '../useTimeline'
import type { TimelineEntry } from '@/types'

function makeEntry(kind: 'image' | 'video' | 'video_segment', time: string, duration: number): TimelineEntry {
  return {
    kind,
    source_path: `/test.${kind === 'image' ? 'jpg' : 'mp4'}`,
    start_time: time,
    duration_seconds: duration,
  }
}

describe('useTimeline', () => {
  it('computeLayout positions entries sequentially with gap', () => {
    const { computeLayout } = useTimeline()
    const entries: TimelineEntry[] = [
      makeEntry('video', '2026-01-01T00:00:00', 10),
      makeEntry('image', '2026-01-01T00:01:00', 3.5),
    ]
    const scale = 50
    const positions = computeLayout(entries, 3.5, scale)

    expect(positions).toHaveLength(2)
    // First entry starts at PADDING (20)
    expect(positions[0].x).toBe(20)
    expect(positions[0].width).toBe(10 * 50) // 500
    // Second entry after first + GAP
    expect(positions[1].x).toBe(20 + 500 + 4) // 524
    expect(positions[1].width).toBe(3.5 * 50) // 175
  })

  it('computeLayout uses imageDuration for image entries', () => {
    const { computeLayout } = useTimeline()
    const entries: TimelineEntry[] = [
      makeEntry('image', '2026-01-01T00:00:00', 999), // ignored
    ]
    const positions = computeLayout(entries, 5.0, 100)
    expect(positions[0].width).toBe(5.0 * 100) // 500
  })

  it('computeLayout enforces minimum width of 2px', () => {
    const { computeLayout } = useTimeline()
    const entries: TimelineEntry[] = [
      makeEntry('video', '2026-01-01T00:00:00', 0.01),
    ]
    const positions = computeLayout(entries, 3.5, 5)
    expect(positions[0].width).toBeGreaterThanOrEqual(2)
  })

  it('formatAxisTicks produces ticks at correct intervals', () => {
    const { computeLayout, formatAxisTicks } = useTimeline()
    const entries: TimelineEntry[] = [
      makeEntry('video', '2026-01-01T00:00:00', 60), // 1 minute
    ]
    const positions = computeLayout(entries, 3.5, 50)
    const ticks = formatAxisTicks(positions, 50, 2000)

    // Should have ticks at 0, 10, 20, 30, 40, 50, 60 (interval=10 for <120s)
    expect(ticks.length).toBeGreaterThan(0)
    expect(ticks[0].seconds).toBe(0)
    expect(ticks[0].label).toBe('0:00')
  })

  it('formatAxisTicks returns empty for no entries', () => {
    const { formatAxisTicks } = useTimeline()
    expect(formatAxisTicks([], 50, 1000)).toEqual([])
  })
})
```

- [ ] **Step 5: Run tests**

Run: `cd src/photowalk/web/vue-app && npm run test:run`
Expected: All composable tests pass

- [ ] **Step 6: Commit**

```bash
git add src/photowalk/web/vue-app/src/composables/
git commit -m "feat: implement useApi, useTimeline, useToast composables"
```

---

### Task 5: Implement Pinia store

**Files:**
- Create: `src/photowalk/web/vue-app/src/stores/appStore.ts`
- Test: `src/photowalk/web/vue-app/src/stores/__tests__/appStore.test.ts`

- [ ] **Step 1: Write appStore**

```typescript
// src/stores/appStore.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  FileRecord,
  TimelineEntry,
  TimelineSettings,
  OffsetEntry,
  RenderStatus,
  RenderState,
} from '@/types'
import { useApi } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'

function formatSignedSeconds(seconds: number): string {
  const sign = seconds >= 0 ? '+' : '-'
  return `${sign}${Math.abs(seconds)}s`
}

export const useAppStore = defineStore('app', () => {
  // ─── State ───

  const files = ref<FileRecord[]>([])
  const originalFilesByPath = ref<Record<string, FileRecord>>({})
  const selection = ref<Set<string>>(new Set())
  const pendingStack = ref<OffsetEntry[]>([])
  const previewIsCurrent = ref(false)
  const lastPreviewFiles = ref<FileRecord[]>([])
  const timelineEntries = ref<TimelineEntry[]>([])
  const timelineSettings = ref<TimelineSettings>({ image_duration: 3.5 })
  const selectedPath = ref<string | null>(null)
  const selectedSource = ref<'sidebar' | 'timeline' | null>(null)
  const renderStatus = ref<RenderStatus>({ state: 'idle', message: '' })
  const currentVideoFile = ref<FileRecord | null>(null)
  const isPlaying = ref(false)
  const currentTime = ref(0)
  const scanPath = ref<string | null>(null)

  // ─── Computed ───

  const filesWithTimestamp = computed(() =>
    files.value.filter((f) => f.has_timestamp)
  )

  const selectionCount = computed(() => selection.value.size)

  const hasPendingOffsets = computed(() => pendingStack.value.length > 0)

  const shiftedFiles = computed(() =>
    lastPreviewFiles.value.filter((f) => f.shifted)
  )

  const selectedFile = computed(() => {
    if (!selectedPath.value) return null
    return (
      originalFilesByPath.value[selectedPath.value] ||
      files.value.find((f) => f.path === selectedPath.value) ||
      null
    )
  })

  // ─── Actions ───

  function selectFile(path: string, source: 'sidebar' | 'timeline') {
    selectedPath.value = path
    selectedSource.value = source

    const fileSource = previewIsCurrent.value
      ? lastPreviewFiles.value
      : files.value
    currentVideoFile.value =
      fileSource.find((f) => f.path === path) ||
      originalFilesByPath.value[path] ||
      null
  }

  function toggleSelection(path: string, checked: boolean) {
    if (checked) {
      selection.value.add(path)
    } else {
      selection.value.delete(path)
    }
    selection.value = new Set(selection.value) // trigger reactivity
  }

  function selectAll(type: 'video' | 'photo') {
    filesWithTimestamp.value
      .filter((f) => f.type === type)
      .forEach((f) => selection.value.add(f.path))
    selection.value = new Set(selection.value)
  }

  function clearSelection() {
    selection.value.clear()
    selectedPath.value = null
    selectedSource.value = null
    currentVideoFile.value = null
  }

  function addToQueue(entry: OffsetEntry) {
    pendingStack.value.push(entry)
  }

  function removeFromQueue(index: number) {
    pendingStack.value.splice(index, 1)
    previewIsCurrent.value = false
  }

  function clearQueue() {
    pendingStack.value = []
    previewIsCurrent.value = false
  }

  function nudge(path: string, delta: number) {
    const top = pendingStack.value[pendingStack.value.length - 1]
    if (
      top &&
      top.target_paths.length === 1 &&
      top.target_paths[0] === path &&
      top.source.kind === 'duration'
    ) {
      top.delta_seconds += delta
      if (top.delta_seconds === 0) {
        const idx = pendingStack.value.indexOf(top)
        if (idx !== -1) pendingStack.value.splice(idx, 1)
      } else {
        top.source.text = formatSignedSeconds(top.delta_seconds)
      }
    } else {
      pendingStack.value.push({
        id: crypto.randomUUID(),
        delta_seconds: delta,
        source: { kind: 'duration', text: formatSignedSeconds(delta) },
        target_paths: [path],
      })
    }
    previewIsCurrent.value = false
  }

  function setPlaybackState(playing: boolean, time: number) {
    isPlaying.value = playing
    currentTime.value = time
  }

  // ─── Async actions (load, preview, apply, render) ───

  async function loadInitial() {
    const api = useApi()
    const toast = useToast()
    try {
      const [timeline, filesRes] = await Promise.all([
        api.fetchTimeline(),
        api.fetchFiles(),
      ])
      timelineEntries.value = timeline.entries
      timelineSettings.value = timeline.settings
      files.value = filesRes.files
      files.value.forEach((f) => {
        originalFilesByPath.value[f.path] = f
      })
      if (timeline.scan_path) {
        scanPath.value = timeline.scan_path
      }
    } catch (e) {
      toast.show(`Failed to load data: ${e instanceof Error ? e.message : String(e)}`, { error: true, sticky: true })
    }
  }

  async function updateTimeline() {
    const api = useApi()
    const toast = useToast()
    try {
      const res = await api.previewTimeline(
        pendingStack.value,
        timelineSettings.value.image_duration,
      )
      files.value = res.files
      lastPreviewFiles.value = res.files
      timelineEntries.value = res.entries
      timelineSettings.value = res.settings
      previewIsCurrent.value = true
    } catch (e) {
      toast.show(`Could not update timeline: ${e instanceof Error ? e.message : String(e)}`, { error: true })
    }
  }

  async function applySync(): Promise<boolean> {
    const api = useApi()
    const toast = useToast()
    try {
      const res = await api.applySync(pendingStack.value)
      files.value = res.files
      lastPreviewFiles.value = res.files
      res.files.forEach((f) => {
        originalFilesByPath.value[f.path] = f
      })
      pendingStack.value = []
      selection.value.clear()
      previewIsCurrent.value = false
      selectedPath.value = null
      selectedSource.value = null
      currentVideoFile.value = null
      timelineEntries.value = res.timeline.entries
      timelineSettings.value = res.timeline.settings

      if (res.failed && res.failed.length > 0) {
        const lines = res.failed.map((f) => `${f.path.split('/').pop()}: ${f.error}`).join('\n')
        toast.show(
          `Applied ${res.applied.length} of ${res.applied.length + res.failed.length}.\n${lines}`,
          { error: true, sticky: true },
        )
      } else {
        toast.show(`Applied ${res.applied.length} files`)
      }
      return true
    } catch (e) {
      toast.show('Apply failed — no changes confirmed', { error: true, sticky: true })
      return false
    }
  }

  return {
    // State
    files,
    originalFilesByPath,
    selection,
    pendingStack,
    previewIsCurrent,
    lastPreviewFiles,
    timelineEntries,
    timelineSettings,
    selectedPath,
    selectedSource,
    renderStatus,
    currentVideoFile,
    isPlaying,
    currentTime,
    scanPath,
    // Computed
    filesWithTimestamp,
    selectionCount,
    hasPendingOffsets,
    shiftedFiles,
    selectedFile,
    // Actions
    selectFile,
    toggleSelection,
    selectAll,
    clearSelection,
    addToQueue,
    removeFromQueue,
    clearQueue,
    nudge,
    setPlaybackState,
    // Async
    loadInitial,
    updateTimeline,
    applySync,
  }
})
```

- [ ] **Step 2: Write store tests**

```typescript
// src/stores/__tests__/appStore.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAppStore } from '../appStore'
import type { FileRecord } from '@/types'

function makeFile(path: string, type: 'video' | 'photo', ts = true): FileRecord {
  return {
    path,
    type,
    timestamp: ts ? '2026-01-01T00:00:00' : null,
    duration_seconds: type === 'video' ? 30 : null,
    has_timestamp: ts,
    shifted: false,
  }
}

describe('appStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('selectFile sets selectedPath and selectedSource', () => {
    const store = useAppStore()
    store.files.value = [makeFile('/test.mp4', 'video')]
    store.originalFilesByPath.value = { '/test.mp4': makeFile('/test.mp4', 'video') }

    store.selectFile('/test.mp4', 'timeline')
    expect(store.selectedPath).toBe('/test.mp4')
    expect(store.selectedSource).toBe('timeline')
    expect(store.currentVideoFile).not.toBeNull()
  })

  it('toggleSelection adds and removes paths', () => {
    const store = useAppStore()
    store.toggleSelection('/a.mp4', true)
    expect(store.selection.has('/a.mp4')).toBe(true)
    expect(store.selectionCount).toBe(1)

    store.toggleSelection('/a.mp4', false)
    expect(store.selection.has('/a.mp4')).toBe(false)
    expect(store.selectionCount).toBe(0)
  })

  it('selectAll selects all files of given type with timestamps', () => {
    const store = useAppStore()
    store.files.value = [
      makeFile('/v1.mp4', 'video', true),
      makeFile('/v2.mp4', 'video', true),
      makeFile('/p1.jpg', 'photo', false),
    ]
    store.selectAll('video')
    expect(store.selectionCount).toBe(2)
    expect(store.selection.has('/v1.mp4')).toBe(true)
    expect(store.selection.has('/v2.mp4')).toBe(true)
  })

  it('nudge creates or modifies top offset entry', () => {
    const store = useAppStore()
    store.nudge('/test.mp4', 5)
    expect(store.pendingStack).toHaveLength(1)
    expect(store.pendingStack[0].delta_seconds).toBe(5)
    expect(store.pendingStack[0].target_paths).toEqual(['/test.mp4'])

    // Second nudge on same file modifies the same entry
    store.nudge('/test.mp4', 3)
    expect(store.pendingStack).toHaveLength(1)
    expect(store.pendingStack[0].delta_seconds).toBe(8)
  })

  it('nudge cancels entry when delta reaches zero', () => {
    const store = useAppStore()
    store.nudge('/test.mp4', 5)
    store.nudge('/test.mp4', -5)
    expect(store.pendingStack).toHaveLength(0)
  })

  it('clearSelection resets selection state', () => {
    const store = useAppStore()
    store.toggleSelection('/a.mp4', true)
    store.selectedPath.value = '/a.mp4'
    store.clearSelection()
    expect(store.selectionCount).toBe(0)
    expect(store.selectedPath).toBeNull()
    expect(store.selectedSource).toBeNull()
  })
})
```

- [ ] **Step 3: Run tests**

Run: `cd src/photowalk/web/vue-app && npm run test:run`
Expected: All store tests pass

- [ ] **Step 4: Commit**

```bash
git add src/photowalk/web/vue-app/src/stores/
git commit -m "feat: implement Pinia store with all state and actions"
```

---

### Task 6: Build Vue components — PreviewPanel

**Files:**
- Create: `src/photowalk/web/vue-app/src/components/PreviewPanel.vue`
- Test: `src/photowalk/web/vue-app/src/components/__tests__/PreviewPanel.test.ts`

- [ ] **Step 1: Write PreviewPanel.vue**

```vue
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '@/stores/appStore'

const store = useAppStore()
const videoRef = ref<HTMLVideoElement | null>(null)
const imageRef = ref<HTMLImageElement | null>(null)
const copied = ref(false)

const trimStart = computed(() => {
  const f = store.currentVideoFile
  if (!f) return undefined
  return f.trim_start
})
const trimEnd = computed(() => {
  const f = store.currentVideoFile
  if (!f) return undefined
  return f.trim_end
})

const playbackTimestamp = computed(() => {
  if (!store.currentVideoFile || !store.currentVideoFile.timestamp) return null
  const ts = new Date(store.currentVideoFile.timestamp).getTime()
  const offset = (store.currentTime - (trimStart.value ?? 0)) * 1000
  return new Date(ts + offset)
})

const shouldShowVideo = computed(() =>
  store.selectedFile?.type === 'video'
)

const shouldShowImage = computed(() =>
  store.selectedFile?.type === 'photo'
)

const mediaUrl = computed(() => {
  if (!store.selectedFile) return ''
  let url = `/media/${store.selectedFile.path}`
  if (store.selectedFile.type === 'video') {
    const s = trimStart.value
    const e = trimEnd.value
    if (s !== undefined && e !== undefined) {
      url += `#t=${s},${e}`
    }
  }
  return url
})

function handleTimeUpdate() {
  const video = videoRef.value
  if (!video) return
  store.setPlaybackState(true, video.currentTime)

  const e = trimEnd.value
  if (e !== undefined && video.currentTime >= e) {
    video.pause()
    video.currentTime = e
    store.setPlaybackState(false, video.currentTime)
  }
}

function handleSeeking() {
  const video = videoRef.value
  if (!video) return
  const s = trimStart.value
  const e = trimEnd.value
  if (s !== undefined && video.currentTime < s) {
    video.currentTime = s
  }
  if (e !== undefined && video.currentTime > e) {
    video.currentTime = e
  }
}

function handleLoadedMetadata() {
  const video = videoRef.value
  if (!video) return
  const s = trimStart.value
  if (s !== undefined) {
    video.currentTime = s
  }
}

function handlePlay() {
  store.setPlaybackState(true, videoRef.value?.currentTime ?? 0)
}

function handlePause() {
  store.setPlaybackState(false, videoRef.value?.currentTime ?? 0)
}

function handleEnded() {
  store.setPlaybackState(false, videoRef.value?.currentTime ?? 0)
}

function copyTimestamp() {
  if (!playbackTimestamp.value) return
  navigator.clipboard.writeText(playbackTimestamp.value.toISOString())
  copied.value = true
  setTimeout(() => { copied.value = false }, 1500)
}

function useRefAsCorrect() {
  if (!playbackTimestamp.value) return
  // Dispatch a custom event that SyncPanel listens to
  window.dispatchEvent(new CustomEvent('use-ref-timestamp', {
    detail: playbackTimestamp.value.toISOString(),
  }))
}
</script>

<template>
  <div class="flex flex-row h-[40vh] bg-surface border-b border-[#333]">
    <!-- Media display -->
    <div class="flex-1 flex items-center justify-center overflow-hidden">
      <video
        v-if="shouldShowVideo"
        ref="videoRef"
        :src="mediaUrl"
        controls
        class="max-w-full max-h-full object-contain"
        @timeupdate="handleTimeUpdate"
        @seeking="handleSeeking"
        @loadedmetadata="handleLoadedMetadata"
        @play="handlePlay"
        @pause="handlePause"
        @ended="handleEnded"
      />
      <img
        v-else-if="shouldShowImage"
        ref="imageRef"
        :src="mediaUrl"
        class="max-w-full max-h-full object-contain"
      />
      <div v-else class="text-muted text-xl">
        Select an item to preview
      </div>
    </div>

    <!-- Timestamp panel -->
    <div class="w-[220px] min-w-[220px] bg-panel border-l border-[#333] flex flex-col items-center justify-center p-4">
      <div class="text-center w-full">
        <div
          v-if="!selectedPath || store.currentVideoFile?.type !== 'video' || store.isPlaying"
          class="text-muted italic text-sm"
        >
          {{ store.isPlaying ? 'Playing...' : 'Select a video to see timestamp' }}
        </div>
        <div v-else>
          <div class="text-[0.7rem] uppercase tracking-wide text-muted mb-1">
            Current timestamp
          </div>
          <hr class="border-[#333] my-2">
          <div class="text-base text-text mb-1">
            {{ playbackTimestamp?.toISOString() ?? '' }}
          </div>
          <div class="text-sm text-muted font-mono mb-3">
            {{ playbackTimestamp?.toISOString() ?? '' }}
          </div>
          <button
            class="w-full btn mb-2"
            @click="copyTimestamp"
          >
            {{ copied ? 'Copied!' : 'Copy ISO' }}
          </button>
          <button class="w-full btn btn-primary" @click="useRefAsCorrect">
            Use as correct
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Write component test**

```typescript
// src/components/__tests__/PreviewPanel.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PreviewPanel from '../PreviewPanel.vue'
import { useAppStore } from '@/stores/appStore'
import type { FileRecord } from '@/types'

function makeFile(path: string, type: 'video' | 'photo', ts = true): FileRecord {
  return {
    path,
    type,
    timestamp: ts ? '2026-01-01T00:00:00' : null,
    duration_seconds: type === 'video' ? 30 : null,
    has_timestamp: ts,
    shifted: false,
  }
}

describe('PreviewPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows placeholder when no file selected', () => {
    const wrapper = mount(PreviewPanel)
    expect(wrapper.text()).toContain('Select an item to preview')
  })

  it('shows "Select a video" for photo selection', () => {
    const store = useAppStore()
    store.selectFile('/test.jpg', 'sidebar')
    store.currentVideoFile = makeFile('/test.jpg', 'photo')

    const wrapper = mount(PreviewPanel)
    expect(wrapper.text()).toContain('Select a video to see timestamp')
  })
})
```

- [ ] **Step 3: Run tests**

Run: `cd src/photowalk/web/vue-app && npm run test:run`
Expected: Tests pass

- [ ] **Step 4: Commit**

```bash
git add src/photowalk/web/vue-app/src/components/PreviewPanel.vue src/photowalk/web/vue-app/src/components/__tests__/
git commit -m "feat: add PreviewPanel component with video playback and timestamp panel"
```

---

### Task 7: Build Vue components — SyncPanel

**Files:**
- Create: `src/photowalk/web/vue-app/src/components/SyncPanel.vue`
- Test: `src/photowalk/web/vue-app/src/components/__tests__/SyncPanel.test.ts`

- [ ] **Step 1: Write SyncPanel.vue**

```vue
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useApi } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import type { OffsetSource, DurationSource, ReferenceSource } from '@/types'

const store = useAppStore()
const api = useApi()
const toast = useToast()

const syncMode = ref<'duration' | 'reference'>('duration')
const durationInput = ref('')
const refWrong = ref('')
const refCorrect = ref('')
const parseError = ref('')

// Modal state
const showApplyModal = ref(false)
const showRenderModal = ref(false)
const renderFormVisible = ref(true)

// Render form
const renderOutput = ref('')
const renderFormat = ref('1920x1080')
const renderDraft = ref(false)
const renderImageDuration = ref(3.5)
const renderMargin = ref(15)
const renderOpenFolder = ref(false)

// Watch for external "use as correct" events from PreviewPanel
function handleUseRefEvent(e: Event) {
  const detail = (e as CustomEvent).detail as string
  syncMode.value = 'reference'
  refCorrect.value = detail
}
watch(() => true, () => {
  window.addEventListener('use-ref-timestamp', handleUseRefEvent)
}, { immediate: true })

// Populate refWrong when selected file changes
watch(() => store.selectedPath, (path) => {
  if (path) {
    const file = store.originalFilesByPath[path]
    if (file?.timestamp) {
      refWrong.value = file.timestamp
    }
  }
})

const canAddToQueue = computed(() => {
  if (syncMode.value === 'duration') return durationInput.value.trim().length > 0
  return refWrong.value.trim().length > 0 && refCorrect.value.trim().length > 0
})

const canUpdateTimeline = computed(() => store.hasPendingOffsets)
const canApply = computed(() =>
  store.hasPendingOffsets && store.previewIsCurrent
)

function getSource(): OffsetSource | null {
  parseError.value = ''
  if (syncMode.value === 'duration') {
    const text = durationInput.value.trim()
    if (!text) { parseError.value = 'Enter a duration'; return null }
    return { kind: 'duration', text }
  }
  const wrong = refWrong.value.trim()
  const correct = refCorrect.value.trim()
  if (!wrong || !correct) { parseError.value = 'Enter both timestamps'; return null }
  return { kind: 'reference', wrong, correct }
}

async function addToQueue() {
  const source = getSource()
  if (!source) return

  try {
    const res = await api.parseOffset(source)
    if (res.error) { parseError.value = res.error; return }
    store.addToQueue({
      id: crypto.randomUUID(),
      delta_seconds: res.delta_seconds!,
      source,
      target_paths: [...store.selection],
    })
  } catch (e) {
    toast.show('Network error contacting server', { error: true })
  }
}

function removeQueueItem(index: number) {
  store.removeFromQueue(index)
}

function clearQueue() {
  store.clearQueue()
  store.updateTimeline()
}

async function updateTimeline() {
  await store.updateTimeline()
}

function openApplyModal() {
  if (store.shiftedFiles.length === 0) {
    toast.show('No files would change')
    return
  }
  showApplyModal.value = true
}

async function confirmApply() {
  const success = await store.applySync()
  if (success) showApplyModal.value = false
}

function cancelApply() {
  showApplyModal.value = false
}

function openRenderModal() {
  renderOutput.value = store.scanPath
    ? store.scanPath.replace(/\/$/, '') + '/photowalk_output.mp4'
    : ''
  renderFormat.value = '1920x1080'
  renderDraft.value = false
  renderImageDuration.value = store.timelineSettings.image_duration
  renderMargin.value = 15
  renderOpenFolder.value = false
  renderFormVisible.value = true
  showRenderModal.value = true
}

function closeRenderModal() {
  showRenderModal.value = false
  renderFormVisible.value = true
}

async function startRender() {
  if (!renderOutput.value.trim()) {
    toast.show('Output path is required', { error: true })
    return
  }

  try {
    const res = await api.startRender({
      output: renderOutput.value,
      format: renderFormat.value,
      draft: renderDraft.value,
      image_duration: renderImageDuration.value,
      margin: renderMargin.value,
      open_folder: renderOpenFolder.value,
    })
    renderFormVisible.value = false

    // Poll status
    const interval = setInterval(async () => {
      try {
        const status = await api.pollRenderStatus()
        if (status.state === 'done') {
          clearInterval(interval)
          if (renderOpenFolder.value && status.output_path) {
            const dir = status.output_path.split('/').slice(0, -1).join('/') || '.'
            api.openFolder(dir).catch(() => {})
          }
          toast.show('Render complete')
          closeRenderModal()
        } else if (status.state === 'cancelled') {
          clearInterval(interval)
          toast.show('Render cancelled')
          closeRenderModal()
        } else if (status.state === 'error') {
          clearInterval(interval)
          toast.show(status.message || 'Render failed', { error: true, sticky: true })
          closeRenderModal()
        }
        store.renderStatus = status
      } catch { /* ignore poll errors */ }
    }, 1000)
  } catch (e: any) {
    if (e.message.includes('409')) {
      toast.show('A render is already in progress', { error: true })
    } else {
      toast.show(e.message || 'Failed to start render', { error: true })
    }
  }
}

async function cancelRender() {
  try {
    await api.cancelRender()
  } catch {
    toast.show('Failed to cancel render', { error: true })
  }
}

function formatDuration(seconds: number): string {
  const m = Math.floor(Math.abs(seconds) / 60)
  const s = Math.floor(Math.abs(seconds) % 60)
  return `${seconds >= 0 ? '+' : '-'}${m}:${s.toString().padStart(2, '0')}`
}
</script>

<template>
  <div class="panel-section px-4 py-3 flex flex-col gap-1.5">
    <h3 class="text-sm">Sync</h3>

    <!-- Mode toggle -->
    <div class="flex gap-4 items-center flex-wrap">
      <label class="text-sm">
        <input type="radio" :checked="syncMode === 'duration'"
               @change="syncMode = 'duration'" class="mr-1">
        Duration
      </label>
      <label class="text-sm">
        <input type="radio" :checked="syncMode === 'reference'"
               @change="syncMode = 'reference'" class="mr-1">
        Reference pair
      </label>
    </div>

    <!-- Duration input -->
    <div v-if="syncMode === 'duration'" class="flex gap-2 items-center flex-wrap">
      <input v-model="durationInput" class="input-field" placeholder="-8h23m5s">
    </div>

    <!-- Reference input -->
    <div v-if="syncMode === 'reference'" class="flex gap-2 items-center flex-wrap">
      <input v-model="refWrong" class="input-field" placeholder="wrong: 2026-04-27T23:28:01+00:00">
      <input v-model="refCorrect" class="input-field" placeholder="correct: 2026-04-27T07:05:00">
    </div>

    <div v-if="parseError" class="text-error text-sm">{{ parseError }}</div>

    <!-- Selection buttons -->
    <div class="flex gap-2 items-center flex-wrap">
      <button class="btn" @click="store.selectAll('video')">All videos</button>
      <button class="btn" @click="store.selectAll('photo')">All photos</button>
      <button class="btn" @click="store.clearSelection()">Clear</button>
      <span class="text-muted text-sm">
        {{ store.selectionCount }} of {{ store.filesWithTimestamp.length }} files selected
      </span>
    </div>

    <!-- Queue -->
    <button class="btn" :disabled="!canAddToQueue" @click="addToQueue">
      Add to queue
    </button>

    <div class="bg-surface border border-[#333] p-1.5 text-sm max-h-[120px] overflow-y-auto">
      <div v-if="store.pendingStack.length === 0" class="text-muted italic">
        No pending offsets
      </div>
      <div v-for="(entry, idx) in store.pendingStack" :key="entry.id"
           class="flex justify-between py-0.5 px-1">
        <span class="text-xs">
          {{ idx + 1 }}. {{
            entry.source.kind === 'duration'
              ? entry.source.text
              : `ref ${entry.delta_seconds >= 0 ? '+' : ''}${Math.round(entry.delta_seconds)}s`
          }} → {{
            entry.target_paths.length === 1
              ? entry.target_paths[0].split('/').pop()
              : `${entry.target_paths.length} files`
          }}
        </span>
        <button class="text-error bg-transparent border-none cursor-pointer"
                @click="removeQueueItem(idx)">×</button>
      </div>
    </div>

    <!-- Action buttons -->
    <div class="flex gap-2 items-center">
      <button class="btn" :disabled="!canUpdateTimeline" @click="updateTimeline">
        Update timeline
      </button>
      <button class="btn" :disabled="!store.hasPendingOffsets" @click="clearQueue">
        Clear queue
      </button>
      <button class="btn" :disabled="!canApply" @click="openApplyModal">
        Apply
      </button>
      <button class="btn btn-primary" @click="openRenderModal">
        Render
      </button>
    </div>

    <!-- Apply Modal -->
    <Teleport to="body">
      <div v-if="showApplyModal" class="fixed inset-0 bg-black/60 flex items-center justify-center z-[100]">
        <div class="bg-panel border border-[#444] p-5 min-w-[480px] max-w-[80vw] max-h-[80vh] flex flex-col rounded">
          <h3 class="mb-3">Confirm apply</h3>
          <div class="flex-1 overflow-y-auto font-mono text-sm bg-surface border border-[#333] p-2">
            <div v-for="f in store.shiftedFiles" :key="f.path" class="py-0.5">
              {{ f.path.split('/').pop() }}
              {{ store.originalFilesByPath[f.path]?.timestamp || '(none)' }}
              →
              {{ f.timestamp }}
            </div>
          </div>
          <div class="flex justify-end gap-2 mt-3">
            <button class="btn" @click="cancelApply">Cancel</button>
            <button class="btn btn-primary" @click="confirmApply">Apply to disk</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Render Modal -->
    <Teleport to="body">
      <div v-if="showRenderModal" class="fixed inset-0 bg-black/60 flex items-center justify-center z-[100]">
        <div class="bg-panel border border-[#444] p-5 min-w-[480px] max-w-[80vw] max-h-[80vh] flex flex-col rounded">
          <!-- Render form -->
          <div v-if="renderFormVisible">
            <h3 class="mb-3">Render Video</h3>
            <p class="text-muted text-sm mb-3">
              This will generate a stitched video from the current timeline.
              The process may take several minutes.
            </p>

            <div class="mb-2.5">
              <label class="block text-sm text-muted mb-1">Output path</label>
              <input v-model="renderOutput" class="input-field w-full" placeholder="/path/to/output.mp4">
            </div>

            <div class="mb-2.5">
              <label class="block text-sm text-muted mb-1">Aspect ratio</label>
              <div class="flex gap-2">
                <button v-for="fmt in [
                  { value: '1920x1080', label: '16:9' },
                  { value: '1080x1920', label: '9:16' },
                  { value: '1920x1440', label: '4:3' },
                  { value: '1080x1440', label: '3:4' },
                ]" :key="fmt.value"
                  class="flex-1 py-2 bg-[#2a2a2a] border border-[#444] rounded text-sm text-muted cursor-pointer"
                  :class="{ 'bg-video-bar border-video-bar text-white': renderFormat === fmt.value }"
                  @click="renderFormat = fmt.value">
                  {{ fmt.label }}
                </button>
              </div>
              <div class="text-xs text-muted text-center mt-1.5">
                {{ renderFormat.replace('x', ' × ') }}
              </div>
            </div>

            <div class="flex items-center gap-2 mb-2.5">
              <label class="flex-1 text-sm text-muted">Draft quality</label>
              <input type="checkbox" v-model="renderDraft" class="cursor-pointer">
            </div>

            <div class="mb-2.5">
              <label class="block text-sm text-muted mb-1">Image duration (seconds)</label>
              <input type="number" v-model="renderImageDuration" step="0.1" min="0.1"
                     class="input-field w-full">
            </div>

            <div class="mb-2.5">
              <label class="block text-sm text-muted mb-1">Margin (%)</label>
              <input type="number" v-model="renderMargin" step="1" min="0"
                     class="input-field w-full">
            </div>

            <div class="flex items-center gap-2 mb-2.5">
              <label class="flex-1 text-sm text-muted">Open output folder when done</label>
              <input type="checkbox" v-model="renderOpenFolder" class="cursor-pointer">
            </div>

            <div class="flex justify-end gap-2 mt-3">
              <button class="btn" @click="closeRenderModal">Cancel</button>
              <button class="btn btn-primary" @click="startRender">Start Render</button>
            </div>
          </div>

          <!-- Render progress -->
          <div v-else class="text-center py-5">
            <div class="w-10 h-10 border-[3px] border-[#333] border-t-video-bar rounded-full animate-spin mx-auto mb-3"></div>
            <p class="text-text">{{ store.renderStatus.message || 'Stitching...' }}</p>
            <button class="btn mt-3" @click="cancelRender">Cancel</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
```

- [ ] **Step 2: Write component test**

```typescript
// src/components/__tests__/SyncPanel.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import SyncPanel from '../SyncPanel.vue'
import { useAppStore } from '@/stores/appStore'
import type { FileRecord } from '@/types'

function makeFile(path: string, type: 'video' | 'photo', ts = true): FileRecord {
  return {
    path,
    type,
    timestamp: ts ? '2026-01-01T00:00:00' : null,
    duration_seconds: type === 'video' ? 30 : null,
    has_timestamp: ts,
    shifted: false,
  }
}

describe('SyncPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows no pending offsets when queue is empty', () => {
    const wrapper = mount(SyncPanel)
    expect(wrapper.text()).toContain('No pending offsets')
  })

  it('shows selection count', () => {
    const store = useAppStore()
    store.files.value = [makeFile('/v1.mp4', 'video', true)]
    const wrapper = mount(SyncPanel)
    expect(wrapper.text()).toContain('0 of 1 files selected')
  })

  it('Add to queue is disabled without input', () => {
    const wrapper = mount(SyncPanel)
    const btn = wrapper.find('button', { text: 'Add to queue' })
    expect(btn.attributes('disabled')).toBeDefined()
  })
})
```

- [ ] **Step 3: Run tests**

Run: `cd src/photowalk/web/vue-app && npm run test:run`
Expected: Tests pass

- [ ] **Step 4: Commit**

```bash
git add src/photowalk/web/vue-app/src/components/SyncPanel.vue src/photowalk/web/vue-app/src/components/__tests__/SyncPanel.test.ts
git commit -m "feat: add SyncPanel with offset queue, apply, and render modal"
```

---

### Task 8: Build Vue components — TimelinePanel

**Files:**
- Create: `src/photowalk/web/vue-app/src/components/TimelinePanel.vue`
- Test: `src/photowalk/web/vue-app/src/components/__tests__/TimelinePanel.test.ts`

- [ ] **Step 1: Write TimelinePanel.vue**

```vue
<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useTimeline } from '@/composables/useTimeline'
import type { FileRecord, TimelineEntry } from '@/types'

const store = useAppStore()
const tl = useTimeline()

const imageDuration = ref(3.5)
const timelineScale = ref(50)
const svgContainer = ref<HTMLDivElement | null>(null)
const containerWidth = ref(1000)
const showDetails = ref(false)
const detailsPath = ref<string | null>(null)

const positions = computed(() =>
  tl.computeLayout(store.timelineEntries, imageDuration.value, timelineScale.value)
)

const svgWidth = computed(() =>
  tl.computeSvgWidth(positions.value, containerWidth.value)
)

const axisTicks = computed(() =>
  tl.formatAxisTicks(positions.value, timelineScale.value, containerWidth.value)
)

const filesWithTs = computed(() =>
  store.files.filter((f) => f.has_timestamp)
)
const filesWithoutTs = computed(() =>
  store.files.filter((f) => !f.has_timestamp)
)

const selectedFile = computed(() => store.selectedFile)

const shiftedFileForDetails = computed(() => {
  if (!store.previewIsCurrent || !detailsPath.value) return null
  return store.lastPreviewFiles.find(f => f.path === detailsPath.value && f.shifted) || null
})

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function formatDateTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return isNaN(d.getTime()) ? iso : d.toISOString()
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]))
}

function selectSidebarFile(f: FileRecord, el: HTMLElement) {
  store.selectFile(f.path, 'sidebar')
  detailsPath.value = f.path
  showDetails.value = true
}

function selectTimelineBar(entry: TimelineEntry) {
  store.selectFile(entry.source_path, 'timeline')
  detailsPath.value = entry.source_path
  showDetails.value = true
}

function getNudgeDelta(): string {
  const top = store.pendingStack[store.pendingStack.length - 1]
  if (
    top &&
    top.target_paths.length === 1 &&
    top.target_paths[0] === detailsPath.value &&
    top.source.kind === 'duration'
  ) {
    return `${top.delta_seconds >= 0 ? '+' : ''}${Math.abs(top.delta_seconds)}s`
  }
  return ''
}

function nudge(delta: number) {
  if (!detailsPath.value) return
  store.nudge(detailsPath.value, delta)
}

function onImageDurationChange() {
  let val = parseFloat(String(imageDuration.value))
  if (Number.isNaN(val) || val < 0.1) val = 0.1
  imageDuration.value = val
  store.timelineSettings.image_duration = val
}

function zoomIn() {
  timelineScale.value = Math.min(500, timelineScale.value * 1.2)
}

function zoomOut() {
  timelineScale.value = Math.max(5, timelineScale.value / 1.2)
}

const zoomPct = computed(() =>
  Math.round((timelineScale.value / 50) * 100) + '%'
)

onMounted(() => {
  imageDuration.value = store.timelineSettings.image_duration
  // Measure container width
  if (svgContainer.value) {
    containerWidth.value = svgContainer.value.clientWidth
  }
  // Load initial data
  store.loadInitial()
})

// Re-measure on resize
const ro = new ResizeObserver((entries) => {
  for (const entry of entries) {
    containerWidth.value = entry.contentRect.width
  }
})

onMounted(() => {
  if (svgContainer.value) {
    ro.observe(svgContainer.value)
  }
})
</script>

<template>
  <div class="flex flex-1 overflow-hidden">
    <!-- Sidebar -->
    <div class="w-[260px] bg-panel border-r border-[#333] flex flex-col overflow-hidden">
      <h3 class="px-4 py-3 text-sm border-b border-[#333]">Source Files</h3>
      <div class="flex-1 overflow-y-auto">
        <div
          v-for="f in [...filesWithTs, ...filesWithoutTs]"
          :key="f.path"
          class="flex items-start gap-2 px-4 py-2.5 border-b border-[#222] cursor-pointer text-sm"
          :class="[
            { 'bg-[#1e2a4a]': !store.selectedPath || store.selectedPath !== f.path },
            { 'bg-[#2a3a5a]': store.selectedPath === f.path },
            { 'italic': f.shifted },
          ]"
          @click="selectSidebarFile(f, $event.currentTarget as HTMLElement)"
        >
          <input
            type="checkbox"
            :checked="store.selection.has(f.path)"
            :disabled="!f.has_timestamp"
            @change.stop="store.toggleSelection(f.path, ($event.target as HTMLInputElement).checked)"
            class="mt-0.5 cursor-pointer"
          >
          <div class="flex-1 min-w-0">
            <div class="whitespace-nowrap overflow-hidden text-ellipsis text-text">
              {{ f.type === 'video' ? '🎬' : '📷' }} {{ f.path.split('/').pop() }}
              <span v-if="f.shifted" class="inline-block bg-accent text-app-bg text-[0.65rem] px-1 py-0.5 rounded ml-1.5">
                shifted
              </span>
            </div>
            <div class="text-muted text-xs mt-0.5" :class="{ 'text-error': !f.has_timestamp }">
              {{ f.timestamp ? new Date(f.timestamp).toISOString() : 'No timestamp' }}
              {{ f.duration_seconds ? ` • ${f.duration_seconds.toFixed(1)}s` : '' }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Timeline -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <div class="flex items-center justify-between gap-3 px-2 py-1">
        <h3 class="text-sm m-0">Timeline</h3>
        <div class="flex items-center gap-1.5 text-sm text-[#ccc]">
          <label>Photo duration:</label>
          <input type="number" v-model="imageDuration" step="0.1" min="0.1"
                 class="w-14 px-1.5 py-0.5 text-sm bg-[#2a2a2a] border border-[#444] rounded text-text text-right"
                 @change="onImageDurationChange">
          <span>s</span>
        </div>
        <div class="flex items-center gap-1.5 text-sm text-[#ccc]">
          <button class="bg-[#2a2a2a] border border-[#444] rounded text-text cursor-pointer px-2 min-w-[28px]"
                  @click="zoomOut">−</button>
          <span class="min-w-[42px] text-center">{{ zoomPct }}</span>
          <button class="bg-[#2a2a2a] border border-[#444] rounded text-text cursor-pointer px-2 min-w-[28px]"
                  @click="zoomIn">+</button>
        </div>
      </div>

      <!-- Timeline SVG -->
      <div ref="svgContainer" class="flex-1 overflow-x-auto overflow-y-hidden relative">
        <svg :width="svgWidth" :height="tl.BAR_HEIGHT + tl.PADDING * 2">
          <rect
            v-for="pos in positions"
            :key="pos.entry.source_path"
            :x="pos.x"
            :y="tl.PADDING"
            :width="pos.width"
            :height="tl.BAR_HEIGHT"
            rx="3"
            :class="[
              'cursor-pointer stroke-white stroke-[1px]',
              pos.entry.kind === 'image' ? 'fill-image-bar' : 'fill-video-bar',
              { 'stroke-yellow-400 stroke-2': store.selectedPath === pos.entry.source_path },
            ]"
            @click="selectTimelineBar(pos.entry)"
          />
          <text
            v-for="pos in positions"
            v-if="pos.width > 40"
            :key="'label-' + pos.entry.source_path"
            :x="pos.x + 4"
            :y="tl.PADDING + tl.BAR_HEIGHT / 2"
            class="fill-white text-[11px] pointer-events-none"
            dominant-baseline="middle"
          >
            {{ pos.entry.source_path.split('/').pop().length > 30
               ? pos.entry.source_path.split('/').pop().slice(0, 28) + '…'
               : pos.entry.source_path.split('/').pop() }}
          </text>
        </svg>
      </div>

      <!-- Axis -->
      <div class="h-[30px] border-t border-[#333] bg-panel relative">
        <div
          v-for="tick in axisTicks"
          :key="tick.seconds"
          class="absolute top-0 text-[11px] text-muted pl-1 border-l border-[#444] h-full whitespace-nowrap"
          :style="{ left: tick.x + 'px' }"
        >
          {{ tick.label }}
        </div>
      </div>
    </div>

    <!-- Details Panel -->
    <div class="w-[300px] bg-panel border-l border-[#333] flex flex-col overflow-hidden">
      <h3 class="px-4 py-3 text-sm border-b border-[#333]">Details</h3>
      <div class="flex-1 overflow-y-auto px-4 py-3">
        <div v-if="!detailsPath" class="text-muted italic text-center pt-10">
          Select a file to see data
        </div>
        <template v-else-if="selectedFile">
          <!-- Nudge controls (only for timeline selection) -->
          <div v-if="store.selectedSource === 'timeline'" class="mb-4">
            <h4 class="text-[0.7rem] uppercase tracking-wide text-muted mb-1.5 flex items-center gap-1.5">
              Adjust
              <span v-if="shiftedFileForDetails" class="bg-accent text-app-bg text-[0.65rem] px-1 py-0.5 rounded">Pending sync</span>
            </h4>
            <div class="flex items-center justify-center gap-3">
              <button class="btn" @click="nudge(-1)">←</button>
              <span class="text-accent text-sm font-mono min-w-[36px] text-center">
                {{ getNudgeDelta() }}
              </span>
              <button class="btn" @click="nudge(1)">→</button>
            </div>
          </div>

          <!-- File info -->
          <div class="mb-4">
            <h4 class="text-[0.7rem] uppercase tracking-wide text-muted mb-1.5">File</h4>
            <div class="flex justify-between text-sm py-0.5 gap-2">
              <span class="text-muted">Name</span>
              <span class="text-text text-right"><strong>{{ selectedFile.path.split('/').pop() }}</strong></span>
            </div>
            <div class="flex justify-between text-sm py-0.5 gap-2">
              <span class="text-muted">Type</span>
              <span class="text-text text-right">{{ selectedFile.type }}</span>
            </div>
            <div class="flex flex-col gap-0.5 text-sm">
              <span class="text-muted">Path</span>
              <span class="text-text font-mono text-xs break-all w-full">{{ selectedFile.path }}</span>
            </div>
          </div>

          <!-- Timestamps -->
          <div class="mb-4">
            <h4 class="text-[0.7rem] uppercase tracking-wide text-muted mb-1.5">
              Timestamps
              <span v-if="shiftedFileForDetails" class="bg-accent text-app-bg text-[0.65rem] px-1 py-0.5 rounded ml-1">Pending sync</span>
            </h4>

            <template v-if="selectedFile.type === 'photo'">
              <div class="flex justify-between text-sm py-0.5 gap-2">
                <span class="text-muted">Captured</span>
                <span class="text-text text-right">
                  <template v-if="shiftedFileForDetails">
                    <span class="text-muted line-through mr-1">{{ formatDateTime(selectedFile.timestamp) }}</span>
                    <span class="text-accent">→</span>
                    <span class="font-semibold ml-1">{{ formatDateTime(shiftedFileForDetails.timestamp) }}</span>
                  </template>
                  <template v-else>
                    {{ formatDateTime(selectedFile.timestamp) }}
                  </template>
                </span>
              </div>
            </template>
            <template v-else>
              <div class="flex justify-between text-sm py-0.5 gap-2">
                <span class="text-muted">Start</span>
                <span class="text-text text-right">
                  <template v-if="shiftedFileForDetails">
                    <span class="text-muted line-through mr-1">{{ formatDateTime(selectedFile.timestamp) }}</span>
                    <span class="text-accent">→</span>
                    <span class="font-semibold ml-1">{{ formatDateTime(shiftedFileForDetails.timestamp) }}</span>
                  </template>
                  <template v-else>
                    {{ formatDateTime(selectedFile.timestamp) }}
                  </template>
                </span>
              </div>
              <div class="flex justify-between text-sm py-0.5 gap-2">
                <span class="text-muted">End</span>
                <span class="text-text text-right">
                  <template v-if="shiftedFileForDetails">
                    <span class="text-muted line-through mr-1">{{ formatDateTime(selectedFile.end_timestamp ?? null) }}</span>
                    <span class="text-accent">→</span>
                    <span class="font-semibold ml-1">{{ formatDateTime(shiftedFileForDetails.end_timestamp ?? null) }}</span>
                  </template>
                  <template v-else>
                    {{ formatDateTime(selectedFile.end_timestamp ?? null) }}
                  </template>
                </span>
              </div>
              <div class="flex justify-between text-sm py-0.5 gap-2">
                <span class="text-muted">Duration</span>
                <span class="text-text text-right">
                  {{ selectedFile.duration_seconds != null ? selectedFile.duration_seconds.toFixed(2) + 's' : '—' }}
                </span>
              </div>
            </template>
          </div>

          <!-- Camera (photos only) -->
          <div v-if="selectedFile.type === 'photo'" class="mb-4">
            <template v-if="selectedFile.camera_model || selectedFile.shutter_speed || selectedFile.iso != null">
              <h4 class="text-[0.7rem] uppercase tracking-wide text-muted mb-1.5">Camera</h4>
              <div v-if="selectedFile.camera_model" class="flex justify-between text-sm py-0.5 gap-2">
                <span class="text-muted">Camera</span>
                <span class="text-text text-right">{{ selectedFile.camera_model }}</span>
              </div>
              <div v-if="selectedFile.shutter_speed" class="flex justify-between text-sm py-0.5 gap-2">
                <span class="text-muted">Shutter</span>
                <span class="text-text text-right">{{ selectedFile.shutter_speed }}</span>
              </div>
              <div v-if="selectedFile.iso != null" class="flex justify-between text-sm py-0.5 gap-2">
                <span class="text-muted">ISO</span>
                <span class="text-text text-right">{{ selectedFile.iso }}</span>
              </div>
              <div v-if="selectedFile.focal_length" class="flex justify-between text-sm py-0.5 gap-2">
                <span class="text-muted">Focal length</span>
                <span class="text-text text-right">{{ selectedFile.focal_length }}</span>
              </div>
            </template>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fill-video-bar { fill: #4a90d9; }
.fill-image-bar { fill: #5cb85c; }
</style>
```

- [ ] **Step 2: Write component test**

```typescript
// src/components/__tests__/TimelinePanel.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import TimelinePanel from '../TimelinePanel.vue'
import { useAppStore } from '@/stores/appStore'
import type { FileRecord, TimelineEntry } from '@/types'

function makeFile(path: string, type: 'video' | 'photo', ts = true): FileRecord {
  return {
    path,
    type,
    timestamp: ts ? '2026-01-01T00:00:00' : null,
    duration_seconds: type === 'video' ? 30 : null,
    has_timestamp: ts,
    shifted: false,
  }
}

describe('TimelinePanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows "Source Files" header', () => {
    const wrapper = mount(TimelinePanel)
    expect(wrapper.text()).toContain('Source Files')
  })

  it('shows "Timeline" header', () => {
    const wrapper = mount(TimelinePanel)
    expect(wrapper.text()).toContain('Timeline')
  })

  it('shows "Details" header', () => {
    const wrapper = mount(TimelinePanel)
    expect(wrapper.text()).toContain('Details')
  })

  it('shows empty details message when no file selected', () => {
    const wrapper = mount(TimelinePanel)
    expect(wrapper.text()).toContain('Select a file to see data')
  })

  it('renders sidebar items for files with and without timestamps', () => {
    const store = useAppStore()
    store.files.value = [
      makeFile('/with-ts.mp4', 'video', true),
      makeFile('/no-ts.jpg', 'photo', false),
    ]
    const wrapper = mount(TimelinePanel)
    expect(wrapper.text()).toContain('with-ts.mp4')
    expect(wrapper.text()).toContain('no-ts.jpg')
  })

  it('files without timestamps have checkbox disabled', () => {
    const store = useAppStore()
    store.files.value = [makeFile('/no-ts.jpg', 'photo', false)]
    const wrapper = mount(TimelinePanel)
    const checkbox = wrapper.find('input[type="checkbox"]')
    expect(checkbox.attributes('disabled')).toBeDefined()
  })
})
```

- [ ] **Step 3: Run tests**

Run: `cd src/photowalk/web/vue-app && npm run test:run`
Expected: Tests pass

- [ ] **Step 4: Commit**

```bash
git add src/photowalk/web/vue-app/src/components/TimelinePanel.vue src/photowalk/web/vue-app/src/components/__tests__/TimelinePanel.test.ts
git commit -m "feat: add TimelinePanel with sidebar, SVG timeline, axis, and details"
```

---

### Task 9: Wire App.vue and add Toast component

**Files:**
- Modify: `src/photowalk/web/vue-app/src/App.vue`
- Create: `src/photowalk/web/vue-app/src/components/Toast.vue`

- [ ] **Step 1: Write Toast.vue**

```vue
<script setup lang="ts">
import { useToast } from '@/composables/useToast'

const { toast, dismiss } = useToast()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="toast"
      class="fixed bottom-5 right-5 bg-panel border px-4 py-3 z-[101] max-w-[400px] rounded"
      :class="{ 'border-error': toast.isError }"
    >
      <div class="flex items-start justify-between gap-2">
        <pre class="whitespace-pre-wrap text-sm text-text">{{ toast.message }}</pre>
        <button
          v-if="toast.sticky"
          class="text-muted bg-transparent border-none cursor-pointer text-lg"
          @click="dismiss"
        >×</button>
      </div>
    </div>
  </Teleport>
</template>
```

- [ ] **Step 2: Update App.vue**

```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import { useAppStore } from '@/stores/appStore'
import PreviewPanel from './components/PreviewPanel.vue'
import SyncPanel from './components/SyncPanel.vue'
import TimelinePanel from './components/TimelinePanel.vue'
import Toast from './components/Toast.vue'

const store = useAppStore()

onMounted(() => {
  store.loadInitial()
})
</script>

<template>
  <div class="flex flex-col h-screen bg-app-bg text-text overflow-hidden">
    <PreviewPanel />
    <SyncPanel />
    <TimelinePanel />
    <Toast />
  </div>
</template>
```

- [ ] **Step 3: Commit**

```bash
git add src/photowalk/web/vue-app/src/App.vue src/photowalk/web/vue-app/src/components/Toast.vue
git commit -m "feat: wire App.vue with 3-panel layout and Toast component"
```

---

### Task 10: Wire backend to serve Vue app

**Files:**
- Modify: `src/photowalk/web/server.py`

- [ ] **Step 1: Update server.py to serve Vue build output**

```python
# In server.py, modify _load_asset and create_app

def _load_asset(filename: str) -> str:
    # Changed from: asset_dir = Path(__file__).parent / "assets"
    # Now serves from vue-app/dist
    vue_dist = Path(__file__).parent / "vue-app" / "dist"
    if (vue_dist / filename).exists():
        return (vue_dist / filename).read_text()
    # Fallback to old assets for backwards compat during dev
    asset_dir = Path(__file__).parent / "assets"
    return (asset_dir / filename).read_text()

# In create_app, update the asset route:
@app.get("/assets/{filename}")
async def asset(filename: str):
    # Serve from vue-app/dist in production
    vue_dist = Path(__file__).parent / "vue-app" / "dist" / "assets"
    file_path = vue_dist / filename
    if file_path.exists():
        return FileResponse(file_path)
    # Fallback to old assets
    allowed = {"style.css", "app.js", "index.html"}
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="Asset not found")
    content = _load_asset(filename)
    media_type = (
        "text/css"
        if filename.endswith(".css")
        else "application/javascript"
        if filename.endswith(".js")
        else "text/html"
    )
    return HTMLResponse(content=content, media_type=media_type)
```

- [ ] **Step 2: Add a vite.config.ts that outputs to the correct dist dir**

The vite.config.ts from Task 1 already builds to `dist/`. In production, the Vue app needs to be built before serving:

```bash
cd src/photowalk/web/vue-app && npm run build
```

This produces `src/photowalk/web/vue-app/dist/` with `index.html` and `assets/` subdirectory.

- [ ] **Step 3: Commit**

```bash
git add src/photowalk/web/server.py
git commit -m "feat: serve Vue build output from vue-app/dist in server.py"
```

---

### Task 11: Manual testing and cleanup

**Files:**
- Delete: `src/photowalk/web/assets/app.js`
- Delete: `src/photowalk/web/assets/style.css`
- Keep: `src/photowalk/web/assets/index.html` (as fallback only)

- [ ] **Step 1: Build the Vue app**

Run: `cd src/photowalk/web/vue-app && npm run build`
Expected: `vue-app/dist/` directory with `index.html` and `assets/`

- [ ] **Step 2: Run the FastAPI server**

Run: `uv run photowalk web ~/Photos/ --port 8080`
Expected: Server starts without errors

- [ ] **Step 3: Smoke test in browser**

Open `http://localhost:8080` and verify:
- Preview panel shows when clicking files
- Sync panel: can parse offsets, add to queue, update timeline
- Apply modal shows diff and confirms
- Render modal opens and starts render
- Timeline renders SVG bars correctly
- Details panel shows file info
- Zoom controls work
- Toast notifications appear

- [ ] **Step 4: Remove old assets (optional — keep as fallback)**

Only remove after everything is confirmed working:

```bash
rm src/photowalk/web/assets/app.js
rm src/photowalk/web/assets/style.css
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete Vue migration — replace vanilla JS with Vue 3 SPA"
```

---

## File Summary

| File | Purpose |
|---|---|
| `src/photowalk/web/vue-app/package.json` | Dependencies and scripts |
| `src/photowalk/web/vue-app/vite.config.ts` | Vite config with API proxy |
| `src/photowalk/web/vue-app/tsconfig.json` | TypeScript config |
| `src/photowalk/web/vue-app/tailwind.config.js` | Tailwind theme |
| `src/photowalk/web/vue-app/postcss.config.js` | PostCSS config |
| `src/photowalk/web/vue-app/index.html` | SPA entry point |
| `src/photowalk/web/vue-app/src/main.ts` | Vue app bootstrap |
| `src/photowalk/web/vue-app/src/style.css` | Tailwind directives + custom classes |
| `src/photowalk/web/vue-app/src/App.vue` | Root layout |
| `src/photowalk/web/vue-app/src/types/index.ts` | All TypeScript types |
| `src/photowalk/web/vue-app/src/stores/appStore.ts` | Pinia store |
| `src/photowalk/web/vue-app/src/composables/useApi.ts` | API client |
| `src/photowalk/web/vue-app/src/composables/useTimeline.ts` | Timeline layout math |
| `src/photowalk/web/vue-app/src/composables/useToast.ts` | Toast notifications |
| `src/photowalk/web/vue-app/src/components/PreviewPanel.vue` | Preview + timestamp |
| `src/photowalk/web/vue-app/src/components/SyncPanel.vue` | Sync controls + modals |
| `src/photowalk/web/vue-app/src/components/TimelinePanel.vue` | Sidebar + timeline + details |
| `src/photowalk/web/vue-app/src/components/Toast.vue` | Toast notification component |
| `src/photowalk/web/server.py` | Modified to serve Vue build |
