<script setup>
import { ref } from 'vue'
import { useJob } from './composables/useJob.js'
import UploadZone from './components/UploadZone.vue'
import JobStatus from './components/JobStatus.vue'
import MapView from './components/MapView.vue'
import JobHistory from './components/JobHistory.vue'

const activeJobId = ref(null)
const { job: activeJob } = useJob(activeJobId)

const onJobCreated = (jobId) => {
  activeJobId.value = jobId
}

const selectJob = (jobId) => {
  activeJobId.value = jobId
}
</script>

<template>
  <div class="app-layout">
    <!-- Sidebar -->
    <aside class="sidebar">
      <header class="app-header">
        <h1 class="app-title">Hack the Heritage</h1>
        <p class="app-subtitle">Historical Thuringian Forest Maps</p>
      </header>

      <UploadZone @job-created="onJobCreated" />
      <JobHistory :active-job-id="activeJobId" @select="selectJob" />
    </aside>

    <!-- Main area -->
    <main class="main">
      <JobStatus v-if="activeJob" :job="activeJob" />
      <MapView :job="activeJob" />
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  width: var(--sidebar-width);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid var(--color-border);
  background: var(--color-surface);
}

.app-header {
  padding: 16px 16px 12px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.app-title {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--color-text);
}

.app-subtitle {
  font-size: 11px;
  color: var(--color-muted);
  font-family: system-ui, sans-serif;
  margin-top: 2px;
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-bg);
  min-width: 0;
}
</style>
