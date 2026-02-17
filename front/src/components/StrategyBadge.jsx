import {
  Target, Ticket, RefreshCw, Repeat, Scissors,
  Plane, Globe, Calendar, MapPin, Shuffle, Search
} from 'lucide-react'

const STRATEGY_CONFIG = {
  standard: { label: 'Standard', color: 'bg-warm-100 text-warm-600', Icon: Search },
  hidden_city: { label: 'Hidden City', color: 'bg-purple-100 text-purple-700', Icon: Target },
  throwaway: { label: 'Throwaway', color: 'bg-orange-100 text-orange-700', Icon: Ticket },
  open_jaw: { label: 'Open Jaw', color: 'bg-blue-100 text-blue-700', Icon: RefreshCw },
  double_open_jaw: { label: 'Double Open Jaw', color: 'bg-indigo-100 text-indigo-700', Icon: RefreshCw },
  back_to_back: { label: 'Back to Back', color: 'bg-green-100 text-green-700', Icon: Repeat },
  split_ticket: { label: 'Split Ticket', color: 'bg-red-100 text-red-700', Icon: Scissors },
  positioning: { label: 'Positioning', color: 'bg-teal-100 text-teal-700', Icon: Plane },
  everywhere: { label: 'Everywhere', color: 'bg-yellow-100 text-yellow-700', Icon: Globe },
  day_arbitrage: { label: 'Day Arbitrage', color: 'bg-pink-100 text-pink-700', Icon: Calendar },
  nearby_airport: { label: 'Nearby Airport', color: 'bg-cyan-100 text-cyan-700', Icon: MapPin },
  mixed_carrier: { label: 'Mixed Carrier', color: 'bg-amber-100 text-amber-700', Icon: Shuffle },
}

export default function StrategyBadge({ strategy }) {
  const config = STRATEGY_CONFIG[strategy] || STRATEGY_CONFIG.standard
  const { label, color, Icon } = config

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-display font-medium ${color} transition`}>
      <Icon className="h-3 w-3" />
      {label}
    </span>
  )
}
