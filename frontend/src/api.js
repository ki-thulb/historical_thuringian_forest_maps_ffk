const BASE = '/api/v1'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  async createJob(formData, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', `${BASE}/jobs`)

      if (onProgress) {
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
        })
      }

      xhr.addEventListener('load', () => {
        if (xhr.status === 202) {
          resolve(JSON.parse(xhr.responseText))
        } else {
          reject(new Error(xhr.responseText || `HTTP ${xhr.status}`))
        }
      })
      xhr.addEventListener('error', () => reject(new Error('Upload failed')))
      xhr.send(formData)
    })
  },

  getJob: (jobId) => request(`/jobs/${jobId}`),

  listJobs: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null))
    ).toString()
    return request(`/jobs${qs ? `?${qs}` : ''}`)
  },

  cancelJob: (jobId) => request(`/jobs/${jobId}/cancel`, { method: 'POST' }),

  deleteJob: async (jobId) => {
    const res = await fetch(`${BASE}/jobs/${jobId}`, { method: 'DELETE' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
  },

  overlayUrl: (jobId) => `${BASE}/jobs/${jobId}/overlay`,
  geojsonUrl: (jobId) => `${BASE}/jobs/${jobId}/geojson`,
}
