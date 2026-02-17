import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { ArrowUpDown, Filter, Zap, X } from 'lucide-react'
import FlightCard from './FlightCard'
import StrategyBadge from './StrategyBadge'

export default function ResultsView({ data, onClear }) {
  const [sortBy, setSortBy] = useState('price')
  const [filterStrategy, setFilterStrategy] = useState(null)
  const [filterStops, setFilterStops] = useState(null)

  const { results, total, cheapest, strategies_used } = data

  const filtered = useMemo(() => {
    let items = [...results]
    if (filterStrategy) {
      items = items.filter(f => f.strategy === filterStrategy)
    }
    if (filterStops !== null) {
      items = items.filter(f => {
        const outbound = (f.route || []).filter(s => s.return_leg === 0)
        const stops = Math.max(0, outbound.length - 1)
        return filterStops === 0 ? stops === 0 : stops <= filterStops
      })
    }
    if (sortBy === 'price') {
      items.sort((a, b) => a.price - b.price)
    } else if (sortBy === 'duration') {
      items.sort((a, b) => (a.duration?.total || 0) - (b.duration?.total || 0))
    }
    return items
  }, [results, sortBy, filterStrategy, filterStops])

  return (
    <div className="space-y-5">
      {/* Summary bar */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="card p-4 flex flex-wrap items-center gap-3 sm:gap-5"
      >
        <div className="flex items-center gap-2">
          <Zap className="h-5 w-5 text-coral-500" />
          <span className="font-display font-bold text-warm-900">{total} flights</span>
        </div>
        {cheapest != null && (
          <span className="text-sm font-body text-warm-500">
            Cheapest: <span className="font-display font-bold text-green-600">&euro;{cheapest}</span>
          </span>
        )}
        <span className="text-sm font-body text-warm-500">
          {strategies_used.length} strateg{strategies_used.length === 1 ? 'y' : 'ies'} used
        </span>
        <button
          onClick={onClear}
          className="ml-auto text-sm font-display font-medium text-warm-400 hover:text-warm-600 transition flex items-center gap-1"
        >
          <X className="h-4 w-4" />
          New search
        </button>
      </motion.div>

      {/* Filter/sort bar */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1.5 text-sm text-warm-500">
          <ArrowUpDown className="h-4 w-4" />
          <span className="font-display font-medium">Sort:</span>
        </div>
        <button
          onClick={() => setSortBy('price')}
          className={`rounded-lg px-3 py-1.5 text-sm font-display font-medium transition ${
            sortBy === 'price' ? 'bg-coral-100 text-coral-600' : 'bg-warm-100 text-warm-500 hover:bg-warm-200'
          }`}
        >
          Price
        </button>
        <button
          onClick={() => setSortBy('duration')}
          className={`rounded-lg px-3 py-1.5 text-sm font-display font-medium transition ${
            sortBy === 'duration' ? 'bg-coral-100 text-coral-600' : 'bg-warm-100 text-warm-500 hover:bg-warm-200'
          }`}
        >
          Duration
        </button>

        <div className="w-px h-5 bg-warm-200 mx-1 hidden sm:block" />

        <div className="flex items-center gap-1.5 text-sm text-warm-500">
          <Filter className="h-4 w-4" />
          <span className="font-display font-medium">Stops:</span>
        </div>
        {[null, 0, 1, 2].map(v => (
          <button
            key={String(v)}
            onClick={() => setFilterStops(filterStops === v ? null : v)}
            className={`rounded-lg px-3 py-1.5 text-sm font-display font-medium transition ${
              filterStops === v ? 'bg-coral-100 text-coral-600' : 'bg-warm-100 text-warm-500 hover:bg-warm-200'
            }`}
          >
            {v === null ? 'All' : v === 0 ? 'Direct' : `${v}+`}
          </button>
        ))}
      </div>

      {/* Strategy filter pills */}
      {strategies_used.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setFilterStrategy(null)}
            className={`rounded-full px-3 py-1 text-xs font-display font-medium transition ${
              !filterStrategy ? 'bg-coral-500 text-white' : 'bg-warm-100 text-warm-500 hover:bg-warm-200'
            }`}
          >
            All
          </button>
          {strategies_used.map(s => (
            <button key={s} onClick={() => setFilterStrategy(filterStrategy === s ? null : s)}>
              <StrategyBadge strategy={s} />
            </button>
          ))}
        </div>
      )}

      {/* Flight cards */}
      <div className="space-y-3">
        {filtered.length === 0 && (
          <div className="card p-8 text-center">
            <p className="text-warm-500 font-body">No flights match your filters. Try adjusting them.</p>
          </div>
        )}
        {filtered.map((flight, i) => (
          <FlightCard key={flight.id || i} flight={flight} index={i} />
        ))}
      </div>
    </div>
  )
}
