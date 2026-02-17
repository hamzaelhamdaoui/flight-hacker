import { Calendar, CalendarDays, CalendarRange, TrendingDown, Sun } from 'lucide-react'

const TABS = [
  { id: 'exact', label: 'Exact', Icon: Calendar },
  { id: 'range', label: 'Range', Icon: CalendarRange },
  { id: 'month', label: 'Month', Icon: CalendarDays },
  { id: 'cheapest', label: 'Cheapest', Icon: TrendingDown },
  { id: 'weekends', label: 'Weekends', Icon: Sun },
]

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
]

export default function DateFlexPicker({ mode, onChange, values, onValuesChange }) {
  const handleValueChange = (key, val) => {
    onValuesChange({ ...values, [key]: val })
  }

  return (
    <div>
      <label className="block text-sm font-display font-medium text-warm-600 mb-2">
        Date Flexibility
      </label>

      {/* Tab strip */}
      <div className="flex gap-1 p-1 bg-warm-100 rounded-xl mb-4 overflow-x-auto">
        {TABS.map(({ id, label, Icon }) => (
          <button
            type="button"
            key={id}
            onClick={() => onChange(id)}
            className={`flex items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-display font-medium transition ${
              mode === id
                ? 'bg-white text-coral-600 shadow-sm'
                : 'text-warm-500 hover:text-warm-700'
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </div>

      {/* Mode-specific inputs */}
      <div className="space-y-3">
        {mode === 'exact' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-body text-warm-500 mb-1">Departure</label>
              <input
                type="date"
                value={values.dateFrom || ''}
                onChange={(e) => handleValueChange('dateFrom', e.target.value)}
                className="input-field text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-body text-warm-500 mb-1">Return</label>
              <input
                type="date"
                value={values.returnFrom || ''}
                onChange={(e) => handleValueChange('returnFrom', e.target.value)}
                className="input-field text-sm"
              />
            </div>
          </div>
        )}

        {mode === 'range' && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-body text-warm-500 mb-1">Earliest departure</label>
                <input
                  type="date"
                  value={values.dateFrom || ''}
                  onChange={(e) => handleValueChange('dateFrom', e.target.value)}
                  className="input-field text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-body text-warm-500 mb-1">Latest departure</label>
                <input
                  type="date"
                  value={values.dateTo || ''}
                  onChange={(e) => handleValueChange('dateTo', e.target.value)}
                  className="input-field text-sm"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-body text-warm-500 mb-1">
                  Min nights: {values.nightsMin || 2}
                </label>
                <input
                  type="range"
                  min="1"
                  max="30"
                  value={values.nightsMin || 2}
                  onChange={(e) => handleValueChange('nightsMin', parseInt(e.target.value))}
                  className="w-full accent-coral-500"
                />
              </div>
              <div>
                <label className="block text-xs font-body text-warm-500 mb-1">
                  Max nights: {values.nightsMax || 7}
                </label>
                <input
                  type="range"
                  min="1"
                  max="30"
                  value={values.nightsMax || 7}
                  onChange={(e) => handleValueChange('nightsMax', parseInt(e.target.value))}
                  className="w-full accent-coral-500"
                />
              </div>
            </div>
          </>
        )}

        {mode === 'month' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-body text-warm-500 mb-1">Month</label>
              <select
                value={values.month || new Date().getMonth() + 1}
                onChange={(e) => handleValueChange('month', parseInt(e.target.value))}
                className="input-field text-sm"
              >
                {MONTHS.map((m, i) => (
                  <option key={i} value={i + 1}>{m}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-body text-warm-500 mb-1">Year</label>
              <select
                value={values.year || new Date().getFullYear()}
                onChange={(e) => handleValueChange('year', parseInt(e.target.value))}
                className="input-field text-sm"
              >
                <option value={2026}>2026</option>
                <option value={2027}>2027</option>
              </select>
            </div>
          </div>
        )}

        {mode === 'cheapest' && (
          <div>
            <label className="block text-xs font-body text-warm-500 mb-1">
              Search next {values.monthsAhead || 3} months
            </label>
            <input
              type="range"
              min="1"
              max="6"
              value={values.monthsAhead || 3}
              onChange={(e) => handleValueChange('monthsAhead', parseInt(e.target.value))}
              className="w-full accent-coral-500"
            />
            <div className="flex justify-between text-xs text-warm-400 mt-1">
              <span>1 month</span>
              <span>6 months</span>
            </div>
          </div>
        )}

        {mode === 'weekends' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-body text-warm-500 mb-1">From</label>
              <input
                type="date"
                value={values.weekendsFrom || ''}
                onChange={(e) => handleValueChange('weekendsFrom', e.target.value)}
                className="input-field text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-body text-warm-500 mb-1">To</label>
              <input
                type="date"
                value={values.weekendsTo || ''}
                onChange={(e) => handleValueChange('weekendsTo', e.target.value)}
                className="input-field text-sm"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
