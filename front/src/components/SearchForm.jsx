import { useState, useEffect } from 'react'
import { Search, Users, Armchair, SlidersHorizontal } from 'lucide-react'
import LocationInput from './LocationInput'
import DateFlexPicker from './DateFlexPicker'
import { fetchStrategies } from '../api/client'

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
  const [strategies, setStrategies] = useState([])
  const [selectedStrategies, setSelectedStrategies] = useState([])
  const [strategiesLoaded, setStrategiesLoaded] = useState(false)

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

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!origin || !destination) return

    const params = {
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

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Location inputs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <LocationInput label="From" value={origin} onChange={setOrigin} placeholder="City or airport" />
        <LocationInput label="To" value={destination} onChange={setDestination} placeholder="City or airport" />
      </div>

      {/* Flight type */}
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

      {/* Date flexibility */}
      <DateFlexPicker
        mode={dateMode}
        onChange={setDateMode}
        values={dateValues}
        onValuesChange={setDateValues}
      />

      {/* Trip config */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
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

        {/* Nights — hide for exact dates and range (DateFlexPicker handles it) */}
        {dateMode !== 'exact' && dateMode !== 'range' && (
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

        <div className="col-span-2 sm:col-span-2">
          <label className="block text-xs font-body text-warm-500 mb-1">Max budget (EUR)</label>
          <input type="number" value={maxPrice} onChange={(e) => setMaxPrice(e.target.value)}
            placeholder="No limit" min="0" className="input-field text-sm py-2" />
        </div>
      </div>

      {/* Strategies */}
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
        disabled={!origin || !destination || loading}
        className="btn-primary w-full text-base py-3.5">
        {loading ? (
          <><div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent" /> Searching...</>
        ) : (
          <><Search className="h-5 w-5" /> Find Cheap Flights</>
        )}
      </button>
    </form>
  )
}
