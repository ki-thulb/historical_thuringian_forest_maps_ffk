<script setup>
import { computed } from 'vue'

const props = defineProps({
  job: Object,
})

const STAGE_LABELS = {
  border_removal: 'Removing borders',
  fold_detection: 'Detecting folds',
  fold_removal:   'Removing fold bands',
  stitching:      'Stitching tiles',
  georeferencing: 'Georeferencing',
  ocr:            'Extracting text',
}

const statusText = computed(() => {
  if (!props.job) return null
  const { status, stage, progress } = props.job
  if (status === 'pending') return 'Queued…'
  if (status === 'processing') return STAGE_LABELS[stage] ?? stage ?? 'Processing…'
  if (status === 'completed') return 'Completed'
  if (status === 'failed') return props.job.error?.message ?? 'Processing failed'
  if (status === 'cancelled') return 'Cancelled'
  return status
})

const pct = computed(() =>
  props.job ? Math.round((props.job.progress ?? 0) * 100) : 0
)

const badgeClass = computed(() => {
  const s = props.job?.status
  return s ? `badge badge-${s}` : 'badge'
})
</script>

<template>
  <div v-if="job" class="job-status">
    <div class="status-row">
      <span :class="badgeClass">{{ job.status }}</span>
      <span class="status-text">{{ statusText }}</span>
    </div>

    <div v-if="job.status === 'processing' || job.status === 'pending'" class="progress-track">
      <div
        class="progress-fill"
        :class="{ 'progress-fill--animated': job.status === 'pending' }"
        :style="{ width: job.status === 'pending' ? '8%' : pct + '%' }"
      />
    </div>
  </div>
</template>

<style scoped>
.job-status {
  padding: 10px 16px;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-text {
  font-size: 13px;
  font-family: system-ui, sans-serif;
  color: var(--color-muted);
}

.progress-track {
  height: 4px;
  background: var(--color-border);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--color-processing);
  border-radius: 2px;
  transition: width 0.4s ease;
}

.progress-fill--animated {
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.4; }
}
</style>
