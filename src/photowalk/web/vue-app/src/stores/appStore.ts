// src/stores/appStore.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  FileRecord,
  TimelineEntry,
  TimelineSettings,
  OffsetEntry,
  RenderStatus,
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
  const trimStart = ref<number | undefined>()
  const trimEnd = ref<number | undefined>()
  const isPlaying = ref(false)
  const currentTime = ref(0)
  const scanPath = ref<string | null>(null)
  const selectedTimelineEntry = ref<TimelineEntry | null>(null)

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
  function selectFile(path: string, source: 'sidebar' | 'timeline', tStart?: number, tEnd?: number) {
    selectedPath.value = path
    selectedSource.value = source
    trimStart.value = tStart
    trimEnd.value = tEnd
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
    selection.value = new Set(selection.value)
  }

  function selectAll(type: 'video' | 'photo') {
    filesWithTimestamp.value
      .filter((f) => f.type === type)
      .forEach((f) => selection.value.add(f.path))
    selection.value = new Set(selection.value)
  }

  function clearSelection() {
    selection.value.clear()
    selectedTimelineEntry.value = null
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
        (top.source as { kind: 'duration'; text: string }).text = formatSignedSeconds(top.delta_seconds)
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

  // ─── Async actions ───
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
      selectedTimelineEntry.value = null
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
    files, originalFilesByPath, selection, pendingStack,
    previewIsCurrent, lastPreviewFiles, timelineEntries,
    timelineSettings, selectedPath, selectedSource,
    renderStatus, currentVideoFile, trimStart, trimEnd, isPlaying, currentTime, scanPath,
    selectedTimelineEntry,
    // Computed
    filesWithTimestamp, selectionCount, hasPendingOffsets, shiftedFiles, selectedFile,
    // Actions
    selectFile, toggleSelection, selectAll, clearSelection,
    addToQueue, removeFromQueue, clearQueue, nudge, setPlaybackState,
    // Async
    loadInitial, updateTimeline, applySync,
  }
})
