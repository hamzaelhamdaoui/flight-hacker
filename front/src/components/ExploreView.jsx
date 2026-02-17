import { useState } from 'react'
import { motion } from 'framer-motion'
import { Compass, ExternalLink, Plane } from 'lucide-react'
import LocationInput from './LocationInput'
import { useExplore } from '../hooks/useSearch'

export default function ExploreView() {
  const [origin, setOrigin] = useState('')
  const [budget, setBudget] = useState(300)
  const { results, loading, error, explore } = useExplore()

  const handleSearch = (e) => {
    e.preventDefault()
    if (!origin) return
    explore({ origin, budget })
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
      <form onSubmit={handleSearch} className="card p-5 sm:p-6 mb-8">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-end">
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

      {error && (
        <div className="card border-red-200 bg-red-50 p-4 mb-6">
          <p className="text-sm text-red-600 font-body">{error}</p>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card p-5 space-y-3">
              <div className="skeleton h-6 w-3/4" />
              <div className="skeleton h-4 w-1/2" />
              <div className="skeleton h-8 w-1/3" />
            </div>
          ))}
        </div>
      )}

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
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-display font-bold text-coral-500">
                      &euro;{dest.price}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 text-xs text-warm-400 font-body mt-3">
                  <Plane className="h-3 w-3" />
                  <span>{dest.fly_from} &rarr; {dest.fly_to}</span>
                  {dest.nights_in_dest > 0 && (
                    <span>&middot; {dest.nights_in_dest} nights</span>
                  )}
                </div>

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
