<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import L from 'leaflet'

const props = defineProps({
  job: Object,  // full job object; shows overlay when job.result is present
})

const mapContainer = ref(null)
const hasOverlay = ref(false)
const opacity = ref(60)
const visible = ref(true)
const showGeoJSON = ref(true)
const geojsonCount = ref(0)
const geojsonMeta = ref(null)
const geojsonFeatures = ref([])
const showPanel = ref(false)

let map = null
let overlay = null
let geojsonLayer = null

const CATEGORY_COLORS = {
  Ortsname:    '#2563eb',
  Gewaesser:   '#0891b2',
  Forstbestand:'#16a34a',
  Legende:     '#9333ea',
  Gemarkung:   '#d97706',
  Beschriftung:'#64748b',
  Sonstiges:   '#94a3b8',
}

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

async function loadGeoJSON(url) {
  if (geojsonLayer) { geojsonLayer.remove(); geojsonLayer = null }
  geojsonCount.value = 0
  geojsonMeta.value = null
  geojsonFeatures.value = []
  showPanel.value = false

  if (!url || !map) return

  const res = await fetch(url)
  if (!res.ok) return
  const data = await res.json()

  geojsonMeta.value = data.metadata ?? null
  geojsonFeatures.value = (data.features ?? []).filter(f => f.properties?.readable !== false)
  geojsonCount.value = geojsonFeatures.value.length

  // Render features that have actual geometry as map markers
  const withGeom = { ...data, features: (data.features ?? []).filter(f => f.geometry) }
  geojsonLayer = L.geoJSON(withGeom, {
    pointToLayer(feature, latlng) {
      return L.circleMarker(latlng, {
        radius: 6,
        fillColor: '#e84033',
        color: '#fff',
        weight: 1.5,
        opacity: 1,
        fillOpacity: 0.9,
      })
    },
    onEachFeature(feature, layer) {
      const p = feature.properties || {}
      const label = p.text || p.name || p.label
      if (label) layer.bindPopup(`<strong>${label}</strong>`)
    },
  })
  if (showGeoJSON.value) geojsonLayer.addTo(map)

  if (geojsonCount.value > 0) showPanel.value = true
}

watch(
  () => props.job,
  (job) => {
    if (!map) return

    // Clear existing layers
    if (overlay) { overlay.remove(); overlay = null; hasOverlay.value = false }
    if (geojsonLayer) { geojsonLayer.remove(); geojsonLayer = null; geojsonCount.value = 0 }

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

    loadGeoJSON(job.result.geojson_url)
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

    <!-- Feature list panel (left side) -->
    <transition name="slide">
      <div v-if="showPanel" class="feature-panel">
        <div class="panel-header">
          <div class="panel-meta" v-if="geojsonMeta">
            <div class="panel-title">{{ geojsonMeta.map_title }}</div>
            <div class="panel-sub">{{ geojsonMeta.map_date }} · {{ geojsonMeta.map_scale }}</div>
          </div>
          <button class="panel-close" @click="showPanel = false">✕</button>
        </div>
        <div class="panel-list">
          <div
            v-for="(f, i) in geojsonFeatures"
            :key="i"
            class="feature-row"
          >
            <span
              class="feature-badge"
              :style="{ background: CATEGORY_COLORS[f.properties.category] ?? '#94a3b8' }"
            >{{ f.properties.category }}</span>
            <span class="feature-text">{{ f.properties.text }}</span>
          </div>
        </div>
      </div>
    </transition>

    <!-- Map controls (right side) -->
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

        <label class="control-row control-row--toggle">
          <input v-model="showPanel" type="checkbox" class="toggle-checkbox" />
          <span class="control-label">Show texts</span>
          <span class="control-value">{{ geojsonCount }}</span>
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

/* Feature panel */
.feature-panel {
  position: absolute;
  top: 12px;
  left: 12px;
  bottom: 12px;
  width: 260px;
  z-index: 1000;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.14);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 10px 12px 8px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
  gap: 8px;
}

.panel-meta {
  flex: 1;
  min-width: 0;
}

.panel-title {
  font-size: 11px;
  font-weight: 600;
  font-family: system-ui, sans-serif;
  color: var(--color-text);
  line-height: 1.4;
  word-break: break-word;
}

.panel-sub {
  font-size: 10px;
  color: var(--color-muted);
  font-family: system-ui, sans-serif;
  margin-top: 2px;
}

.panel-close {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 11px;
  color: var(--color-muted);
  padding: 0 2px;
  flex-shrink: 0;
  line-height: 1;
}

.panel-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px 0;
}

.feature-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 4px 12px;
  font-family: system-ui, sans-serif;
}

.feature-row:hover {
  background: rgba(0,0,0,0.03);
}

.feature-badge {
  flex-shrink: 0;
  font-size: 9px;
  font-weight: 600;
  color: #fff;
  padding: 1px 5px;
  border-radius: 3px;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.feature-text {
  font-size: 11px;
  color: var(--color-text);
  line-height: 1.4;
  word-break: break-word;
}

.slide-enter-active, .slide-leave-active { transition: opacity 0.2s, transform 0.2s; }
.slide-enter-from, .slide-leave-to { opacity: 0; transform: translateX(-8px); }
</style>
