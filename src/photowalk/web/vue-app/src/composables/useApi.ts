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
