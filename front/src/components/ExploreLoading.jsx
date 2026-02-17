import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'

const TRAVEL_FACTS = [
  "Tuesday is usually the cheapest day to fly ✈️",
  "Booking 6-8 weeks ahead saves up to 20%",
  "Hidden city ticketing can save 40-60%",
  "Nearby airports can be 50% cheaper",
  "Round-trip is often cheaper than one-way",
  "Incognito mode doesn't actually change prices",
  "January is the cheapest month to fly in Europe",
  "Budget airlines charge €0 base but €€€ for bags",
  "Connecting flights via Istanbul are often cheapest",
  "Virtual interlining mixes airlines others won't",
  "Flying on Christmas Day is surprisingly cheap",
  "Error fares happen most often on Tuesdays",
]

const STRATEGY_NAMES = [
  "Checking standard prices",
  "Scanning nearby airports",
  "Comparing day-of-week prices",
  "Mixing carriers for deals",
  "Looking for virtual interlining",
  "Finding hidden city routes",
  "Checking throwaway tickets",
  "Analyzing open jaw options",
  "Grouping by destination",
  "Calculating savings",
]

export default function ExploreLoading({ budget }) {
  const [factIndex, setFactIndex] = useState(0)
  const [strategyIndex, setStrategyIndex] = useState(0)
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    const factTimer = setInterval(() => {
      setFactIndex(i => (i + 1) % TRAVEL_FACTS.length)
    }, 3000)
    return () => clearInterval(factTimer)
  }, [])

  useEffect(() => {
    const strategyTimer = setInterval(() => {
      setStrategyIndex(i => (i + 1) % STRATEGY_NAMES.length)
    }, 1500)
    return () => clearInterval(strategyTimer)
  }, [])

  useEffect(() => {
    const start = Date.now()
    const duration = 15000
    const tick = () => {
      const elapsed = Date.now() - start
      const pct = Math.min((elapsed / duration) * 100, 95)
      setProgress(pct)
      if (pct < 95) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  }, [])

  return (
    <div className="card p-8 sm:p-10 text-center relative overflow-hidden">
      {/* Animated plane on dotted path */}
      <div className="explore-plane-track mx-auto mb-8">
        <svg viewBox="0 0 320 80" className="w-full max-w-sm mx-auto" aria-hidden="true">
          {/* Dotted flight path */}
          <path
            d="M 20 60 Q 80 10, 160 40 Q 240 70, 300 20"
            fill="none"
            stroke="currentColor"
            strokeDasharray="4 6"
            className="text-warm-300"
          />
          {/* Animated plane */}
          <g className="explore-plane">
            <text fontSize="20" textAnchor="middle" dominantBaseline="middle">✈️</text>
          </g>
        </svg>
      </div>

      {/* Scanning text */}
      <p className="font-display text-lg font-semibold text-warm-800 mb-2">
        Scanning €{budget} deals across strategies...
      </p>

      {/* Strategy name cycling */}
      <motion.p
        key={strategyIndex}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        className="font-body text-sm text-coral-500 mb-6 h-5"
      >
        {STRATEGY_NAMES[strategyIndex]}...
      </motion.p>

      {/* Progress bar */}
      <div className="w-full max-w-xs mx-auto h-2 bg-warm-100 rounded-full overflow-hidden mb-6">
        <motion.div
          className="h-full bg-gradient-to-r from-coral-400 to-coral-500 rounded-full"
          style={{ width: `${progress}%` }}
          transition={{ ease: 'linear' }}
        />
      </div>

      {/* Rotating facts */}
      <div className="h-12 flex items-center justify-center">
        <motion.p
          key={factIndex}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4 }}
          className="font-body text-sm text-warm-500 italic max-w-md"
        >
          💡 {TRAVEL_FACTS[factIndex]}
        </motion.p>
      </div>
    </div>
  )
}
