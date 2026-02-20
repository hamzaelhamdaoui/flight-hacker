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
  // Start async job
  const job = await request('/api/search', {
    method: 'POST',
    body: JSON.stringify(params),
  })
  if (!job.job_id) return job // direct response fallback

  // Poll for results
  const jobId = job.job_id
  const startTime = Date.now()
  const maxMs = 5 * 60 * 1000 // 5 min max

  while ((Date.now() - startTime) < maxMs) {
    await new Promise(r => setTimeout(r, 3000))
    let status
    try {
      status = await request(`/api/search/status/${jobId}`)
    } catch { continue }
    if (status.status === 'done') return status
    if (status.status === 'error') throw new Error(status.error || 'Search failed')
    if (status.status === 'not_found') throw new Error('Job expired or not found')
  }
  throw new Error('Search timed out')
}

export async function exploreFlights(params, onProgress) {
  // Start async job with POST request
  const payload = { ...params }
  // months is already an array, pass as-is
  const job = await request('/api/explore', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  if (!job.job_id) {
    // Fallback: direct response (no async)
    return job
  }

  // Poll for results — adaptive interval: 3s for first 2 min, then 5s
  const jobId = job.job_id
  const maxMinutes = 180 // 3 hours max (large multi-continent searches)
  const startTime = Date.now()
  
  while ((Date.now() - startTime) < maxMinutes * 60 * 1000) {
    const elapsed = (Date.now() - startTime) / 1000
    const interval = elapsed < 120 ? 3000 : 5000 // faster at start, slower later
    await new Promise(r => setTimeout(r, interval))
    
    let status
    try {
      status = await request(`/api/explore/status/${jobId}`)
    } catch (err) {
      // Network hiccup — retry silently
      continue
    }
    
    // Call onProgress with partial results if available
    if (onProgress && status.status === 'running') {
      onProgress(status.progress || 0, status.results || [], {
        destinations_searched: status.destinations_searched || 0,
        destinations_total: status.destinations_total || 0,
        current_destination: status.current_destination || '',
      })
    }
    
    if (status.status === 'done') return status
    if (status.status === 'error') throw new Error(status.error || 'Explore failed')
    if (status.status === 'not_found') throw new Error('Job expired or not found')
  }
  throw new Error('Explore timed out after ' + maxMinutes + ' minutes')
}

export async function fetchLocations(query) {
  if (!query || query.length < 2) return { results: [] }
  return request(`/api/locations?query=${encodeURIComponent(query)}`)
}

export async function fetchStrategies() {
  return request('/api/strategies')
}
