import { Plane } from 'lucide-react'

export default function Layout({ children }) {
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
        </div>
      </header>

      <main className="flex-1">
        {children}
      </main>

      <footer className="text-center py-3 text-xs font-body text-warm-400">
        v0.5.0
      </footer>
    </div>
  )
}
