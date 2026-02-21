<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { api } from '../api.js'

const props = defineProps({
  activeJobId: String,
})

const emit = defineEmits(['select'])

const jobs = ref([])
let timer = null

const load = async () => {
  try {
    const data = await api.listJobs({ limit: 50 })
    jobs.value = data.items
  } catch (e) {
    // silently ignore — network may not be up yet
  }
}

onMounted(() => {
  load()
  timer = setInterval(load, 5000)
})

onUnmounted(() => clearInterval(timer))

const badgeClass = (status) => `badge badge-${status}`

function formatDate(iso) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}
</script>

<template>
  <section class="history">
    <h2 class="section-title">History</h2>

    <p v-if="!jobs.length" class="empty">No jobs yet.</p>

    <ul class="job-list">
      <li
        v-for="j in jobs"
        :key="j.job_id"
        class="job-item"
        :class="{ 'job-item--active': j.job_id === activeJobId }"
        @click="emit('select', j.job_id)"
      >
        <div class="job-top">
          <span :class="badgeClass(j.status)">{{ j.status }}</span>
          <span class="job-date">{{ formatDate(j.created_at) }}</span>
        </div>
        <div class="job-meta">
          <template v-if="j.filenames && j.filenames.length">
            <span class="job-filename">{{ j.filenames[0] }}</span>
            <span v-if="j.filenames.length > 1" class="job-count">+{{ j.filenames.length - 1 }}</span>
          </template>
          <span v-else class="job-count">{{ j.image_count }} image{{ j.image_count !== 1 ? 's' : '' }}</span>
          <span v-if="j.notes" class="job-notes">· {{ j.notes }}</span>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.history {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
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
  flex-shrink: 0;
}

.empty {
  font-size: 13px;
  color: var(--color-muted);
  font-family: system-ui, sans-serif;
}

.job-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.job-item {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 10px 12px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.job-item:hover {
  border-color: var(--color-accent);
}

.job-item--active {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 2px rgba(74, 103, 65, 0.15);
}

.job-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.job-date {
  font-size: 11px;
  color: var(--color-muted);
  font-family: system-ui, sans-serif;
}

.job-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-family: system-ui, sans-serif;
}

.job-filename {
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 180px;
}

.job-count {
  color: var(--color-muted);
  flex-shrink: 0;
}

.job-notes {
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 160px;
}
</style>
