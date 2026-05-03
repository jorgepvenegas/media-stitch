<script setup lang="ts">
import PreviewPanel from './components/PreviewPanel.vue'
import SyncPanel from './components/SyncPanel.vue'
import TimelinePanel from './components/TimelinePanel.vue'
import Toast from './components/Toast.vue'
import { useAppStore } from '@/stores/appStore'
import { computed } from 'vue'

const store = useAppStore()

// ─── Details panel (right sidebar) ───
const selectedFile = computed(() => store.selectedFile)
const detailsPath = computed(() => store.selectedPath)

const shiftedFileForDetails = computed(() => {
  if (!store.previewIsCurrent || !detailsPath.value) return null
  return store.lastPreviewFiles.find(f => f.path === detailsPath.value && f.shifted) || null
})

function formatDateTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return isNaN(d.getTime()) ? iso : d.toISOString()
}

function basename(path: string): string {
  return path.split('/').pop() || ''
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function getNudgeDelta(): string {
  if (!detailsPath.value) return ''
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

async function nudge(delta: number) {
  if (!detailsPath.value) return
  store.nudge(detailsPath.value, delta)
  await store.updateTimeline()
}
</script>

<template>
  <div class="flex h-screen bg-app-bg overflow-hidden">
    <!-- Main content -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <PreviewPanel class="flex-1 min-h-0" />
      <SyncPanel />
      <TimelinePanel />
    </div>

    <!-- Right sidebar: Details panel -->
    <div class="w-[300px] bg-panel border-l border-[#333] flex flex-col overflow-hidden">
      <h3 class="px-4 py-3 text-sm border-b border-[#333]">Details</h3>
      <div class="flex-1 overflow-y-auto px-4 py-3">
        <div v-if="!detailsPath" class="text-muted italic text-center pt-10">Select a file to see data</div>
        <template v-else-if="selectedFile">
          <!-- Nudge controls -->
          <div class="mb-4">
            <h4 class="text-[0.7rem] uppercase tracking-wide text-muted mb-1.5 flex items-center gap-1.5">
              Adjust
              <span v-if="shiftedFileForDetails" class="bg-accent text-app-bg text-[0.65rem] px-1 py-0.5 rounded">Pending sync</span>
            </h4>
            <div class="flex items-center justify-center gap-3">
              <button class="btn" @click="nudge(-1)">←</button>
              <span class="text-accent text-sm font-mono min-w-[36px] text-center">{{ getNudgeDelta() }}</span>
              <button class="btn" @click="nudge(1)">→</button>
            </div>
          </div>

          <!-- Segment info -->
          <div v-if="store.selectedTimelineEntry?.kind === 'video_segment'" class="mb-4">
            <h4 class="text-[0.7rem] uppercase tracking-wide text-muted mb-1.5">This segment</h4>
            <div class="flex justify-between text-sm py-0.5 gap-2">
              <span class="text-muted">Start on timeline</span>
              <span class="text-right">{{ formatDateTime(store.selectedTimelineEntry.start_time) }}</span>
            </div>
            <div class="flex justify-between text-sm py-0.5 gap-2">
              <span class="text-muted">Trim start</span>
              <span class="text-right">{{ store.selectedTimelineEntry.trim_start != null ? formatTime(store.selectedTimelineEntry.trim_start) + 's' : '—' }}</span>
            </div>
            <div class="flex justify-between text-sm py-0.5 gap-2">
              <span class="text-muted">Trim end</span>
              <span class="text-right">{{ store.selectedTimelineEntry.trim_end != null ? formatTime(store.selectedTimelineEntry.trim_end) + 's' : '—' }}</span>
            </div>
            <div class="flex justify-between text-sm py-0.5 gap-2">
              <span class="text-muted">Segment duration</span>
              <span class="text-right">{{ store.selectedTimelineEntry.duration_seconds != null ? store.selectedTimelineEntry.duration_seconds.toFixed(2) + 's' : '—' }}</span>
            </div>
          </div>

          <!-- File info -->
          <div class="mb-4">
            <h4 class="text-[0.7rem] uppercase tracking-wide text-muted mb-1.5">File</h4>
            <div class="flex justify-between text-sm py-0.5 gap-2">
              <span class="text-muted">Name</span>
              <span class="text-right"><strong>{{ basename(selectedFile.path) }}</strong></span>
            </div>
            <div class="flex justify-between text-sm py-0.5 gap-2">
              <span class="text-muted">Type</span>
              <span class="text-right">{{ selectedFile.type }}</span>
            </div>
            <div class="flex flex-col gap-0.5 text-sm">
              <span class="text-muted">Path</span>
              <span class="font-mono text-xs break-all w-full">{{ selectedFile.path }}</span>
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
                <span class="text-right">
                  <template v-if="shiftedFileForDetails">
                    <span class="text-muted line-through mr-1">{{ formatDateTime(selectedFile.timestamp) }}</span>
                    <span class="text-accent">→</span>
                    <span class="font-semibold ml-1">{{ formatDateTime(shiftedFileForDetails.timestamp) }}</span>
                  </template>
                  <template v-else>{{ formatDateTime(selectedFile.timestamp) }}</template>
                </span>
              </div>
            </template>
            <template v-else>
              <div class="flex justify-between text-sm py-0.5 gap-2">
                <span class="text-muted">Start</span>
                <span class="text-right">
                  <template v-if="shiftedFileForDetails">
                    <span class="text-muted line-through mr-1">{{ formatDateTime(selectedFile.timestamp) }}</span>
                    <span class="text-accent">→</span>
                    <span class="font-semibold ml-1">{{ formatDateTime(shiftedFileForDetails.timestamp) }}</span>
                  </template>
                  <template v-else>{{ formatDateTime(selectedFile.timestamp) }}</template>
                </span>
              </div>
              <div class="flex justify-between text-sm py-0.5 gap-2">
                <span class="text-muted">End</span>
                <span class="text-right">
                  <template v-if="shiftedFileForDetails">
                    <span class="text-muted line-through mr-1">{{ formatDateTime(selectedFile.end_timestamp ?? null) }}</span>
                    <span class="text-accent">→</span>
                    <span class="font-semibold ml-1">{{ formatDateTime(shiftedFileForDetails.end_timestamp ?? null) }}</span>
                  </template>
                  <template v-else>{{ formatDateTime(selectedFile.end_timestamp ?? null) }}</template>
                </span>
              </div>
              <div class="flex justify-between text-sm py-0.5 gap-2">
                <span class="text-muted">Duration</span>
                <span class="text-right">{{ selectedFile.duration_seconds != null ? selectedFile.duration_seconds.toFixed(2) + 's' : '—' }}</span>
              </div>
            </template>
          </div>

          <!-- Camera (photos only) -->
          <div v-if="selectedFile.type === 'photo'" class="mb-4">
            <template v-if="selectedFile.camera_model || selectedFile.shutter_speed || selectedFile.iso != null">
              <h4 class="text-[0.7rem] uppercase tracking-wide text-muted mb-1.5">Camera</h4>
              <div v-if="selectedFile.camera_model" class="flex justify-between text-sm py-0.5 gap-2">
                <span class="text-muted">Camera</span><span class="text-right">{{ selectedFile.camera_model }}</span>
              </div>
              <div v-if="selectedFile.shutter_speed" class="flex justify-between text-sm py-0.5 gap-2">
                <span class="text-muted">Shutter</span><span class="text-right">{{ selectedFile.shutter_speed }}</span>
              </div>
              <div v-if="selectedFile.iso != null" class="flex justify-between text-sm py-0.5 gap-2">
                <span class="text-muted">ISO</span><span class="text-right">{{ selectedFile.iso }}</span>
              </div>
              <div v-if="selectedFile.focal_length" class="flex justify-between text-sm py-0.5 gap-2">
                <span class="text-muted">Focal length</span><span class="text-right">{{ selectedFile.focal_length }}</span>
              </div>
            </template>
          </div>
        </template>
      </div>
    </div>

    <Toast />
  </div>
</template>
