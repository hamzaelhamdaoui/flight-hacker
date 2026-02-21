import { useState } from 'react'
import Layout from './components/Layout'
import SearchForm from './components/SearchForm'
import ResultsView from './components/ResultsView'
import ExploreView from './components/ExploreView'
import { useSearch } from './hooks/useSearch'

export default function App() {
  const [activeTab, setActiveTab] = useState('search')
  const { results, loading, error, search, clearResults, progress, searchStatus, currentStrategy } = useSearch()

  const handleSearch = (params) => {
    search({ ...params, _mode: 'search' })
  }

  return (
    <Layout activeTab={activeTab} onTabChange={setActiveTab}>
      {activeTab === 'search' && (
        <section className="mx-auto max-w-6xl px-4 py-8 pb-24 md:pb-8">
          {/* Hero — before first search */}
          {!results && !loading && (
            <div className="text-center mb-8">
              <h2 className="font-display text-3xl sm:text-5xl font-bold text-warm-900 mb-3 tracking-tight">
                Hack your next flight
              </h2>
              <p className="font-body text-lg text-warm-500 max-w-2xl mx-auto">
                12 strategies to find prices that Google Flights won't show you.
                Hidden cities, split tickets, throwaway returns, and more.
              </p>
            </div>
          )}

          {/* Search form */}
          <div className={`card ${!results && !loading ? 'p-5 sm:p-8 max-w-3xl mx-auto' : 'p-5 sm:p-6 max-w-3xl mx-auto mb-6'}`}>
            <SearchForm onSearch={handleSearch} loading={loading} />
          </div>

          {/* Error */}
          {error && (
            <div className="card border-red-200 bg-red-50 p-4 mt-6 max-w-3xl mx-auto">
              <p className="text-sm text-red-600 font-body">{error}</p>
              <button onClick={clearResults} className="mt-2 text-sm font-display font-medium text-red-500 hover:text-red-700 transition">
                Try again
              </button>
            </div>
          )}

          {/* Streaming progress */}
          {loading && (
            <div className="card p-6 mb-6 max-w-3xl mx-auto mt-6">
              <div className="flex items-center gap-4 mb-4">
                <div className="w-8 h-8 animate-spin rounded-full border-2 border-coral-200 border-t-coral-500 flex-shrink-0" />
                <div className="flex-1">
                  <h3 className="font-display text-base font-semibold text-warm-800">Searching flights...</h3>
                  <p className="text-sm text-warm-500 font-body">{searchStatus || 'Starting strategies...'}</p>
                </div>
                {progress > 0 && <span className="font-display font-bold text-coral-500 text-lg">{progress}%</span>}
              </div>
              {progress > 0 && (
                <div className="w-full bg-warm-200 rounded-full h-2">
                  <div className="bg-coral-500 h-2 rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
                </div>
              )}
            </div>
          )}

          {/* Search results */}
          {results && (
            <div className={loading ? 'mt-4' : 'mt-6'}>
              <ResultsView data={results} onClear={clearResults} isStreaming={loading} />
            </div>
          )}
        </section>
      )}

      {activeTab === 'explore' && <ExploreView />}
    </Layout>
  )
}
