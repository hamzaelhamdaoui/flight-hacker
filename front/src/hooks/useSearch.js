import { useState, useCallback } from 'react'
import { searchFlights, exploreFlights } from '../api/client'

export function useSearch() {
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [mode, setMode] = useState(null) // 'search' or 'explore'
  const [progress, setProgress] = useState(0)
  const [searchStatus, setSearchStatus] = useState('')

  const search = useCallback(async (params) => {
    const isExplore = params._mode === 'explore'
    const cleanParams = { ...params }
    delete cleanParams._mode

    setMode(isExplore ? 'explore' : 'search')
    setLoading(true)
    setError(null)
    setResults(null)
    setProgress(0)
    setSearchStatus('')

    try {
      if (isExplore) {
        const data = await exploreFlights(cleanParams, (progressValue, partialResults, status) => {
          if (typeof progressValue === 'number' && partialResults && status) {
            setProgress(progressValue)
            setSearchStatus(`${status.destinations_searched}/${status.destinations_total} destinations${status.current_destination ? ` — searching ${status.current_destination}...` : '...'}`)
            if (partialResults.length > 0) {
              setResults({
                results: partialResults,
                total: partialResults.length,
                origin: cleanParams.origin || '',
              })
            }
          } else {
            setProgress(Math.min(progressValue * 5, 95))
          }
        })
        setResults(data)
        setProgress(100)
      } else {
        const data = await searchFlights(cleanParams)
        setResults(data)
      }
    } catch (err) {
      setError(err.message || 'Search failed')
    } finally {
      setLoading(false)
    }
  }, [])

  const clearResults = useCallback(() => {
    setResults(null)
    setError(null)
    setMode(null)
    setProgress(0)
    setSearchStatus('')
  }, [])

  return { results, loading, error, search, clearResults, mode, progress, searchStatus }
}

// Keep for backward compat if needed
export function useExplore() {
  const { results, loading, error, search, clearResults, progress, searchStatus } = useSearch()
  const explore = useCallback((params) => search({ ...params, _mode: 'explore' }), [search])
  return { results, loading, error, explore, progress, searchStatus }
}
