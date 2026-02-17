const BASE_URL = import.meta.env.VITE_API_URL || ''

async function request(url, options = {}) {
  const res = await fetch(`${BASE_URL}${url}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`API Error ${res.status}: ${text}`)
  }
  return res.json()
}

export async function searchFlights(params) {
  return request('/api/search', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

export async function exploreFlights(params, onProgress) {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '' && v !== false) qs.set(k, v)
  })
  if (params.direct_only === true) qs.set('direct_only', 'true')

  // Start async job
  const job = await request(`/api/explore?${qs.toString()}`, { method: 'POST' })
  if (!job.job_id) {
    // Fallback: direct response (no async)
    return job
  }

  // Poll for results
  const jobId = job.job_id
  const maxAttempts = 120 // 10 min max
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(r => setTimeout(r, 3000)) // 3s between polls
    if (onProgress) onProgress(i)
    const status = await request(`/api/explore/status/${jobId}`)
    if (status.status === 'done') return status
    if (status.status === 'error') throw new Error(status.error || 'Explore failed')
    if (status.status === 'not_found') throw new Error('Job expired')
  }
  throw new Error('Explore timed out')
}

export async function fetchLocations(query) {
  if (!query || query.length < 2) return { results: [] }
  return request(`/api/locations?query=${encodeURIComponent(query)}`)
}

export async function fetchStrategies() {
  return request('/api/strategies')
}
