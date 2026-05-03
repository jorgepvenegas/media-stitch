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
