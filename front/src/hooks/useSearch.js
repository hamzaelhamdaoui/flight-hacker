import { useState, useCallback } from 'react'
import { searchFlights, exploreFlights } from '../api/client'

export function useSearch() {
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [mode, setMode] = useState(null) // 'search' or 'explore'
  const [progress, setProgress] = useState(0)
  const [searchStatus, setSearchStatus] = useState('')
  const [currentStrategy, setCurrentStrategy] = useState('')

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
    setCurrentStrategy('')

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
        // Search mode — streaming with strategy progress
        const data = await searchFlights(cleanParams, (status) => {
          const { current_strategy, strategies_done, strategies_total, progress: prog, results: partialResults, total, cheapest, strategies_used } = status
          setProgress(prog || 0)
          setCurrentStrategy(current_strategy || '')
          setSearchStatus(`${strategies_done}/${strategies_total} strategies${current_strategy ? ` — running ${current_strategy}...` : ''}`)
          if (partialResults && partialResults.length > 0) {
            setResults({
              results: partialResults,
              total,
              cheapest,
              strategies_used: strategies_used || [],
            })
          }
        })
        setResults(data)
        setProgress(100)
        setCurrentStrategy('')
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
    setCurrentStrategy('')
  }, [])

  return { results, loading, error, search, clearResults, mode, progress, searchStatus, currentStrategy }
}

export function useExplore() {
  const { results, loading, error, search, clearResults, progress, searchStatus } = useSearch()
  const explore = useCallback((params) => search({ ...params, _mode: 'explore' }), [search])
  return { results, loading, error, explore, progress, searchStatus }
}
