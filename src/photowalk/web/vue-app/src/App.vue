<script setup lang="ts">
import PreviewPanel from './components/PreviewPanel.vue'
import SyncPanel from './components/SyncPanel.vue'
import TimelinePanel from './components/TimelinePanel.vue'
import Toast from './components/Toast.vue'
</script>

<template>
  <div class="flex flex-col h-screen bg-app-bg text-text overflow-hidden">
    <PreviewPanel />
    <SyncPanel />
    <TimelinePanel />
    <Toast />
  </div>
</template>
