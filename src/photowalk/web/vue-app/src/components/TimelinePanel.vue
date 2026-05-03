<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useAppStore } from "@/stores/appStore";
import { useTimeline } from "@/composables/useTimeline";
import type { TimelineEntry, TimelinePosition } from "@/types";

const CHAR_WIDTH = 7; // ~7px per char at 11px font
const TEXT_PADDING = 8; // left + right padding inside the block

const store = useAppStore();
const tl = useTimeline();

const imageDuration = ref(3.5);
const timelineScale = ref(50);
const svgContainer = ref<HTMLDivElement | null>(null);
const containerWidth = ref(1000);

const positions = computed(() =>
  tl.computeLayout(
    store.timelineEntries,
    imageDuration.value,
    timelineScale.value,
  ),
);

const svgWidth = computed(() =>
  tl.computeSvgWidth(positions.value, containerWidth.value),
);

const axisTicks = computed(() =>
  tl.formatAxisTicks(
    positions.value,
    timelineScale.value,
    containerWidth.value,
  ),
);

function basename(path: string): string {
  return path.split("/").pop() || "";
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function entryLabel(entry: TimelineEntry): string {
  let name = basename(entry.source_path);
  if (
    entry.kind === "video_segment" &&
    entry.trim_start != null &&
    entry.trim_end != null
  ) {
    name = `${name} [${formatTime(entry.trim_start)}–${formatTime(entry.trim_end)}]`;
  }
  return name;
}

function selectTimelineBar(entry: TimelineEntry) {
  const isCurrentlySelected = store.selection.has(entry.source_path);
  store.toggleSelection(entry.source_path, !isCurrentlySelected);
  store.selectFile(
    entry.source_path,
    "timeline",
    entry.trim_start,
    entry.trim_end,
  );
  store.selectedTimelineEntry = entry;
}

function onImageDurationChange() {
  let val = parseFloat(String(imageDuration.value));
  if (Number.isNaN(val) || val < 0.1) val = 0.1;
  imageDuration.value = val;
  store.timelineSettings.image_duration = val;
}

function zoomIn() {
  timelineScale.value = Math.min(500, timelineScale.value * 1.2);
}
function zoomOut() {
  timelineScale.value = Math.max(5, timelineScale.value / 1.2);
}

const zoomPct = computed(
  () => Math.round((timelineScale.value / 50) * 100) + "%",
);

let ro: ResizeObserver | null = null;

// ─── Tooltip ───
const tooltipVisible = ref(false);
const tooltipX = ref(0);
const tooltipY = ref(0);
const tooltipText = ref("");
let tooltipTimer: ReturnType<typeof setTimeout> | null = null;

function showTooltip(px: number, py: number, text: string) {
  if (tooltipTimer) clearTimeout(tooltipTimer);
  tooltipTimer = setTimeout(() => {
    tooltipX.value = px;
    tooltipY.value = py;
    tooltipText.value = text;
    tooltipVisible.value = true;
  }, 250);
}

function hideTooltip() {
  if (tooltipTimer) clearTimeout(tooltipTimer);
  tooltipVisible.value = false;
}

function getTruncatedLabel(pos: TimelinePosition): string {
  const fullLabel = entryLabel(pos.entry);
  const availableWidth = pos.width - TEXT_PADDING;
  // Apply 30-char limit first
  const charLimited = fullLabel.length > 30 ? fullLabel.slice(0, 28) + "\u2026" : fullLabel;
  // Then apply pixel-based truncation
  if (charLimited.length * CHAR_WIDTH <= availableWidth) return charLimited;
  const maxChars = Math.max(3, Math.floor((availableWidth - CHAR_WIDTH * 3) / CHAR_WIDTH));
  return charLimited.slice(0, maxChars) + "\u2026";
}

onMounted(() => {
  imageDuration.value = store.timelineSettings.image_duration;
  if (svgContainer.value) {
    containerWidth.value = svgContainer.value.clientWidth;
    ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        containerWidth.value = entry.contentRect.width;
      }
    });
    ro.observe(svgContainer.value);
  }
  store.loadInitial();
});

onUnmounted(() => {
  if (ro) ro.disconnect();
});
</script>

<template>
  <div class="flex flex-col" id="timeline-panel">
    <div class="flex items-center justify-between gap-3 px-2 py-1">
      <h3 class="text-sm m-0">Timeline</h3>
      <div class="flex items-center gap-1.5 text-sm text-[#ccc]">
        <label>Photo duration:</label>
        <input
          type="number"
          v-model.number="imageDuration"
          step="0.1"
          min="0.1"
          class="w-14 px-1.5 py-0.5 text-sm bg-[#2a2a2a] border border-[#444] rounded text-right focus:border-blue-400 focus:outline-none"
          @change="onImageDurationChange"
        />
        <span>s</span>
      </div>
      <div class="flex items-center gap-1.5 text-sm text-[#ccc]">
        <button
          class="bg-[#2a2a2a] border border-[#444] rounded cursor-pointer px-2 min-w-[28px] hover:bg-[#3a3a3a]"
          @click="zoomOut"
        >
          −
        </button>
        <span class="min-w-[42px] text-center">{{ zoomPct }}</span>
        <button
          class="bg-[#2a2a2a] border border-[#444] rounded cursor-pointer px-2 min-w-[28px] hover:bg-[#3a3a3a]"
          @click="zoomIn"
        >
          +
        </button>
      </div>
    </div>

    <!-- Timeline SVG -->
    <div ref="svgContainer" class="overflow-x-auto overflow-y-hidden relative">
      <svg :width="svgWidth" :height="tl.BAR_HEIGHT + tl.PADDING * 2">
        <template v-for="pos in positions" :key="pos.entry.source_path">
          <rect
            :x="pos.x"
            :y="tl.PADDING"
            :width="pos.width"
            :height="tl.BAR_HEIGHT"
            rx="3"
            :class="[
              'cursor-pointer',
              pos.entry.kind === 'image' ? 'fill-image-bar' : 'fill-video-bar',
              store.selectedPath === pos.entry.source_path
                ? store.selection.has(pos.entry.source_path)
                  ? 'stroke-yellow-400 stroke-[3]'
                  : 'stroke-yellow-400 stroke-2'
                : store.selection.has(pos.entry.source_path)
                  ? 'stroke-white stroke-[4]'
                  : 'stroke-white stroke-1',
            ]"
            @click="selectTimelineBar(pos.entry)"
            @mouseenter="(e) => showTooltip(e.clientX, e.clientY, entryLabel(pos.entry))"
            @mouseleave="hideTooltip"
          />
          <text
            v-if="pos.width > 40"
            :x="pos.x + 4"
            :y="tl.PADDING + tl.BAR_HEIGHT / 2"
            class="fill-white text-[11px] pointer-events-none"
            dominant-baseline="middle"
          >
            {{ getTruncatedLabel(pos) }}
          </text>
        </template>
        <!-- Axis ticks below SVG -->
      </svg>
    </div>

    <!-- Tooltip overlay -->
    <div
      v-if="tooltipVisible"
      class="fixed z-50 pointer-events-none bg-surface border border-[#555] text-white text-xs px-2 py-1 rounded shadow-lg whitespace-nowrap"
      :style="{ left: (tooltipX + 12) + 'px', top: (tooltipY + 12) + 'px' }"
    >
      {{ tooltipText }}
    </div>

    <!-- Axis -->
    <div class="h-[30px] border-t border-[#333] bg-panel relative">
      <div
        v-for="tick in axisTicks"
        :key="tick.seconds"
        class="absolute top-0 text-[11px] text-muted pl-1 border-l border-[#444] h-full whitespace-nowrap"
        :style="{ left: tick.x + 'px' }"
      >
        {{ tick.label }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.fill-video-bar {
  fill: #4a90d9;
}
.fill-image-bar {
  fill: #5cb85c;
}
</style>
