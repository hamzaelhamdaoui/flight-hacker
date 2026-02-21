// Admin API client for RataTrip Admin Panel
const API_BASE = import.meta.env.VITE_API_URL || ''

class AdminApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'AdminApiError'
    this.status = status
  }
}

const handleResponse = async (response) => {
  if (!response.ok) {
    let message = `HTTP ${response.status}: ${response.statusText}`
    try {
      const errorData = await response.json()
      message = errorData.detail || errorData.message || message
    } catch (e) {
      // If can't parse error response, use default message
    }
    throw new AdminApiError(message, response.status)
  }
  return response.json()
}

const buildQueryString = (params) => {
  const filtered = Object.entries(params).filter(([_, value]) => 
    value !== null && value !== undefined && value !== ''
  )
  return new URLSearchParams(filtered).toString()
}

export const adminApi = {
  // Statistics
  async getStats() {
    const response = await fetch(`${API_BASE}/api/admin/stats`)
    return handleResponse(response)
  },

  // Deals endpoints
  async getDeals(filters = {}) {
    const queryString = buildQueryString(filters)
    const url = `${API_BASE}/api/admin/deals${queryString ? `?${queryString}` : ''}`
    const response = await fetch(url)
    return handleResponse(response)
  },

  async deleteDeal(dealId) {
    const response = await fetch(`${API_BASE}/api/admin/deals/${dealId}`, {
      method: 'DELETE'
    })
    return handleResponse(response)
  },

  async updateDeal(dealId, data) {
    const response = await fetch(`${API_BASE}/api/admin/deals/${dealId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
    return handleResponse(response)
  },

  // Queue endpoints
  async getQueue(filters = {}) {
    const queryString = buildQueryString(filters)
    const url = `${API_BASE}/api/admin/queue${queryString ? `?${queryString}` : ''}`
    const response = await fetch(url)
    return handleResponse(response)
  },

  async addToQueue(data) {
    const response = await fetch(`${API_BASE}/api/admin/queue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
    return handleResponse(response)
  },

  async updateQueueItem(queueId, data) {
    const response = await fetch(`${API_BASE}/api/admin/queue/${queueId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
    return handleResponse(response)
  },

  async deleteQueueItem(queueId) {
    const response = await fetch(`${API_BASE}/api/admin/queue/${queueId}`, {
      method: 'DELETE'
    })
    return handleResponse(response)
  },

  async reorderQueue(items) {
    const response = await fetch(`${API_BASE}/api/admin/queue/reorder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items })
    })
    return handleResponse(response)
  },

  // Published endpoints
  async getPublished(filters = {}) {
    const queryString = buildQueryString(filters)
    const url = `${API_BASE}/api/admin/published${queryString ? `?${queryString}` : ''}`
    const response = await fetch(url)
    return handleResponse(response)
  },

  async updatePublished(publishedId, data) {
    const response = await fetch(`${API_BASE}/api/admin/published/${publishedId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
    return handleResponse(response)
  },

  async deletePublished(publishedId) {
    const response = await fetch(`${API_BASE}/api/admin/published/${publishedId}`, {
      method: 'DELETE'
    })
    return handleResponse(response)
  },
}