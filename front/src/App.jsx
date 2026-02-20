import { useState } from 'react'
import { Plane, Clock, MapPin, Filter } from 'lucide-react'
import Layout from './components/Layout'
import SearchForm from './components/SearchForm'
import ResultsView from './components/ResultsView'
import RouteCard from './components/RouteCard'
import { useSearch } from './hooks/useSearch'
import { fetchStrategies } from './api/client'
import { useEffect } from 'react'

const CONTINENTS = [
  { key: '', label: 'All', emoji: '🌍' },
  { key: 'europe', label: 'Europe', emoji: '🇪🇺' },
  { key: 'asia', label: 'Asia', emoji: '🌏' },
  { key: 'africa', label: 'Africa', emoji: '🌍' },
  { key: 'americas', label: 'Americas', emoji: '🌎' },
  { key: 'oceania', label: 'Oceania', emoji: '🏝️' },
]

const DURATION_OPTIONS = [
  { value: '', label: 'Any duration' },
  { value: '3', label: 'Flight <3h' },
  { value: '5', label: 'Flight <5h' },
  { value: '8', label: 'Flight <8h' },
  { value: '12', label: 'Flight <12h' },
]

const SORT_OPTIONS = [
  { value: 'price', label: 'Price' },
  { value: 'distance', label: 'Distance' },
  { value: 'duration', label: 'Duration' },
]

export default function App() {
  const { results, loading, error, search, clearResults, mode, progress, searchStatus, currentStrategy } = useSearch()

  // Explore filters (client-side)
  const [continent, setContinent] = useState('')
  const [maxDuration, setMaxDuration] = useState('')
  const [directOnly, setDirectOnly] = useState(false)
  const [sortBy, setSortBy] = useState('price')
  const [strategies, setStrategies] = useState([])

  useEffect(() => {
    fetchStrategies().then(d => setStrategies(d.strategies || [])).catch(() => {})
  }, [])

  // Filter explore results client-side
  const filteredExploreResults = (() => {
    if (!results || mode !== 'explore') return null
    let items = [...(results.results || [])]
    if (continent) items = items.filter(r => r.continent === continent)
    if (maxDuration) items = items.filter(r => r.flight_duration_hours && r.flight_duration_hours <= parseFloat(maxDuration))
    if (directOnly) items = items.filter(r => r.is_direct)
    if (sortBy === 'price') items.sort((a, b) => a.price - b.price)
    else if (sortBy === 'distance') items.sort((a, b) => (a.distance_km || 99999) - (b.distance_km || 99999))
    else if (sortBy === 'duration') items.sort((a, b) => (a.flight_duration_hours || 99) - (b.flight_duration_hours || 99))
    return items
  })()

  return (
    <Layout>
      <section className="mx-auto max-w-6xl px-4 py-8 pb-24 md:pb-8">
        {/* Hero — only before first search */}
        {!results && !loading && (
          <div className="text-center mb-8">
            <h2 className="font-display text-3xl sm:text-5xl font-bold text-warm-900 mb-3 tracking-tight">
              Hack your next flight
            </h2>
            <p className="font-body text-lg text-warm-500 max-w-2xl mx-auto">
              12 strategies to find prices that Google Flights won't show you.
              Leave destination empty to explore everywhere.
            </p>
          </div>
        )}

        {/* Search form — always present */}
        <div className={`card ${!results && !loading ? 'p-5 sm:p-8 max-w-3xl mx-auto' : 'p-5 sm:p-6 max-w-3xl mx-auto mb-6'}`}>
          <SearchForm onSearch={search} loading={loading} />
        </div>

        {/* Error */}
        {error && (
          <div className="card border-red-200 bg-red-50 p-4 mt-6 max-w-3xl mx-auto">
            <p className="text-sm text-red-600 font-body">{error}</p>
            <button onClick={clearResults} className="mt-2 text-sm font-display font-medium text-red-500 hover:text-red-700 transition">
              Try again
            </button>
          </div>
        )}

        {/* Loading — explore mode with progress */}
        {loading && mode === 'explore' && (
          <div className="card p-6 mb-6 max-w-3xl mx-auto">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-8 h-8 animate-spin rounded-full border-2 border-coral-200 border-t-coral-500 flex-shrink-0" />
              <div className="flex-1">
                <h3 className="font-display text-base font-semibold text-warm-800">Exploring destinations...</h3>
                <p className="text-sm text-warm-500 font-body">{searchStatus || 'Starting search...'}</p>
              </div>
              {progress > 0 && <span className="font-display font-bold text-coral-500 text-lg">{progress}%</span>}
            </div>
            {progress > 0 && (
              <div className="w-full bg-warm-200 rounded-full h-2">
                <div className="bg-coral-500 h-2 rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
              </div>
            )}
          </div>
        )}

        {/* Loading — search mode with streaming progress */}
        {loading && mode === 'search' && (
          <div className="card p-6 mb-6 max-w-3xl mx-auto mt-6">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-8 h-8 animate-spin rounded-full border-2 border-coral-200 border-t-coral-500 flex-shrink-0" />
              <div className="flex-1">
                <h3 className="font-display text-base font-semibold text-warm-800">Searching flights...</h3>
                <p className="text-sm text-warm-500 font-body">{searchStatus || 'Starting strategies...'}</p>
              </div>
              {progress > 0 && <span className="font-display font-bold text-coral-500 text-lg">{progress}%</span>}
            </div>
            {progress > 0 && (
              <div className="w-full bg-warm-200 rounded-full h-2">
                <div className="bg-coral-500 h-2 rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
              </div>
            )}
          </div>
        )}

        {/* Explore results */}
        {results && mode === 'explore' && (
          <>
            {/* Filter bar */}
            <div className="mb-6 overflow-x-auto scrollbar-hide -mx-4 px-4">
              <div className="flex items-center gap-3 min-w-max">
                <div className="flex items-center gap-1.5">
                  {CONTINENTS.map((c) => (
                    <button key={c.key} type="button" onClick={() => setContinent(c.key)}
                      className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-display font-medium transition whitespace-nowrap ${
                        continent === c.key ? 'bg-coral-500 text-white shadow-sm' : 'bg-white border border-warm-200 text-warm-600 hover:border-warm-300'
                      }`}>
                      <span>{c.emoji}</span><span>{c.label}</span>
                    </button>
                  ))}
                </div>
                <div className="w-px h-6 bg-warm-200 flex-shrink-0" />
                <select value={maxDuration} onChange={(e) => setMaxDuration(e.target.value)}
                  className="px-3 py-1.5 rounded-full text-sm font-display font-medium bg-white border border-warm-200 text-warm-600 hover:border-warm-300 transition appearance-none cursor-pointer">
                  {DURATION_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
                <button type="button" onClick={() => setDirectOnly(!directOnly)}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-display font-medium transition whitespace-nowrap ${
                    directOnly ? 'bg-coral-500 text-white shadow-sm' : 'bg-white border border-warm-200 text-warm-600 hover:border-warm-300'
                  }`}>
                  <Plane className="h-3.5 w-3.5" /> Direct only
                </button>
                <div className="w-px h-6 bg-warm-200 flex-shrink-0" />
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-body text-warm-400 mr-0.5">Sort:</span>
                  {SORT_OPTIONS.map((o) => (
                    <button key={o.value} type="button" onClick={() => setSortBy(o.value)}
                      className={`px-2.5 py-1 rounded-full text-xs font-display font-medium transition ${
                        sortBy === o.value ? 'bg-warm-800 text-white' : 'bg-white border border-warm-200 text-warm-500 hover:border-warm-300'
                      }`}>{o.label}</button>
                  ))}
                </div>
              </div>
            </div>

            {/* Results count + new search */}
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm font-body text-warm-500">
                {filteredExploreResults?.length || 0} route{(filteredExploreResults?.length || 0) !== 1 ? 's' : ''} found
                {results.origin && ` from ${results.origin}`}
                {loading && filteredExploreResults?.length > 0 && (
                  <span className="ml-2 text-coral-600 animate-pulse">● Live — updating...</span>
                )}
              </div>
              <button onClick={clearResults} className="text-sm font-display font-medium text-warm-400 hover:text-warm-600 transition">
                ✕ New search
              </button>
            </div>

            {/* Route cards grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {(filteredExploreResults || []).map((dest, i) => (
                <RouteCard
                  key={`${dest.fly_from}-${dest.city_code}-${i}`}
                  dest={dest}
                  strategies={strategies}
                  index={i}
                  isStreaming={loading}
                />
              ))}
            </div>
          </>
        )}

        {/* Search results — show even while streaming */}
        {results && mode === 'search' && (
          <div className={loading ? 'mt-4' : 'mt-6'}>
            <ResultsView data={results} onClear={clearResults} isStreaming={loading} />
          </div>
        )}
      </section>
    </Layout>
  )
}
