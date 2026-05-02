<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
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
let renderPollInterval: ReturnType<typeof setInterval> | null = null

// Listen for "use as correct" events from PreviewPanel
function handleUseRefEvent(e: Event) {
  const detail = (e as CustomEvent).detail as string
  syncMode.value = 'reference'
  refCorrect.value = detail
}

onMounted(() => {
  window.addEventListener('use-ref-timestamp', handleUseRefEvent)
})
onUnmounted(() => {
  window.removeEventListener('use-ref-timestamp', handleUseRefEvent)
})

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
const canApply = computed(() => store.hasPendingOffsets && store.previewIsCurrent)

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

async function clearQueue() {
  store.clearQueue()
  await store.updateTimeline()
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
  if (renderPollInterval) {
    clearInterval(renderPollInterval)
    renderPollInterval = null
  }
}

async function startRender() {
  if (!renderOutput.value.trim()) {
    toast.show('Output path is required', { error: true })
    return
  }
  try {
    await api.startRender({
      output: renderOutput.value,
      format: renderFormat.value,
      draft: renderDraft.value,
      image_duration: renderImageDuration.value,
      margin: renderMargin.value,
      open_folder: renderOpenFolder.value,
    })
    renderFormVisible.value = false

    renderPollInterval = setInterval(async () => {
      try {
        const status = await api.pollRenderStatus()
        store.renderStatus = status
        if (status.state === 'done') {
          clearInterval(renderPollInterval!)
          renderPollInterval = null
          if (renderOpenFolder.value && status.output_path) {
            const dir = status.output_path.split('/').slice(0, -1).join('/') || '.'
            api.openFolder(dir).catch(() => {})
          }
          toast.show('Render complete')
          closeRenderModal()
        } else if (status.state === 'cancelled') {
          clearInterval(renderPollInterval!)
          renderPollInterval = null
          toast.show('Render cancelled')
          closeRenderModal()
        } else if (status.state === 'error') {
          clearInterval(renderPollInterval!)
          renderPollInterval = null
          toast.show(status.message || 'Render failed', { error: true, sticky: true })
          closeRenderModal()
        }
      } catch { /* ignore poll errors */ }
    }, 1000)
  } catch (e: any) {
    if (e.message?.includes('409')) {
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

const renderFormatOptions = [
  { value: '1920x1080', label: '16:9' },
  { value: '1080x1920', label: '9:16' },
  { value: '1920x1440', label: '4:3' },
  { value: '1080x1440', label: '3:4' },
]
</script>

<template>
  <div class="bg-panel border-b border-[#333] px-4 py-3 flex flex-col gap-1.5">
    <h3 class="text-sm">Sync</h3>

    <!-- Mode toggle -->
    <div class="flex gap-4 items-center flex-wrap">
      <label class="text-sm cursor-pointer">
        <input type="radio" :checked="syncMode === 'duration'" @change="syncMode = 'duration'" class="mr-1"> Duration
      </label>
      <label class="text-sm cursor-pointer">
        <input type="radio" :checked="syncMode === 'reference'" @change="syncMode = 'reference'" class="mr-1"> Reference pair
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
      <span class="text-muted text-sm">{{ store.selectionCount }} of {{ store.filesWithTimestamp.length }} files selected</span>
    </div>

    <!-- Add to queue -->
    <button class="btn" :disabled="!canAddToQueue" @click="addToQueue">Add to queue</button>

    <!-- Queue -->
    <div class="bg-surface border border-[#333] p-1.5 text-sm max-h-[120px] overflow-y-auto">
      <div v-if="store.pendingStack.length === 0" class="text-muted italic">No pending offsets</div>
      <div v-for="(entry, idx) in store.pendingStack" :key="entry.id" class="flex justify-between py-0.5 px-1">
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
        <button class="text-error bg-transparent border-none cursor-pointer" @click="removeQueueItem(idx)">×</button>
      </div>
    </div>

    <!-- Action buttons -->
    <div class="flex gap-2 items-center">
      <button class="btn" :disabled="!canUpdateTimeline" @click="updateTimeline">Update timeline</button>
      <button class="btn" :disabled="!store.hasPendingOffsets" @click="clearQueue">Clear queue</button>
      <button class="btn" :disabled="!canApply" @click="openApplyModal">Apply</button>
      <button class="btn btn-primary" @click="openRenderModal">Render</button>
    </div>

    <!-- Apply Modal -->
    <Teleport to="body">
      <div v-if="showApplyModal" class="fixed inset-0 bg-black/60 flex items-center justify-center z-[100]">
        <div class="bg-panel border border-[#444] p-5 min-w-[480px] max-w-[80vw] max-h-[80vh] flex flex-col rounded">
          <h3 class="mb-3">Confirm apply</h3>
          <div class="flex-1 overflow-y-auto font-mono text-sm bg-surface border border-[#333] p-2">
            <div v-for="f in store.shiftedFiles" :key="f.path" class="py-0.5">
              {{ f.path.split('/').pop() }} {{ store.originalFilesByPath[f.path]?.timestamp || '(none)' }} → {{ f.timestamp }}
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
            <p class="text-muted text-sm mb-3">This will generate a stitched video from the current timeline. The process may take several minutes.</p>

            <div class="mb-2.5">
              <label class="block text-sm text-muted mb-1">Output path</label>
              <input v-model="renderOutput" class="input-field w-full" placeholder="/path/to/output.mp4">
            </div>

            <div class="mb-2.5">
              <label class="block text-sm text-muted mb-1">Aspect ratio</label>
              <div class="flex gap-2">
                <button v-for="fmt in renderFormatOptions" :key="fmt.value"
                  class="flex-1 py-2 bg-[#2a2a2a] border border-[#444] rounded text-sm text-muted cursor-pointer"
                  :class="{ 'bg-video-bar border-video-bar text-white': renderFormat === fmt.value }"
                  @click="renderFormat = fmt.value">
                  {{ fmt.label }}
                </button>
              </div>
              <div class="text-xs text-muted text-center mt-1.5">{{ renderFormat.replace('x', ' × ') }}</div>
            </div>

            <div class="flex items-center gap-2 mb-2.5">
              <label class="flex-1 text-sm text-muted">Draft quality</label>
              <input type="checkbox" v-model="renderDraft" class="cursor-pointer">
            </div>

            <div class="mb-2.5">
              <label class="block text-sm text-muted mb-1">Image duration (seconds)</label>
              <input type="number" v-model="renderImageDuration" step="0.1" min="0.1" class="input-field w-full">
            </div>

            <div class="mb-2.5">
              <label class="block text-sm text-muted mb-1">Margin (%)</label>
              <input type="number" v-model="renderMargin" step="1" min="0" class="input-field w-full">
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
