import { Plane, Search, Compass } from 'lucide-react'

export default function Layout({ children, activeTab, onTabChange }) {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-warm-200 bg-white/80 backdrop-blur-md sticky top-0 z-50">
        <div className="mx-auto max-w-6xl px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-coral-500 shadow-lg shadow-coral-500/20">
              <Plane className="h-5 w-5 text-white" strokeWidth={2.5} />
            </div>
            <div>
              <h1 className="font-display text-xl font-bold tracking-tight text-warm-900">
                Flight Hacker
              </h1>
              <p className="hidden sm:block text-xs font-body text-warm-500 -mt-0.5">
                Travel hacking, simplified
              </p>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-1">
            <button
              onClick={() => onTabChange('search')}
              className={`flex items-center gap-2 rounded-lg px-4 py-2 font-display text-sm font-medium transition ${
                activeTab === 'search'
                  ? 'bg-coral-50 text-coral-600'
                  : 'text-warm-500 hover:text-warm-700 hover:bg-warm-100'
              }`}
            >
              <Search className="h-4 w-4" />
              Search
            </button>
            <button
              onClick={() => onTabChange('explore')}
              className={`flex items-center gap-2 rounded-lg px-4 py-2 font-display text-sm font-medium transition ${
                activeTab === 'explore'
                  ? 'bg-coral-50 text-coral-600'
                  : 'text-warm-500 hover:text-warm-700 hover:bg-warm-100'
              }`}
            >
              <Compass className="h-4 w-4" />
              Explore
            </button>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        {children}
      </main>

      <footer className="text-center py-3 pb-20 md:pb-3 text-xs font-body text-warm-400">
        v0.3.2
      </footer>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 bg-white border-t border-warm-200 z-50 safe-area-pb">
        <div className="flex">
          <button
            onClick={() => onTabChange('search')}
            className={`flex-1 flex flex-col items-center gap-1 py-3 transition ${
              activeTab === 'search' ? 'text-coral-500' : 'text-warm-400'
            }`}
          >
            <Search className="h-5 w-5" />
            <span className="text-[11px] font-display font-medium">Search</span>
          </button>
          <button
            onClick={() => onTabChange('explore')}
            className={`flex-1 flex flex-col items-center gap-1 py-3 transition ${
              activeTab === 'explore' ? 'text-coral-500' : 'text-warm-400'
            }`}
          >
            <Compass className="h-5 w-5" />
            <span className="text-[11px] font-display font-medium">Explore</span>
          </button>
        </div>
      </nav>
    </div>
  )
}
