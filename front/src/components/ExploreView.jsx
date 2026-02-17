import { useState } from 'react'
import { motion } from 'framer-motion'
import { Compass, ExternalLink, Plane, Clock, MapPin } from 'lucide-react'
import LocationInput from './LocationInput'
import ExploreLoading from './ExploreLoading'
import { useExplore } from '../hooks/useSearch'

const CONTINENTS = [
  { key: '', label: 'All', emoji: '🌍' },
  { key: 'europe', label: 'Europe', emoji: '🇪🇺' },
  { key: 'asia', label: 'Asia', emoji: '🌏' },
  { key: 'africa', label: 'Africa', emoji: '🌍' },
  { key: 'americas', label: 'Americas', emoji: '🌎' },
  { key: 'oceania', label: 'Oceania', emoji: '🏝️' },
]

const DURATION_OPTIONS = [
  { value: '', label: 'Any' },
  { value: '3', label: '<3h' },
  { value: '5', label: '<5h' },
  { value: '8', label: '<8h' },
  { value: '12', label: '<12h' },
]

const SORT_OPTIONS = [
  { value: 'price', label: 'Price' },
  { value: 'distance', label: 'Distance' },
  { value: 'duration', label: 'Duration' },
]

function formatDuration(hours) {
  if (!hours) return ''
  const h = Math.floor(hours)
  const m = Math.round((hours - h) * 60)
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}

function formatDistance(km) {
  if (!km) return ''
  return km >= 1000 ? `${(km / 1000).toFixed(1)}k km` : `${km} km`
}

export default function ExploreView() {
  const [origin, setOrigin] = useState('')
  const [budget, setBudget] = useState(300)
  const [nightsMin, setNightsMin] = useState(2)
  const [nightsMax, setNightsMax] = useState(7)

  // Filters
  const [continent, setContinent] = useState('')
  const [maxDuration, setMaxDuration] = useState('')
  const [directOnly, setDirectOnly] = useState(false)
  const [sortBy, setSortBy] = useState('price')

  const { results, loading, error, explore, pollCount } = useExplore()

  const doSearch = () => {
    if (!origin) return
    explore({
      origin,
      budget,
      nights_min: nightsMin,
      nights_max: nightsMax,
      continent: continent || undefined,
      max_duration: maxDuration || undefined,
      direct_only: directOnly || undefined,
      sort_by: sortBy,
    })
  }

  const handleSearch = (e) => {
    e.preventDefault()
    doSearch()
  }

  const updateFilter = (setter, value) => {
    setter(value)
    // Re-search with new filter if we already have results
    if (results) {
      setTimeout(() => {
        // We need to call explore again; we'll use a ref-like approach
        // Instead, just let the user click search again or auto-search
      }, 0)
    }
  }

  const handleFilterSearch = (newContinent, newMaxDuration, newDirectOnly, newSortBy) => {
    if (!origin || loading) return
    explore({
      origin,
      budget,
      nights_min: nightsMin,
      nights_max: nightsMax,
      continent: newContinent || undefined,
      max_duration: newMaxDuration || undefined,
      direct_only: newDirectOnly || undefined,
      sort_by: newSortBy,
    })
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-8 pb-24 md:pb-8">
      {/* Hero */}
      <div className="text-center mb-8">
        <h2 className="font-display text-3xl sm:text-4xl font-bold text-warm-900 mb-2">
          Where can you go?
        </h2>
        <p className="font-body text-warm-500 max-w-prose mx-auto">
          Set your budget and discover the cheapest destinations from your city.
        </p>
      </div>

      {/* Search form */}
      <form onSubmit={handleSearch} className="card p-5 sm:p-6 mb-4">
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 items-end">
          <LocationInput
            label="From"
            value={origin}
            onChange={setOrigin}
            placeholder="Your city"
          />
          <div>
            <label className="block text-sm font-display font-medium text-warm-600 mb-1.5">
              Budget (EUR): &euro;{budget}
            </label>
            <input
              type="range"
              min="50"
              max="2000"
              step="50"
              value={budget}
              onChange={(e) => setBudget(parseInt(e.target.value))}
              className="w-full accent-coral-500 mt-2"
            />
            <div className="flex justify-between text-xs text-warm-400 mt-1">
              <span>&euro;50</span>
              <span>&euro;2000</span>
            </div>
          </div>
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="block text-sm font-display font-medium text-warm-600 mb-1.5">
                Min nights
              </label>
              <input
                type="number"
                min="1"
                max="30"
                value={nightsMin}
                onChange={(e) => setNightsMin(parseInt(e.target.value) || 1)}
                className="input-field text-center !py-2"
              />
            </div>
            <div className="flex-1">
              <label className="block text-sm font-display font-medium text-warm-600 mb-1.5">
                Max nights
              </label>
              <input
                type="number"
                min="1"
                max="30"
                value={nightsMax}
                onChange={(e) => setNightsMax(parseInt(e.target.value) || 1)}
                className="input-field text-center !py-2"
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={!origin || loading}
            className="btn-primary"
          >
            {loading ? (
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <Compass className="h-5 w-5" />
            )}
            Explore
          </button>
        </div>
      </form>

      {/* Filter bar */}
      <div className="mb-6 overflow-x-auto scrollbar-hide -mx-4 px-4">
        <div className="flex items-center gap-3 min-w-max">
          {/* Continent pills */}
          <div className="flex items-center gap-1.5">
            {CONTINENTS.map((c) => (
              <button
                key={c.key}
                type="button"
                onClick={() => {
                  setContinent(c.key)
                  handleFilterSearch(c.key, maxDuration, directOnly, sortBy)
                }}
                className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-display font-medium transition whitespace-nowrap ${
                  continent === c.key
                    ? 'bg-coral-500 text-white shadow-sm'
                    : 'bg-white border border-warm-200 text-warm-600 hover:border-warm-300'
                }`}
              >
                <span>{c.emoji}</span>
                <span>{c.label}</span>
              </button>
            ))}
          </div>

          {/* Separator */}
          <div className="w-px h-6 bg-warm-200 flex-shrink-0" />

          {/* Max flight time */}
          <select
            value={maxDuration}
            onChange={(e) => {
              setMaxDuration(e.target.value)
              handleFilterSearch(continent, e.target.value, directOnly, sortBy)
            }}
            className="px-3 py-1.5 rounded-full text-sm font-display font-medium bg-white border border-warm-200 text-warm-600 hover:border-warm-300 transition appearance-none cursor-pointer"
          >
            {DURATION_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.value ? `Flight ${o.label}` : 'Any duration'}
              </option>
            ))}
          </select>

          {/* Direct only toggle */}
          <button
            type="button"
            onClick={() => {
              const next = !directOnly
              setDirectOnly(next)
              handleFilterSearch(continent, maxDuration, next, sortBy)
            }}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-display font-medium transition whitespace-nowrap ${
              directOnly
                ? 'bg-coral-500 text-white shadow-sm'
                : 'bg-white border border-warm-200 text-warm-600 hover:border-warm-300'
            }`}
          >
            <Plane className="h-3.5 w-3.5" />
            Direct only
          </button>

          {/* Separator */}
          <div className="w-px h-6 bg-warm-200 flex-shrink-0" />

          {/* Sort pills */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-body text-warm-400 mr-0.5">Sort:</span>
            {SORT_OPTIONS.map((o) => (
              <button
                key={o.value}
                type="button"
                onClick={() => {
                  setSortBy(o.value)
                  handleFilterSearch(continent, maxDuration, directOnly, o.value)
                }}
                className={`px-2.5 py-1 rounded-full text-xs font-display font-medium transition ${
                  sortBy === o.value
                    ? 'bg-warm-800 text-white'
                    : 'bg-white border border-warm-200 text-warm-500 hover:border-warm-300'
                }`}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <div className="card border-red-200 bg-red-50 p-4 mb-6">
          <p className="text-sm text-red-600 font-body">{error}</p>
        </div>
      )}

      {/* Loading animation */}
      {loading && <ExploreLoading budget={budget} pollCount={pollCount} continent={continent} />}

      {/* Results grid */}
      {results && !loading && (
        <>
          <div className="text-sm font-body text-warm-500 mb-4">
            {results.total} destinations found from {results.origin}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {results.results.map((dest, i) => (
              <motion.div
                key={dest.city_code || i}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04, duration: 0.3 }}
                className="card p-5 hover:shadow-md transition-shadow group"
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h3 className="font-display text-lg font-bold text-warm-900">
                      {dest.city}
                    </h3>
                    <p className="text-sm font-body text-warm-500">
                      {dest.country}
                      {dest.continent && dest.continent !== 'other' && (
                        <span className="ml-1.5 text-warm-400">
                          {CONTINENTS.find(c => c.key === dest.continent)?.emoji}
                        </span>
                      )}
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-display font-bold text-coral-500">
                      &euro;{dest.price}
                    </div>
                    {dest.savings_pct > 0 && (
                      <span className="inline-block mt-0.5 px-1.5 py-0.5 rounded text-[10px] font-display font-bold bg-green-100 text-green-700">
                        -{dest.savings_pct}%
                      </span>
                    )}
                  </div>
                </div>

                {/* Badges row */}
                <div className="flex flex-wrap items-center gap-1.5 mb-2">
                  {dest.is_direct && (
                    <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[10px] font-display font-bold bg-blue-50 text-blue-600">
                      ✈️ Direct
                    </span>
                  )}
                  {dest.best_strategy === 'mixed_carrier' && (
                    <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[10px] font-display font-bold bg-coral-50 text-coral-600">
                      Mixed Carrier
                    </span>
                  )}
                </div>

                {/* Flight details */}
                <div className="flex items-center gap-3 text-xs text-warm-400 font-body">
                  <span className="inline-flex items-center gap-1">
                    <Plane className="h-3 w-3" />
                    {dest.fly_from} → {dest.fly_to}
                  </span>
                  {dest.flight_duration_hours > 0 && (
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatDuration(dest.flight_duration_hours)}
                    </span>
                  )}
                  {dest.distance_km > 0 && (
                    <span className="inline-flex items-center gap-1">
                      <MapPin className="h-3 w-3" />
                      {formatDistance(dest.distance_km)}
                    </span>
                  )}
                </div>

                {dest.nights_in_dest > 0 && (
                  <div className="text-xs text-warm-400 font-body mt-1">
                    {dest.nights_in_dest} nights
                  </div>
                )}

                {dest.airlines && dest.airlines.length > 0 && (
                  <div className="flex items-center gap-1 mt-2">
                    {dest.airlines.slice(0, 3).map(code => (
                      <img
                        key={code}
                        src={`https://images.kiwi.com/airlines/64/${code}.png`}
                        alt={code}
                        className="h-5 w-5 rounded object-contain"
                        onError={(e) => { e.target.style.display = 'none' }}
                      />
                    ))}
                  </div>
                )}

                {dest.deep_link && (
                  <a
                    href={dest.deep_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-3 flex items-center justify-center gap-1.5 btn-secondary text-sm py-2 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    View deal
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                )}
              </motion.div>
            ))}
          </div>
        </>
      )}
    </section>
  )
}
