import { useState } from 'react'
import Layout from './components/Layout'
import SearchForm from './components/SearchForm'
import ResultsView from './components/ResultsView'
import ExploreView from './components/ExploreView'
import { useSearch } from './hooks/useSearch'

export default function App() {
  const [activeTab, setActiveTab] = useState('search')
  const { results, loading, error, search, clearResults } = useSearch()

  return (
    <Layout activeTab={activeTab} onTabChange={setActiveTab}>
      {activeTab === 'search' && (
        <section className="mx-auto max-w-6xl px-4 py-8 pb-24 md:pb-8">
          {!results && (
            <>
              {/* Hero */}
              <div className="text-center mb-8">
                <h2 className="font-display text-3xl sm:text-5xl font-bold text-warm-900 mb-3 tracking-tight">
                  Hack your next flight
                </h2>
                <p className="font-body text-lg text-warm-500 max-w-2xl mx-auto">
                  12 strategies to find prices that Google Flights won't show you.
                  Hidden cities, split tickets, throwaway returns, and more.
                </p>
              </div>

              {/* Search form card */}
              <div className="card p-5 sm:p-8 max-w-3xl mx-auto">
                <SearchForm onSearch={search} loading={loading} />
              </div>
            </>
          )}

          {/* Error state */}
          {error && (
            <div className="card border-red-200 bg-red-50 p-4 mt-6 max-w-3xl mx-auto">
              <p className="text-sm text-red-600 font-body">{error}</p>
              <button
                onClick={clearResults}
                className="mt-2 text-sm font-display font-medium text-red-500 hover:text-red-700 transition"
              >
                Try again
              </button>
            </div>
          )}

          {/* Loading state */}
          {loading && !results && (
            <div className="mt-8 max-w-3xl mx-auto space-y-4">
              <div className="card p-4 flex items-center gap-3">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-coral-500 border-t-transparent" />
                <span className="font-body text-warm-600">
                  Running strategies... This may take a moment.
                </span>
              </div>
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="card p-5 space-y-3">
                  <div className="flex justify-between">
                    <div className="skeleton h-6 w-24" />
                    <div className="skeleton h-8 w-16" />
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="skeleton h-4 w-12" />
                    <div className="skeleton h-2 flex-1" />
                    <div className="skeleton h-4 w-12" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Results */}
          {results && (
            <div className="mt-6">
              <ResultsView data={results} onClear={clearResults} />
            </div>
          )}
        </section>
      )}

      {activeTab === 'explore' && <ExploreView />}
    </Layout>
  )
}
