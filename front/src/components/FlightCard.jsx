import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, ExternalLink, Clock, Luggage, Info } from 'lucide-react'
import StrategyBadge from './StrategyBadge'

function formatTime(isoStr) {
  if (!isoStr) return '--:--'
  try {
    const d = new Date(isoStr)
    return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return '--:--'
  }
}

function formatDate(isoStr) {
  if (!isoStr) return ''
  try {
    const d = new Date(isoStr)
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
  } catch {
    return ''
  }
}

function formatDuration(seconds) {
  if (!seconds) return ''
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${h}h ${m}m`
}

function getStopCount(route) {
  if (!route || route.length === 0) return 0
  const outbound = route.filter(s => s.return_leg === 0)
  return Math.max(0, outbound.length - 1)
}

export default function FlightCard({ flight, index }) {
  const [expanded, setExpanded] = useState(false)
  const stops = getStopCount(flight.route)
  const depDuration = flight.duration?.departure
  const retDuration = flight.duration?.return

  const uniqueAirlines = [...new Set(flight.airlines || [])]

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.3 }}
      className="card hover:shadow-md transition-shadow"
    >
      <div className="p-4 sm:p-5">
        {/* Top row: badges + price */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex flex-wrap gap-1.5">
            <StrategyBadge strategy={flight.strategy} />
            {flight.savings_pct != null && flight.savings_pct > 0 && (
              <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2.5 py-1 text-xs font-display font-medium text-green-700">
                Save {flight.savings_pct}%
              </span>
            )}
          </div>
          <div className="text-right shrink-0">
            <div className="text-2xl font-display font-bold text-warm-900">
              &euro;{flight.price}
            </div>
            {flight.savings_vs != null && (
              <div className="text-xs text-warm-400 line-through">
                &euro;{flight.savings_vs}
              </div>
            )}
          </div>
        </div>

        {/* Route info */}
        <div className="flex items-center gap-3 sm:gap-6">
          {/* Airlines logos */}
          <div className="hidden sm:flex flex-col gap-1">
            {uniqueAirlines.slice(0, 2).map(code => (
              <img
                key={code}
                src={`https://images.kiwi.com/airlines/64/${code}.png`}
                alt={code}
                className="h-8 w-8 rounded object-contain"
                onError={(e) => { e.target.style.display = 'none' }}
              />
            ))}
          </div>

          {/* Departure */}
          <div className="text-center min-w-0">
            <div className="text-lg font-display font-bold text-warm-900">
              {formatTime(flight.local_departure)}
            </div>
            <div className="text-xs font-body text-warm-500">
              {flight.fly_from}
            </div>
            <div className="text-[11px] text-warm-400 truncate max-w-[80px]">
              {formatDate(flight.local_departure)}
            </div>
          </div>

          {/* Route line */}
          <div className="flex-1 flex flex-col items-center gap-1 px-2">
            {depDuration && (
              <div className="text-[11px] font-body text-warm-400 flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {formatDuration(depDuration)}
              </div>
            )}
            <div className="relative w-full flex items-center">
              <div className="h-px flex-1 bg-warm-300" />
              {stops > 0 && (
                <div className="mx-1 flex h-4 min-w-[20px] items-center justify-center rounded-full bg-warm-200 px-1.5 text-[10px] font-display font-semibold text-warm-600">
                  {stops}
                </div>
              )}
              <div className="h-px flex-1 bg-warm-300" />
              <div className="absolute -right-0.5 top-1/2 -translate-y-1/2 h-0 w-0 border-y-[3px] border-y-transparent border-l-[5px] border-l-warm-300" />
            </div>
            <div className="text-[11px] text-warm-400">
              {stops === 0 ? 'Direct' : `${stops} stop${stops > 1 ? 's' : ''}`}
            </div>
          </div>

          {/* Arrival */}
          <div className="text-center min-w-0">
            <div className="text-lg font-display font-bold text-warm-900">
              {formatTime(flight.local_arrival)}
            </div>
            <div className="text-xs font-body text-warm-500">
              {flight.fly_to}
            </div>
            <div className="text-[11px] text-warm-400 truncate max-w-[80px]">
              {formatDate(flight.local_arrival)}
            </div>
          </div>
        </div>

        {/* City names */}
        <div className="flex justify-between mt-2 text-xs text-warm-500 font-body">
          <span className="truncate max-w-[120px]">{flight.city_from}</span>
          <span className="truncate max-w-[120px]">{flight.city_to}</span>
        </div>

        {/* Actions row */}
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-warm-100">
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1.5 text-sm font-display font-medium text-warm-500 hover:text-warm-700 transition"
          >
            <Info className="h-3.5 w-3.5" />
            Details
            <ChevronDown
              className={`h-3.5 w-3.5 transition-transform ${expanded ? 'rotate-180' : ''}`}
            />
          </button>

          {flight.deep_link && (
            <a
              href={flight.deep_link}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary text-sm py-2 px-4"
            >
              Book
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
        </div>
      </div>

      {/* Expanded details */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 sm:px-5 pb-4 border-t border-warm-100 pt-3 space-y-3">
              {/* Strategy explanation */}
              {flight.strategy_explanation && (
                <div className="rounded-xl bg-warm-50 p-3 text-sm font-body text-warm-700">
                  <span className="font-display font-medium text-warm-800">How it works: </span>
                  {flight.strategy_explanation}
                </div>
              )}

              {/* Segments */}
              <div className="space-y-2">
                <h4 className="text-xs font-display font-semibold text-warm-500 uppercase tracking-wider">
                  Flight Segments
                </h4>
                {(flight.route || []).map((seg, i) => (
                  <div key={seg.id || i} className="flex items-center gap-3 text-sm font-body">
                    <img
                      src={`https://images.kiwi.com/airlines/64/${seg.airline}.png`}
                      alt={seg.airline}
                      className="h-6 w-6 rounded object-contain"
                      onError={(e) => { e.target.style.display = 'none' }}
                    />
                    <span className="font-display font-medium text-warm-800">
                      {seg.fly_from} &rarr; {seg.fly_to}
                    </span>
                    <span className="text-warm-400">
                      {seg.airline}{seg.flight_no ? ` ${seg.flight_no}` : ''}
                    </span>
                    <span className="text-warm-400 ml-auto">
                      {formatTime(seg.local_departure)} &ndash; {formatTime(seg.local_arrival)}
                    </span>
                    {seg.return_leg === 1 && (
                      <span className="text-xs bg-warm-100 text-warm-500 px-1.5 py-0.5 rounded font-display">
                        Return
                      </span>
                    )}
                  </div>
                ))}
              </div>

              {/* Baggage */}
              {flight.bags_price && Object.keys(flight.bags_price).length > 0 && (
                <div className="flex items-center gap-2 text-sm text-warm-500 font-body">
                  <Luggage className="h-4 w-4" />
                  {Object.entries(flight.bags_price).map(([k, v]) => (
                    <span key={k}>Bag {k}: +&euro;{v}</span>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
