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
