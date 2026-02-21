<script setup>
import { ref } from 'vue'
import { api } from '../api.js'

const emit = defineEmits(['job-created'])

const dragOver = ref(false)
const files = ref([])
const tilesX = ref('')
const tilesY = ref('')
const notes = ref('')
const MAX_TILES = 6
const hoverX = ref(0)
const hoverY = ref(0)

const setTiles = (col, row) => {
  tilesX.value = col
  tilesY.value = row
}
const clearTiles = () => { tilesX.value = ''; tilesY.value = '' }
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadError = ref(null)
const fileInput = ref(null)

const ACCEPTED = ['image/jpeg', 'image/png', 'image/tiff', 'image/tif']

function addFiles(incoming) {
  const valid = Array.from(incoming).filter(
    (f) => !f.type || ACCEPTED.includes(f.type) || f.name.match(/\.(jpe?g|png|tiff?)$/i)
  )
  files.value = [...files.value, ...valid]
}

const onDrop = (e) => {
  dragOver.value = false
  addFiles(e.dataTransfer.files)
}

const onFileInput = (e) => addFiles(e.target.files)

const removeFile = (i) => {
  files.value = files.value.filter((_, idx) => idx !== i)
}

const triggerInput = () => fileInput.value?.click()

const submit = async () => {
  if (!files.value.length || uploading.value) return

  uploading.value = true
  uploadProgress.value = 0
  uploadError.value = null

  try {
    const fd = new FormData()
    files.value.forEach((f) => fd.append('images', f))
    if (tilesX.value) fd.append('tiles_x', tilesX.value)
    if (tilesY.value) fd.append('tiles_y', tilesY.value)
    if (notes.value.trim()) fd.append('notes', notes.value.trim())

    const job = await api.createJob(fd, (p) => { uploadProgress.value = p })

    files.value = []
    tilesX.value = ''
    tilesY.value = ''
    notes.value = ''
    hoverX.value = 0
    hoverY.value = 0
    emit('job-created', job.job_id)
  } catch (e) {
    uploadError.value = e.message
  } finally {
    uploading.value = false
    uploadProgress.value = 0
  }
}
</script>

<template>
  <section class="upload-zone">
    <h2 class="section-title">New job</h2>

    <!-- Drop area -->
    <div
      class="drop-area"
      :class="{ 'drop-area--over': dragOver }"
      @dragover.prevent="dragOver = true"
      @dragleave.prevent="dragOver = false"
      @drop.prevent="onDrop"
      @click="triggerInput"
    >
      <svg class="drop-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>
        <polyline points="16 8 12 4 8 8"/>
        <line x1="12" y1="4" x2="12" y2="16"/>
      </svg>
      <span v-if="!files.length">Drop images here or click to select</span>
      <span v-else>{{ files.length }} file{{ files.length > 1 ? 's' : '' }} selected — click to add more</span>
    </div>

    <input
      ref="fileInput"
      type="file"
      accept="image/*"
      multiple
      class="hidden-input"
      @change="onFileInput"
    />

    <!-- File list -->
    <ul v-if="files.length" class="file-list">
      <li v-for="(f, i) in files" :key="i" class="file-item">
        <span class="file-name">{{ f.name }}</span>
        <span class="file-size">({{ (f.size / 1024 / 1024).toFixed(1) }} MB)</span>
        <button class="file-remove" @click.stop="removeFile(i)" title="Remove">✕</button>
      </li>
    </ul>

    <!-- Tile grid picker -->
    <div class="tile-picker">
      <div class="tile-picker-header">
        <span class="tile-label">Tile grid</span>
        <button
          class="tile-auto-btn"
          :class="{ 'tile-auto-btn--active': !tilesX && !tilesY }"
          @click.stop="clearTiles"
        >auto</button>
        <span v-if="tilesX && tilesY" class="tile-selection">{{ tilesX }} × {{ tilesY }}</span>
      </div>

      <div class="tile-grid" @mouseleave="hoverX = 0; hoverY = 0">
        <div v-for="row in MAX_TILES" :key="row" class="tile-row">
          <div
            v-for="col in MAX_TILES"
            :key="col"
            class="tile-cell"
            :class="{
              'tile-cell--active':  col <= (tilesX || 0) && row <= (tilesY || 0),
              'tile-cell--preview': col <= (hoverX || 0) && row <= (hoverY || 0),
            }"
            @mouseenter="hoverX = col; hoverY = row"
            @click="setTiles(col, row)"
          />
        </div>
      </div>
    </div>

    <label class="notes-label">
      Notes
      <textarea v-model="notes" rows="2" placeholder="Map identifier, epoch, remarks…" />
    </label>

    <!-- Upload progress -->
    <div v-if="uploading" class="progress-bar-wrap">
      <div class="progress-bar" :style="{ width: uploadProgress + '%' }" />
      <span class="progress-label">Uploading… {{ uploadProgress }}%</span>
    </div>

    <p v-if="uploadError" class="upload-error">{{ uploadError }}</p>

    <button class="btn-submit" :disabled="!files.length || uploading" @click="submit">
      {{ uploading ? 'Uploading…' : 'Process maps' }}
    </button>
  </section>
</template>

<style scoped>
.upload-zone {
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-title {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-muted);
  font-family: system-ui, sans-serif;
  font-weight: 600;
}

.drop-area {
  border: 2px dashed var(--color-border);
  border-radius: 6px;
  padding: 20px 12px;
  text-align: center;
  cursor: pointer;
  color: var(--color-muted);
  font-size: 13px;
  transition: border-color 0.15s, background 0.15s;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.drop-area:hover,
.drop-area--over {
  border-color: var(--color-accent);
  background: #f0f5ef;
  color: var(--color-accent);
}

.drop-icon {
  width: 28px;
  height: 28px;
  opacity: 0.5;
}

.hidden-input {
  display: none;
}

.file-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  background: var(--color-bg);
  border-radius: 4px;
  padding: 4px 8px;
}

.file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  color: var(--color-muted);
  flex-shrink: 0;
}

.file-remove {
  border: none;
  background: none;
  color: var(--color-muted);
  padding: 0 2px;
  line-height: 1;
  font-size: 11px;
}
.file-remove:hover { color: var(--color-failed); }

.tile-picker {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tile-picker-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-family: system-ui, sans-serif;
  color: var(--color-muted);
}

.tile-selection {
  font-weight: 600;
  color: var(--color-text);
  min-width: 42px;
}

.tile-auto-btn {
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  color: var(--color-muted);
  font-size: 11px;
  font-family: system-ui, sans-serif;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  cursor: pointer;
  padding: 2px 7px;
  border-radius: 10px;
  transition: background 0.12s, color 0.12s, border-color 0.12s;
}
.tile-auto-btn:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}
.tile-auto-btn--active {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: white;
}
.tile-auto-btn--active:hover {
  background: var(--color-accent-hover);
  border-color: var(--color-accent-hover);
  color: white;
}

.tile-grid {
  display: flex;
  flex-direction: column;
  gap: 3px;
  align-self: flex-start;
}

.tile-row { display: flex; gap: 3px; }

.tile-cell {
  width: 18px;
  height: 18px;
  border-radius: 3px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  cursor: pointer;
  transition: background 0.08s, border-color 0.08s;
}

.tile-cell--preview {
  background: #d4e6d0;
  border-color: var(--color-accent);
}

.tile-cell--active {
  background: var(--color-accent);
  border-color: var(--color-accent-hover);
}

.notes-label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--color-muted);
  font-family: system-ui, sans-serif;
}

.notes-label textarea {
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 5px 8px;
  background: var(--color-surface);
  color: var(--color-text);
  resize: vertical;
}

.notes-label textarea:focus {
  outline: none;
  border-color: var(--color-accent);
}

.progress-bar-wrap {
  position: relative;
  height: 20px;
  background: var(--color-bg);
  border-radius: 4px;
  border: 1px solid var(--color-border);
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: var(--color-accent);
  transition: width 0.2s ease;
}

.progress-label {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-family: system-ui, sans-serif;
  color: var(--color-text);
}

.upload-error {
  font-size: 12px;
  color: var(--color-failed);
  font-family: system-ui, sans-serif;
}

.btn-submit {
  background: var(--color-accent);
  color: white;
  border: none;
  border-radius: 5px;
  padding: 9px 14px;
  font-size: 13px;
  font-weight: 600;
  font-family: system-ui, sans-serif;
  letter-spacing: 0.02em;
  transition: background 0.15s;
}
.btn-submit:hover:not(:disabled) { background: var(--color-accent-hover); }
.btn-submit:disabled { opacity: 0.45; cursor: not-allowed; }
</style>
