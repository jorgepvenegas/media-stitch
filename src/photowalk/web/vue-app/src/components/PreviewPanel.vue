<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAppStore } from '@/stores/appStore'

const store = useAppStore()
const videoRef = ref<HTMLVideoElement | null>(null)
const imageRef = ref<HTMLImageElement | null>(null)
const copied = ref(false)

const trimStart = computed(() => store.trimStart)
const trimEnd = computed(() => store.trimEnd)

const playbackTimestamp = computed(() => {
  if (!store.currentVideoFile || !store.currentVideoFile.timestamp) return null
  const ts = new Date(store.currentVideoFile.timestamp).getTime()
  const offset = (store.currentTime - (trimStart.value ?? 0)) * 1000
  return new Date(ts + offset)
})

const shouldShowVideo = computed(() => store.selectedFile?.type === 'video')
const shouldShowImage = computed(() => store.selectedFile?.type === 'photo')

const mediaUrl = computed(() => {
  if (!store.selectedFile) return ''
  return `/media/${store.selectedFile.path}`
})

function handleLoadedMetadata() {
  const video = videoRef.value
  if (!video) return
  // Seek to trim start if defined
  const s = trimStart.value
  if (s !== undefined) {
    video.currentTime = s
  }
}

function handleTimeUpdate() {
  const video = videoRef.value
  if (!video) return
  store.setPlaybackState(true, video.currentTime)
  // Enforce trim end — pause immediately when reached
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
  // Clamp seeking within trim bounds
  const s = trimStart.value
  const e = trimEnd.value
  if (s !== undefined && video.currentTime < s) video.currentTime = s
  if (e !== undefined && video.currentTime > e) video.currentTime = e
}

function handlePlay() { store.setPlaybackState(true, videoRef.value?.currentTime ?? 0) }
function handlePause() { store.setPlaybackState(false, videoRef.value?.currentTime ?? 0) }
function handleEnded() { store.setPlaybackState(false, videoRef.value?.currentTime ?? 0) }

function copyTimestamp() {
  if (!playbackTimestamp.value) return
  navigator.clipboard.writeText(playbackTimestamp.value.toISOString())
  copied.value = true
  setTimeout(() => { copied.value = false }, 1500)
}

function useRefAsCorrect() {
  if (!playbackTimestamp.value) return
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
        v-if="shouldShowVideo" ref="videoRef" :src="mediaUrl" controls
        class="max-w-full max-h-full object-contain"
        @timeupdate="handleTimeUpdate" @seeking="handleSeeking"
        @loadedmetadata="handleLoadedMetadata" @play="handlePlay"
        @pause="handlePause" @ended="handleEnded"
      />
      <img
        v-else-if="shouldShowImage" ref="imageRef" :src="mediaUrl"
        class="max-w-full max-h-full object-contain"
      />
      <div v-else class="text-muted text-xl">Select an item to preview</div>
    </div>

    <!-- Timestamp panel -->
    <div class="w-[220px] min-w-[220px] bg-panel border-l border-[#333] flex flex-col items-center justify-center p-4">
      <div class="text-center w-full">
        <div v-if="!store.selectedPath || store.currentVideoFile?.type !== 'video' || store.isPlaying" class="text-muted italic text-sm">
          {{ store.isPlaying ? 'Playing...' : 'Select a video to see timestamp' }}
        </div>
        <div v-else>
          <div class="text-[0.7rem] uppercase tracking-wide text-muted mb-1">Current timestamp</div>
          <hr class="border-[#333] my-2">
          <div class="text-base mb-1">{{ playbackTimestamp?.toISOString() ?? '' }}</div>
          <div class="text-sm text-muted font-mono mb-3">{{ playbackTimestamp?.toISOString() ?? '' }}</div>
          <button class="w-full btn mb-2" @click="copyTimestamp">{{ copied ? 'Copied!' : 'Copy ISO' }}</button>
          <button class="w-full btn btn-primary" @click="useRefAsCorrect">Use as correct</button>
        </div>
      </div>
    </div>
  </div>
</template>
