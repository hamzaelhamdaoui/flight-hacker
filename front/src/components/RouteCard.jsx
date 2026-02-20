import { useState } from 'react'
import { motion } from 'framer-motion'
import { ExternalLink, Plane, Clock, Calendar, ChevronDown, ChevronUp } from 'lucide-react'

const CONTINENT_EMOJIS = {
  europe: '🇪🇺', asia: '🌏', africa: '🌍', americas: '🌎', oceania: '🏝️',
}

function formatDuration(hours) {
  if (!hours) return ''
  const h = Math.floor(hours)
  const m = Math.round((hours - h) * 60)
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}

function formatDate(isoStr) {
  if (!isoStr) return ''
  try {
    const d = new Date(isoStr)
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
  } catch { return isoStr.slice(0, 10) }
}

export default function RouteCard({ dest, strategies = [], index = 0, isStreaming = false }) {
  const [expanded, setExpanded] = useState(false)
  const dates = dest.dates || []

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: isStreaming ? 0 : index * 0.03, duration: 0.25 }}
      className="card p-5 hover:shadow-md transition-shadow"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div>
          <h3 className="font-display text-lg font-bold text-warm-900">{dest.city}</h3>
          <p className="text-sm font-body text-warm-500">
            {dest.country}
            {dest.continent && dest.continent !== 'other' && (
              <span className="ml-1.5 text-warm-400">{CONTINENT_EMOJIS[dest.continent] || ''}</span>
            )}
          </p>
        </div>
        <div className="text-right">
          <div className="text-xs font-body text-warm-400 mb-0.5">from</div>
          <div className="text-2xl font-display font-bold text-coral-500">&euro;{dest.price}</div>
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
            <div key={i} className="flex items-center justify-between py-2 px-2 -mx-2 rounded-lg hover:bg-warm-50 transition group/date">
              <div className="flex items-center gap-3 text-sm font-body">
                <Calendar className="h-3.5 w-3.5 text-warm-400" />
                <span className="text-warm-700 font-medium">{formatDate(d.local_departure)}</span>
                {d.nights_in_dest > 0 && <span className="text-warm-400 text-xs">{d.nights_in_dest}n</span>}
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 font-display font-medium">2 bookings</span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`font-display font-bold ${i === 0 ? 'text-coral-500' : 'text-warm-700'}`}>&euro;{d.price}</span>
                <a href={links[0]} target="_blank" rel="noopener noreferrer" className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-600 font-display font-medium hover:bg-blue-100 transition">① Hub</a>
                <a href={links[1]} target="_blank" rel="noopener noreferrer" className="text-[10px] px-1.5 py-0.5 rounded bg-green-50 text-green-600 font-display font-medium hover:bg-green-100 transition">② Flight</a>
              </div>
            </div>
          ) : (
            <a key={i} href={d.deep_link} target="_blank" rel="noopener noreferrer" className="flex items-center justify-between py-2 px-2 -mx-2 rounded-lg hover:bg-warm-50 transition group/date">
              <div className="flex items-center gap-3 text-sm font-body">
                <Calendar className="h-3.5 w-3.5 text-warm-400" />
                <span className="text-warm-700 font-medium">{formatDate(d.local_departure)}</span>
                {d.nights_in_dest > 0 && <span className="text-warm-400 text-xs">{d.nights_in_dest}n</span>}
                {d.best_strategy && d.best_strategy !== 'standard' && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-50 text-green-600 font-display font-medium">
                    {strategies.find(s => s.id === d.best_strategy)?.name || d.best_strategy}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <span className={`font-display font-bold ${i === 0 ? 'text-coral-500' : 'text-warm-700'}`}>&euro;{d.price}</span>
                <ExternalLink className="h-3.5 w-3.5 text-warm-400 opacity-0 group-hover/date:opacity-100 transition" />
              </div>
            </a>
          )
        })}
      </div>

      {dates.length > 3 && (
        <button onClick={() => setExpanded(!expanded)} className="mt-1 flex items-center gap-1 text-xs font-display font-medium text-coral-500 hover:text-coral-600 transition">
          {expanded ? <><ChevronUp className="h-3.5 w-3.5" /> Show less</> : <><ChevronDown className="h-3.5 w-3.5" /> {dates.length - 3} more date{dates.length - 3 > 1 ? 's' : ''}</>}
        </button>
      )}
    </motion.div>
  )
}
