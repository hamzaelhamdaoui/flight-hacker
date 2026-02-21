import { useState, useEffect } from 'react'
import { Search, ChevronDown, Users, Armchair, SlidersHorizontal, Compass } from 'lucide-react'
import LocationInput from './LocationInput'
import DateFlexPicker from './DateFlexPicker'
import { fetchStrategies } from '../api/client'

// Generate next 12 months
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

function formatDateForApi(dateStr) {
  if (!dateStr) return undefined
  const [y, m, d] = dateStr.split('-')
  return `${d}/${m}/${y}`
}

const CABIN_OPTIONS = [
  { value: 'M', label: 'Economy' },
  { value: 'W', label: 'Premium' },
  { value: 'C', label: 'Business' },
  { value: 'F', label: 'First' },
]

export default function SearchForm({ onSearch, loading }) {
  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [flightType, setFlightType] = useState('round')
  const [dateMode, setDateMode] = useState('range')
  const [dateValues, setDateValues] = useState({
    nightsMin: 2,
    nightsMax: 7,
    monthsAhead: 3,
    month: new Date().getMonth() + 1,
    year: 2026,
  })
  const [adults, setAdults] = useState(1)
  const [cabin, setCabin] = useState('M')
  const [maxPrice, setMaxPrice] = useState('')
  const [budget, setBudget] = useState(300)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [strategies, setStrategies] = useState([])
  const [selectedStrategies, setSelectedStrategies] = useState([])
  const [strategiesLoaded, setStrategiesLoaded] = useState(false)

  // Month multi-selector for explore mode
  const [selectedMonths, setSelectedMonths] = useState(() => MONTHS.slice(0, 3).map(m => m.key))

  const isExploreMode = !destination

  useEffect(() => {
    fetchStrategies()
      .then(data => {
        setStrategies(data.strategies || [])
        const defaults = data.strategies?.filter(s => s.default).map(s => s.id) || []
        setSelectedStrategies(defaults)
        setStrategiesLoaded(true)
      })
      .catch(() => {
        setSelectedStrategies(['standard', 'nearby_airport', 'mixed_carrier', 'day_arbitrage'])
        setStrategiesLoaded(true)
      })
  }, [])

  const toggleStrategy = (id) => {
    setSelectedStrategies(prev =>
      prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]
    )
  }

  const selectAll = () => setSelectedStrategies(strategies.map(s => s.id))
  const selectNone = () => setSelectedStrategies([])
  const selectDefaults = () => setSelectedStrategies(strategies.filter(s => s.default).map(s => s.id))

  const toggleMonth = (key) => {
    setSelectedMonths(prev =>
      prev.includes(key) ? prev.filter(x => x !== key) : [...prev, key]
    )
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!origin) return

    if (isExploreMode) {
      // Explore mode — discover destinations
      onSearch({
        _mode: 'explore',
        origin,
        budget,
        nights_min: dateValues.nightsMin || 2,
        nights_max: dateValues.nightsMax || 7,
        strategies: selectedStrategies.length > 0 ? selectedStrategies : undefined,
        months: selectedMonths,
      })
    } else {
      // Search mode — specific destination
      const params = {
        _mode: 'search',
        origin,
        destination,
        date_mode: dateMode,
        flight_type: flightType,
        adults,
        selected_cabins: cabin,
        max_price: maxPrice ? parseInt(maxPrice) : null,
        nights_min: dateValues.nightsMin || 2,
        nights_max: dateValues.nightsMax || 7,
        strategies: selectedStrategies,
      }

      if (dateMode === 'exact') {
        params.date_from = formatDateForApi(dateValues.dateFrom)
        params.date_to = formatDateForApi(dateValues.dateFrom)
        params.return_from = formatDateForApi(dateValues.returnFrom)
        params.return_to = formatDateForApi(dateValues.returnFrom)
      } else if (dateMode === 'range') {
        params.date_from = formatDateForApi(dateValues.dateFrom)
        params.date_to = formatDateForApi(dateValues.dateTo)
      } else if (dateMode === 'month') {
        params.month = dateValues.month
        params.year = dateValues.year
      } else if (dateMode === 'cheapest') {
        params.months_ahead = dateValues.monthsAhead || 3
      } else if (dateMode === 'weekends') {
        params.weekends_from = formatDateForApi(dateValues.weekendsFrom)
        params.weekends_to = formatDateForApi(dateValues.weekendsTo)
      }

      onSearch(params)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Location inputs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <LocationInput
          label="From"
          value={origin}
          onChange={setOrigin}
          placeholder="City or airport"
        />
        <LocationInput
          label="To"
          value={destination}
          onChange={setDestination}
          placeholder="Anywhere (explore)"
          allowAnywhere
        />
      </div>

      {/* Mode indicator */}
      {isExploreMode && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-coral-50 border border-coral-200">
          <Compass className="h-4 w-4 text-coral-500" />
          <span className="text-sm font-display font-medium text-coral-700">
            Explore mode — discovering cheapest destinations from {origin || '...'}
          </span>
        </div>
      )}

      {/* Flight type toggle — only for search mode */}
      {!isExploreMode && (
        <div className="flex gap-2">
          <button type="button" onClick={() => setFlightType('round')}
            className={`rounded-lg px-4 py-2 text-sm font-display font-medium transition ${
              flightType === 'round' ? 'bg-coral-500 text-white shadow-sm' : 'bg-warm-100 text-warm-600 hover:bg-warm-200'
            }`}>Round trip</button>
          <button type="button" onClick={() => setFlightType('oneway')}
            className={`rounded-lg px-4 py-2 text-sm font-display font-medium transition ${
              flightType === 'oneway' ? 'bg-coral-500 text-white shadow-sm' : 'bg-warm-100 text-warm-600 hover:bg-warm-200'
            }`}>One way</button>
        </div>
      )}

      {/* Date flexibility — search mode */}
      {!isExploreMode && (
        <DateFlexPicker
          mode={dateMode}
          onChange={setDateMode}
          values={dateValues}
          onValuesChange={setDateValues}
        />
      )}

      {/* Months multi-selector — explore mode */}
      {isExploreMode && (
        <div>
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
      )}

      {/* Trip config */}
      <div className={`grid gap-3 ${isExploreMode ? 'grid-cols-2 sm:grid-cols-3' : 'grid-cols-2 sm:grid-cols-4'}`}>
        {!isExploreMode && (
          <>
            <div>
              <label className="block text-xs font-body text-warm-500 mb-1">
                <Users className="h-3 w-3 inline mr-1" />Passengers
              </label>
              <select value={adults} onChange={(e) => setAdults(parseInt(e.target.value))} className="input-field text-sm py-2">
                {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(n => <option key={n} value={n}>{n} adult{n > 1 ? 's' : ''}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-body text-warm-500 mb-1">
                <Armchair className="h-3 w-3 inline mr-1" />Cabin
              </label>
              <select value={cabin} onChange={(e) => setCabin(e.target.value)} className="input-field text-sm py-2">
                {CABIN_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
            </div>
          </>
        )}

        {/* Nights — hide for exact dates in search mode, and for range mode (DateFlexPicker has its own) */}
        {(isExploreMode || (dateMode !== 'exact' && dateMode !== 'range')) && (
          <>
            <div>
              <label className="block text-xs font-body text-warm-500 mb-1">Min nights</label>
              <input type="number" min="1" max="30" value={dateValues.nightsMin || 2}
                onChange={(e) => setDateValues(v => ({ ...v, nightsMin: parseInt(e.target.value) || 1 }))}
                className="input-field text-sm py-2 text-center" />
            </div>
            <div>
              <label className="block text-xs font-body text-warm-500 mb-1">Max nights</label>
              <input type="number" min="1" max="30" value={dateValues.nightsMax || 7}
                onChange={(e) => setDateValues(v => ({ ...v, nightsMax: parseInt(e.target.value) || 1 }))}
                className="input-field text-sm py-2 text-center" />
            </div>
          </>
        )}

        {/* Budget */}
        <div className={isExploreMode ? 'col-span-2 sm:col-span-1' : 'col-span-2 sm:col-span-2'}>
          {isExploreMode ? (
            <>
              <label className="block text-xs font-body text-warm-500 mb-1">Budget: €{budget}</label>
              <input type="range" min="50" max="2000" step="50" value={budget}
                onChange={(e) => setBudget(parseInt(e.target.value))}
                className="w-full accent-coral-500 mt-1" />
              <div className="flex justify-between text-[10px] text-warm-400"><span>€50</span><span>€2000</span></div>
            </>
          ) : (
            <>
              <label className="block text-xs font-body text-warm-500 mb-1">Max budget (EUR)</label>
              <input type="number" value={maxPrice} onChange={(e) => setMaxPrice(e.target.value)}
                placeholder="No limit" min="0" className="input-field text-sm py-2" />
            </>
          )}
        </div>
      </div>

      {/* Strategies — always visible */}
      {strategies.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <SlidersHorizontal className="h-4 w-4 text-warm-500" />
              <span className="text-sm font-display font-medium text-warm-600">Strategies</span>
              <span className="text-xs text-warm-400 font-body">{selectedStrategies.length}/{strategies.length}</span>
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
            {strategies.map((s) => (
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

      {/* Search button */}
      <button type="submit"
        disabled={!origin || loading || (isExploreMode && (selectedMonths.length === 0 || selectedStrategies.length === 0))}
        className="btn-primary w-full text-base py-3.5">
        {loading ? (
          <><div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent" /> Searching...</>
        ) : isExploreMode ? (
          <><Compass className="h-5 w-5" /> Explore Destinations</>
        ) : (
          <><Search className="h-5 w-5" /> Find Cheap Flights</>
        )}
      </button>
    </form>
  )
}
