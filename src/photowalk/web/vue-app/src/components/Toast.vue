<script setup lang="ts">
import { useToast } from '@/composables/useToast'
const { toast, dismiss } = useToast()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="toast"
      class="fixed bottom-5 right-5 z-[101] max-w-[400px] rounded border px-4 py-3"
      :class="toast.isError ? 'bg-panel border-error' : 'bg-panel border-[#444]'"
    >
      <div class="flex items-start justify-between gap-2">
        <pre class="whitespace-pre-wrap text-sm text-text">{{ toast.message }}</pre>
        <button v-if="toast.sticky" class="text-muted bg-transparent border-none cursor-pointer text-lg" @click="dismiss">×</button>
      </div>
    </div>
  </Teleport>
</template>
