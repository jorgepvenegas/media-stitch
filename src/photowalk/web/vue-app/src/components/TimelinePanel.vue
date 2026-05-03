<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useTimeline } from '@/composables/useTimeline'
import type { FileRecord, TimelineEntry } from '@/types'

const store = useAppStore()
const tl = useTimeline()

const imageDuration = ref(3.5)
const timelineScale = ref(50)
const svgContainer = ref<HTMLDivElement | null>(null)
const containerWidth = ref(1000)

const positions = computed(() =>
  tl.computeLayout(store.timelineEntries, imageDuration.value, timelineScale.value)
)

const svgWidth = computed(() =>
  tl.computeSvgWidth(positions.value, containerWidth.value)
)

const axisTicks = computed(() =>
  tl.formatAxisTicks(positions.value, timelineScale.value, containerWidth.value)
)

const filesWithTs = computed(() => store.files.filter((f) => f.has_timestamp))
const filesWithoutTs = computed(() => store.files.filter((f) => !f.has_timestamp))

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

function selectSidebarFile(f: FileRecord) {
  store.selectFile(f.path, 'sidebar')
}

function basename(path: string): string {
  return path.split('/').pop() || ''
}

function selectTimelineBar(entry: TimelineEntry) {
  store.selectFile(entry.source_path, 'timeline')
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

function zoomIn() { timelineScale.value = Math.min(500, timelineScale.value * 1.2) }
function zoomOut() { timelineScale.value = Math.max(5, timelineScale.value / 1.2) }

const zoomPct = computed(() => Math.round((timelineScale.value / 50) * 100) + '%')

let ro: ResizeObserver | null = null

onMounted(() => {
  imageDuration.value = store.timelineSettings.image_duration
  if (svgContainer.value) {
    containerWidth.value = svgContainer.value.clientWidth
    ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        containerWidth.value = entry.contentRect.width
      }
    })
    ro.observe(svgContainer.value)
  }
  store.loadInitial()
})

onUnmounted(() => {
  if (ro) ro.disconnect()
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
          :class="[store.selectedPath === f.path ? 'bg-[#2a3a5a]' : 'hover:bg-[#1e2a4a]']"
          @click="selectSidebarFile(f)"
        >
          <input
            type="checkbox"
            :checked="store.selection.has(f.path)"
            :disabled="!f.has_timestamp"
            @change.stop="store.toggleSelection(f.path, ($event.target as HTMLInputElement).checked)"
            @click.stop
            class="mt-0.5 cursor-pointer"
          />
          <div class="flex-1 min-w-0">
            <div class="whitespace-nowrap overflow-hidden text-ellipsis">
              {{ f.type === 'video' ? '🎬' : '📷' }} {{ basename(f.path) }}
              <span v-if="f.shifted" class="inline-block bg-accent text-app-bg text-[0.65rem] px-1 py-0.5 rounded ml-1.5">shifted</span>
            </div>
            <div class="text-muted text-xs mt-0.5" :class="{ 'text-error': !f.has_timestamp }">
              {{ f.timestamp ? new Date(f.timestamp).toISOString() : 'No timestamp' }}{{ f.duration_seconds ? ` • ${f.duration_seconds.toFixed(1)}s` : '' }}
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
          <input type="number" v-model.number="imageDuration" step="0.1" min="0.1"
                 class="w-14 px-1.5 py-0.5 text-sm bg-[#2a2a2a] border border-[#444] rounded text-right focus:border-blue-400 focus:outline-none"
                 @change="onImageDurationChange">
          <span>s</span>
        </div>
        <div class="flex items-center gap-1.5 text-sm text-[#ccc]">
          <button class="bg-[#2a2a2a] border border-[#444] rounded cursor-pointer px-2 min-w-[28px] hover:bg-[#3a3a3a]" @click="zoomOut">−</button>
          <span class="min-w-[42px] text-center">{{ zoomPct }}</span>
          <button class="bg-[#2a2a2a] border border-[#444] rounded cursor-pointer px-2 min-w-[28px] hover:bg-[#3a3a3a]" @click="zoomIn">+</button>
        </div>
      </div>

      <!-- Timeline SVG -->
      <div ref="svgContainer" class="flex-1 overflow-x-auto overflow-y-hidden relative">
        <svg :width="svgWidth" :height="tl.BAR_HEIGHT + tl.PADDING * 2">
          <rect
            v-for="pos in positions"
            :key="pos.entry.source_path"
            :x="pos.x" :y="tl.PADDING" :width="pos.width" :height="tl.BAR_HEIGHT" rx="3"
            :class="['cursor-pointer stroke-white stroke-[1px]', pos.entry.kind === 'image' ? 'fill-image-bar' : 'fill-video-bar']"
            @click="selectTimelineBar(pos.entry)"
          />
          <template v-for="pos in positions" :key="'label-' + pos.entry.source_path">
            <text
              v-if="pos.width > 40"
              :x="pos.x + 4" :y="tl.PADDING + tl.BAR_HEIGHT / 2"
              class="fill-white text-[11px] pointer-events-none"
              dominant-baseline="middle"
            >{{ basename(pos.entry.source_path).length > 30 ? basename(pos.entry.source_path).slice(0, 28) + '…' : basename(pos.entry.source_path) }}</text>
          </template>
        </svg>
      </div>

      <!-- Axis -->
      <div class="h-[30px] border-t border-[#333] bg-panel relative">
        <div
          v-for="tick in axisTicks"
          :key="tick.seconds"
          class="absolute top-0 text-[11px] text-muted pl-1 border-l border-[#444] h-full whitespace-nowrap"
          :style="{ left: tick.x + 'px' }"
        >{{ tick.label }}</div>
      </div>
    </div>

    <!-- Details Panel -->
    <div class="w-[300px] bg-panel border-l border-[#333] flex flex-col overflow-hidden">
      <h3 class="px-4 py-3 text-sm border-b border-[#333]">Details</h3>
      <div class="flex-1 overflow-y-auto px-4 py-3">
        <div v-if="!detailsPath" class="text-muted italic text-center pt-10">Select a file to see data</div>
        <template v-else-if="selectedFile">
          <!-- Nudge controls -->
          <div v-if="store.selectedSource === 'timeline'" class="mb-4">
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
  </div>
</template>

<style scoped>
.fill-video-bar { fill: #4a90d9; }
.fill-image-bar { fill: #5cb85c; }
</style>
