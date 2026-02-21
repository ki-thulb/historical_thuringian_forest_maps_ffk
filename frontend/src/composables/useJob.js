import { ref, watch, onUnmounted } from 'vue'
import { api } from '../api.js'

const TERMINAL = new Set(['completed', 'failed', 'cancelled'])
const POLL_INTERVAL_MS = 4000

export function useJob(jobIdRef) {
  const job = ref(null)
  const error = ref(null)
  let timer = null

  const stopPolling = () => {
    if (timer) { clearInterval(timer); timer = null }
  }

  const poll = async (id) => {
    try {
      const data = await api.getJob(id)
      job.value = data
      error.value = null
      if (TERMINAL.has(data.status)) stopPolling()
    } catch (e) {
      error.value = e.message
    }
  }

  const startPolling = (id) => {
    stopPolling()
    if (!id) { job.value = null; error.value = null; return }
    poll(id)
    timer = setInterval(() => poll(id), POLL_INTERVAL_MS)
  }

  watch(jobIdRef, (id) => startPolling(id), { immediate: true })
  onUnmounted(stopPolling)

  return { job, error }
}
