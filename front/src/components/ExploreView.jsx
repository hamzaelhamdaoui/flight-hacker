import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Compass, ExternalLink, Plane, Clock, MapPin, Info, Calendar, ChevronDown, ChevronUp } from 'lucide-react'
import LocationInput from './LocationInput'
import { useExplore } from '../hooks/useSearch'
import { fetchStrategies } from '../api/client'

// Generate next 12 months from now
function getNext12Months() {
  const months = []
  const now = new Date()
  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() + i, 1)
    months.push({
      key: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`,
      label: d.toLocaleDateString('en-US', { month: 'short' }),
      year: d.getFullYear(),
    })
  }
  return months
}

const MONTHS = getNext12Months()

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

function formatDate(isoStr) {
  if (!isoStr) return ''
  try {
    const d = new Date(isoStr)
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
  } catch { return isoStr.slice(0, 10) }
}

function RouteCard({ dest, strategies, index, isStreaming }) {
  const [expanded, setExpanded] = useState(false)
  const dates = dest.dates || []
  const topDate = dates[0]

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: isStreaming ? 0 : index * 0.03, duration: 0.25 }}
      className="card p-5 hover:shadow-md transition-shadow"
    >
      {/* Header: city + price */}
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
          <div className="text-xs font-body text-warm-400 mb-0.5">from</div>
          <div className="text-2xl font-display font-bold text-coral-500">
            &euro;{dest.price}
          </div>
        </div>
      </div>

      {/* Badges */}
      <div className="flex flex-wrap items-center gap-1.5 mb-3">
        {dest.is_direct && (
          <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[10px] font-display font-bold bg-blue-50 text-blue-600">
            ✈️ Direct
          </span>
        )}
        {dest.best_strategy && dest.best_strategy !== 'standard' && (
          <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[10px] font-display font-bold bg-green-50 text-green-600">
            {strategies.find(s => s.id === dest.best_strategy)?.name || dest.best_strategy}
          </span>
        )}
        <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[10px] font-display font-bold bg-warm-100 text-warm-600">
          <Plane className="h-3 w-3" /> {dest.fly_from} → {dest.city_code}
        </span>
        {dest.flight_duration_hours > 0 && (
          <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[10px] font-display font-bold bg-warm-100 text-warm-500">
            <Clock className="h-3 w-3" /> {formatDuration(dest.flight_duration_hours)}
          </span>
        )}
      </div>

      {/* Date rows */}
      <div className="border-t border-warm-100 pt-2 space-y-0">
        {(expanded ? dates : dates.slice(0, 3)).map((d, i) => {
          const isSplit = d.deep_link && d.deep_link.includes('|')
          const links = isSplit ? d.deep_link.split('|') : [d.deep_link]

          return isSplit ? (
            <div
              key={i}
              className="flex items-center justify-between py-2 px-2 -mx-2 rounded-lg hover:bg-warm-50 transition group/date"
            >
              <div className="flex items-center gap-3 text-sm font-body">
                <Calendar className="h-3.5 w-3.5 text-warm-400" />
                <span className="text-warm-700 font-medium">{formatDate(d.local_departure)}</span>
                {d.nights_in_dest > 0 && (
                  <span className="text-warm-400 text-xs">{d.nights_in_dest}n</span>
                )}
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 font-display font-medium">
                  2 bookings
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`font-display font-bold ${i === 0 ? 'text-coral-500' : 'text-warm-700'}`}>
                  &euro;{d.price}
                </span>
                <a href={links[0]} target="_blank" rel="noopener noreferrer"
                  className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-600 font-display font-medium hover:bg-blue-100 transition"
                >① Hub</a>
                <a href={links[1]} target="_blank" rel="noopener noreferrer"
                  className="text-[10px] px-1.5 py-0.5 rounded bg-green-50 text-green-600 font-display font-medium hover:bg-green-100 transition"
                >② Flight</a>
              </div>
            </div>
          ) : (
          <a
            key={i}
            href={d.deep_link}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-between py-2 px-2 -mx-2 rounded-lg hover:bg-warm-50 transition group/date"
          >
            <div className="flex items-center gap-3 text-sm font-body">
              <Calendar className="h-3.5 w-3.5 text-warm-400" />
              <span className="text-warm-700 font-medium">{formatDate(d.local_departure)}</span>
              {d.nights_in_dest > 0 && (
                <span className="text-warm-400 text-xs">{d.nights_in_dest}n</span>
              )}
              {d.best_strategy && d.best_strategy !== 'standard' && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-50 text-green-600 font-display font-medium">
                  {strategies.find(s => s.id === d.best_strategy)?.name || d.best_strategy}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className={`font-display font-bold ${i === 0 ? 'text-coral-500' : 'text-warm-700'}`}>
                &euro;{d.price}
              </span>
              <ExternalLink className="h-3.5 w-3.5 text-warm-400 opacity-0 group-hover/date:opacity-100 transition" />
            </div>
          </a>
          )
        })}
      </div>

      {/* Expand/collapse */}
      {dates.length > 3 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-1 flex items-center gap-1 text-xs font-display font-medium text-coral-500 hover:text-coral-600 transition"
        >
          {expanded ? (
            <><ChevronUp className="h-3.5 w-3.5" /> Show less</>
          ) : (
            <><ChevronDown className="h-3.5 w-3.5" /> {dates.length - 3} more date{dates.length - 3 > 1 ? 's' : ''}</>
          )}
        </button>
      )}
    </motion.div>
  )
}

export default function ExploreView() {
  const [origin, setOrigin] = useState('')
  const [budget, setBudget] = useState(300)
  const [nightsMin, setNightsMin] = useState(2)
  const [nightsMax, setNightsMax] = useState(7)

  // Month selection (default: next 3 months)
  const [selectedMonths, setSelectedMonths] = useState(() => MONTHS.slice(0, 3).map(m => m.key))

  // Filters
  const [continent, setContinent] = useState('')
  const [maxDuration, setMaxDuration] = useState('')
  const [directOnly, setDirectOnly] = useState(false)
  const [sortBy, setSortBy] = useState('price')

  // Strategy selection
  const [availableStrategies, setAvailableStrategies] = useState([])
  const [selectedStrategies, setSelectedStrategies] = useState([])
  const [strategiesLoaded, setStrategiesLoaded] = useState(false)

  const { results, loading, error, explore, progress, searchStatus } = useExplore()

  useEffect(() => {
    const loadStrategies = async () => {
      try {
        const data = await fetchStrategies()
        setAvailableStrategies(data.strategies || [])
        const defaults = data.strategies?.filter(s => s.default).map(s => s.id) || []
        setSelectedStrategies(defaults)
        setStrategiesLoaded(true)
      } catch (err) {
        console.error('Failed to load strategies:', err)
        setSelectedStrategies(['standard', 'nearby_airport', 'mixed_carrier', 'day_arbitrage'])
        setStrategiesLoaded(true)
      }
    }
    loadStrategies()
  }, [])

  const doSearch = () => {
    if (!origin || !strategiesLoaded || selectedMonths.length === 0) return
    explore({
      origin, budget,
      nights_min: nightsMin, nights_max: nightsMax,
      continent: continent || undefined,
      max_duration: maxDuration || undefined,
      direct_only: directOnly || undefined,
      sort_by: sortBy,
      strategies: selectedStrategies.length > 0 ? selectedStrategies : undefined,
      months: selectedMonths,
    })
  }

  const toggleMonth = (key) => {
    setSelectedMonths(prev =>
      prev.includes(key) ? prev.filter(x => x !== key) : [...prev, key]
    )
  }

  const handleSearch = (e) => { e.preventDefault(); doSearch() }

  const toggleStrategy = (id) => {
    setSelectedStrategies(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const selectAll = () => setSelectedStrategies(availableStrategies.map(s => s.id))
  const selectNone = () => setSelectedStrategies([])
  const selectDefaults = () => setSelectedStrategies(availableStrategies.filter(s => s.default).map(s => s.id))

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
          <LocationInput label="From" value={origin} onChange={setOrigin} placeholder="Your city" />
          <div>
            <label className="block text-sm font-display font-medium text-warm-600 mb-1.5">
              Budget (EUR): &euro;{budget}
            </label>
            <input type="range" min="50" max="2000" step="50" value={budget}
              onChange={(e) => setBudget(parseInt(e.target.value))}
              className="w-full accent-coral-500 mt-2" />
            <div className="flex justify-between text-xs text-warm-400 mt-1">
              <span>&euro;50</span><span>&euro;2000</span>
            </div>
          </div>
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="block text-sm font-display font-medium text-warm-600 mb-1.5">Min nights</label>
              <input type="number" min="1" max="30" value={nightsMin}
                onChange={(e) => setNightsMin(parseInt(e.target.value) || 1)}
                className="input-field text-center !py-2" />
            </div>
            <div className="flex-1">
              <label className="block text-sm font-display font-medium text-warm-600 mb-1.5">Max nights</label>
              <input type="number" min="1" max="30" value={nightsMax}
                onChange={(e) => setNightsMax(parseInt(e.target.value) || 1)}
                className="input-field text-center !py-2" />
            </div>
          </div>
          <button type="submit"
            disabled={!origin || loading || !strategiesLoaded || selectedStrategies.length === 0 || selectedMonths.length === 0}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed">
            {loading ? (
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : <Compass className="h-5 w-5" />}
            Explore
          </button>
        </div>

        {/* Month selector */}
        <div className="mt-4 pt-4 border-t border-warm-100">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-display font-medium text-warm-600">Months to search</label>
            <span className="text-xs text-warm-400 font-body">{selectedMonths.length} selected</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {MONTHS.map((m, idx) => (
              <button key={m.key} type="button" onClick={() => toggleMonth(m.key)}
                className={`px-3 py-1.5 rounded-lg text-xs font-display font-medium transition ${
                  selectedMonths.includes(m.key)
                    ? 'bg-coral-500 text-white shadow-sm'
                    : 'bg-white border border-warm-200 text-warm-500 hover:border-warm-300'
                }`}>
                {m.label}{idx === 0 || MONTHS[idx - 1]?.year !== m.year ? ` '${String(m.year).slice(2)}` : ''}
              </button>
            ))}
          </div>
        </div>
      </form>

      {/* Strategy Selector */}
      {availableStrategies.length > 0 && (
        <div className="card p-4 mb-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <h3 className="font-display text-sm font-semibold text-warm-700">Strategies</h3>
              <span className="text-xs text-warm-400 font-body">{selectedStrategies.length}/{availableStrategies.length}</span>
            </div>
            <div className="flex items-center gap-2">
              <button type="button" onClick={selectAll} className="text-[11px] font-display text-coral-500 hover:text-coral-600">All</button>
              <span className="text-warm-300">·</span>
              <button type="button" onClick={selectDefaults} className="text-[11px] font-display text-coral-500 hover:text-coral-600">Defaults</button>
              <span className="text-warm-300">·</span>
              <button type="button" onClick={selectNone} className="text-[11px] font-display text-coral-500 hover:text-coral-600">None</button>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {availableStrategies.map((s) => (
              <button key={s.id} type="button" onClick={() => toggleStrategy(s.id)} title={s.description}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-display font-medium transition ${
                  selectedStrategies.includes(s.id)
                    ? 'bg-blue-500 text-white shadow-sm'
                    : 'bg-white border border-warm-200 text-warm-500 hover:border-warm-300 hover:bg-warm-50'
                }`}>
                {s.name}
              </button>
            ))}
          </div>
        </div>
      )}

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
            {DURATION_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.value ? `Flight ${o.label}` : 'Any duration'}</option>
            ))}
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

      {error && (
        <div className="card border-red-200 bg-red-50 p-4 mb-6">
          <p className="text-sm text-red-600 font-body">{error}</p>
        </div>
      )}

      {/* Loading / Progress */}
      {loading && (
        <div className="card p-6 mb-6">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-8 h-8 animate-spin rounded-full border-2 border-coral-200 border-t-coral-500 flex-shrink-0" />
            <div className="flex-1">
              <h3 className="font-display text-base font-semibold text-warm-800">
                Exploring destinations...
              </h3>
              <p className="text-sm text-warm-500 font-body">
                {searchStatus || `Using ${selectedStrategies.length} strategies`}
              </p>
            </div>
            {progress > 0 && (
              <span className="font-display font-bold text-coral-500 text-lg">{progress}%</span>
            )}
          </div>
          {progress > 0 && (
            <div className="w-full bg-warm-200 rounded-full h-2">
              <div className="bg-coral-500 h-2 rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
            </div>
          )}
        </div>
      )}

      {/* Results */}
      {results && (
        <>
          <div className="text-sm font-body text-warm-500 mb-4">
            {results.total} route{results.total !== 1 ? 's' : ''} found from {results.origin}
            {loading && results.total > 0 && (
              <span className="ml-2 text-coral-600 animate-pulse">● Live — updating...</span>
            )}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {results.results.map((dest, i) => (
              <RouteCard
                key={`${dest.fly_from}-${dest.city_code}-${i}`}
                dest={dest}
                strategies={availableStrategies}
                index={i}
                isStreaming={loading}
              />
            ))}
          </div>
        </>
      )}
    </section>
  )
}
