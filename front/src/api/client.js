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

export async function exploreFlights(params) {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '' && v !== false) qs.set(k, v)
  })
  // direct_only should be sent as true when enabled
  if (params.direct_only === true) qs.set('direct_only', 'true')
  return request(`/api/explore?${qs.toString()}`)
}

export async function fetchLocations(query) {
  if (!query || query.length < 2) return { results: [] }
  return request(`/api/locations?query=${encodeURIComponent(query)}`)
}

export async function fetchStrategies() {
  return request('/api/strategies')
}
