<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import L from 'leaflet'

const props = defineProps({
  job: Object,  // full job object; shows overlay when job.result is present
})

const mapContainer = ref(null)
const hasOverlay = ref(false)
const opacity = ref(80)
const visible = ref(true)

let map = null
let overlay = null

onMounted(() => {
  map = L.map(mapContainer.value, { zoomControl: true }).setView([50.98, 11.57], 10)

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  }).addTo(map)
})

onUnmounted(() => {
  if (map) { map.remove(); map = null }
})

watch(
  () => props.job,
  (job) => {
    if (!map) return

    // Clear any existing overlay
    if (overlay) {
      overlay.remove()
      overlay = null
      hasOverlay.value = false
    }

    if (!job?.result) return

    const b = job.result.bounds
    const bounds = [[b.south, b.west], [b.north, b.east]]

    overlay = L.imageOverlay(job.result.overlay_url, bounds, {
      opacity: opacity.value / 100,
      interactive: false,
    })

    if (visible.value) overlay.addTo(map)
    hasOverlay.value = true
    map.fitBounds(bounds, { padding: [30, 30] })
  },
  { deep: true }
)

watch(opacity, (val) => {
  if (overlay) overlay.setOpacity(val / 100)
})

watch(visible, (val) => {
  if (!overlay || !map) return
  if (val) overlay.addTo(map)
  else overlay.remove()
})
</script>

<template>
  <div class="map-wrapper">
    <div ref="mapContainer" class="map" />

    <transition name="fade">
      <div v-if="hasOverlay" class="map-controls">
        <label class="control-row">
          <span class="control-label">Opacity</span>
          <input
            v-model.number="opacity"
            type="range"
            min="0"
            max="100"
            class="opacity-slider"
          />
          <span class="control-value">{{ opacity }}%</span>
        </label>

        <label class="control-row control-row--toggle">
          <input v-model="visible" type="checkbox" class="toggle-checkbox" />
          <span class="control-label">Show overlay</span>
        </label>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.map-wrapper {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.map {
  width: 100%;
  height: 100%;
}

.map-controls {
  position: absolute;
  bottom: 24px;
  right: 12px;
  z-index: 1000;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  backdrop-filter: blur(4px);
  box-shadow: 0 2px 8px rgba(0,0,0,0.12);
  min-width: 200px;
}

.control-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-family: system-ui, sans-serif;
  color: var(--color-text);
  cursor: pointer;
}

.control-label {
  flex-shrink: 0;
  color: var(--color-muted);
  width: 52px;
}

.opacity-slider {
  flex: 1;
  accent-color: var(--color-accent);
  cursor: pointer;
}

.control-value {
  width: 32px;
  text-align: right;
  color: var(--color-muted);
}

.control-row--toggle {
  gap: 8px;
}

.toggle-checkbox {
  accent-color: var(--color-accent);
  cursor: pointer;
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
