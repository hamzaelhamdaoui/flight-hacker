import { useState, useCallback } from 'react'
import { searchFlights, exploreFlights } from '../api/client'

export function useSearch() {
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const search = useCallback(async (params) => {
    setLoading(true)
    setError(null)
    setResults(null)
    try {
      const data = await searchFlights(params)
      setResults(data)
    } catch (err) {
      setError(err.message || 'Search failed')
    } finally {
      setLoading(false)
    }
  }, [])

  const clearResults = useCallback(() => {
    setResults(null)
    setError(null)
  }, [])

  return { results, loading, error, search, clearResults }
}

export function useExplore() {
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [pollCount, setPollCount] = useState(0)

  const explore = useCallback(async (params) => {
    setLoading(true)
    setError(null)
    setResults(null)
    setPollCount(0)
    try {
      const data = await exploreFlights(params, (count) => {
        setPollCount(count + 1)
      })
      setResults(data)
    } catch (err) {
      setError(err.message || 'Explore failed')
    } finally {
      setLoading(false)
    }
  }, [])

  return { results, loading, error, explore, pollCount }
}
