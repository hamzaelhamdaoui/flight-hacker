import { useState, useRef, useEffect, useCallback } from 'react'
import { MapPin, X } from 'lucide-react'
import { fetchLocations } from '../api/client'

export default function LocationInput({ label, value, onChange, placeholder, allowAnywhere = false }) {
  const [query, setQuery] = useState(value || '')
  const [suggestions, setSuggestions] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const timerRef = useRef(null)
  const wrapperRef = useRef(null)

  useEffect(() => {
    if (!value) setQuery('')
  }, [value])

  useEffect(() => {
    function handleClickOutside(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const fetchSuggestions = useCallback(async (term) => {
    if (!term || term.length < 2) {
      setSuggestions([])
      return
    }
    setLoading(true)
    try {
      const data = await fetchLocations(term)
      setSuggestions(data.results || [])
    } catch {
      setSuggestions([])
    } finally {
      setLoading(false)
    }
  }, [])

  const handleInputChange = (e) => {
    const val = e.target.value
    setQuery(val)
    setOpen(true)
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => fetchSuggestions(val), 300)
  }

  const handleSelect = (loc) => {
    const display = loc.code ? `${loc.name} (${loc.code})` : loc.name
    setQuery(display)
    onChange(loc.code || loc.name)
    setOpen(false)
  }

  const handleSelectAnywhere = () => {
    setQuery('Anywhere')
    onChange('')
    setOpen(false)
  }

  const handleClear = () => {
    setQuery('')
    onChange('')
    setSuggestions([])
  }

  return (
    <div ref={wrapperRef} className="relative">
      <label className="block text-sm font-display font-medium text-warm-600 mb-1.5">
        {label}
      </label>
      <div className="relative">
        <MapPin className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-warm-400" />
        <input
          type="text"
          value={query}
          onChange={handleInputChange}
          onFocus={() => { if (query.length >= 2) setOpen(true) }}
          placeholder={placeholder}
          className="input-field pl-10 pr-9"
        />
        {query && (
          <button
            onClick={handleClear}
            className="absolute right-3 top-1/2 -translate-y-1/2 p-0.5 rounded-full text-warm-400 hover:text-warm-600 transition"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
      {open && (suggestions.length > 0 || allowAnywhere || loading) && (
        <div className="absolute top-full left-0 right-0 mt-1.5 bg-white border border-warm-200 rounded-xl shadow-xl z-40 overflow-hidden max-h-64 overflow-y-auto">
          {loading && (
            <div className="px-4 py-3 text-sm text-warm-400 font-body">Searching...</div>
          )}
          {allowAnywhere && (
            <button
              onClick={handleSelectAnywhere}
              className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-coral-50 transition border-b border-warm-100"
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-coral-100 text-coral-500">
                <MapPin className="h-4 w-4" />
              </div>
              <div>
                <div className="text-sm font-display font-medium text-coral-600">Anywhere</div>
                <div className="text-xs text-warm-400">Search all destinations</div>
              </div>
            </button>
          )}
          {suggestions.map((loc) => (
            <button
              key={loc.id || loc.code}
              onClick={() => handleSelect(loc)}
              className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-warm-50 transition"
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-warm-100 text-warm-500">
                <MapPin className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-display font-medium text-warm-800 truncate">
                  {loc.name} {loc.code ? `(${loc.code})` : ''}
                </div>
                <div className="text-xs text-warm-400 truncate">
                  {[loc.city !== loc.name && loc.city, loc.country].filter(Boolean).join(', ') || loc.type}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
