import { useState, useEffect } from 'react'
import { Database, Clock, CheckCircle, Trash2, Edit, Plus, Search, Filter, AlertCircle, ChevronUp, ChevronDown, X, Eye } from 'lucide-react'
import { adminApi } from '../api/admin'

const TABS = [
  { id: 'deals', label: 'Deals', icon: Database },
  { id: 'queue', label: 'Queue', icon: Clock },
  { id: 'published', label: 'Published', icon: CheckCircle },
]

const CONTINENTS = [
  { key: '', label: 'All' },
  { key: 'europe', label: 'Europe' },
  { key: 'asia', label: 'Asia' },
  { key: 'africa', label: 'Africa' },
  { key: 'americas', label: 'Americas' },
  { key: 'oceania', label: 'Oceania' },
]

const STRATEGIES = [
  'direct', 'standard', 'nearby_airport', 'day_arbitrage', 'mixed_carrier',
  'hidden_city', 'throwaway', 'open_jaw', 'double_open_jaw', 'back_to_back',
  'split_ticket', 'positioning', 'everywhere'
]

const getSortField = (tab) => tab === 'queue' ? 'position' : tab === 'published' ? 'published_at' : 'found_at'

// Modal component
function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg max-h-[80vh] overflow-y-auto m-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-warm-200">
          <h3 className="text-lg font-semibold text-warm-900">{title}</h3>
          <button onClick={onClose} className="p-1 text-warm-500 hover:text-warm-700"><X className="h-5 w-5" /></button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  )
}

export default function AdminPanel() {
  const [activeTab, setActiveTab] = useState('deals')
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [stats, setStats] = useState({})
  const [pagination, setPagination] = useState({})
  const [selected, setSelected] = useState(new Set())
  const [toast, setToast] = useState(null)
  const [editItem, setEditItem] = useState(null)
  const [editForm, setEditForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [viewItem, setViewItem] = useState(null) // For published detail view
  const [expandedRows, setExpandedRows] = useState(new Set()) // For published expanded rows

  // Filters
  const [filters, setFilters] = useState({
    page: 1,
    limit: 20,
    search: '',
    continent: '',
    country: '',
    min_price: '',
    max_price: '',
    origin: '',
    strategy: '',
    is_direct: null,
    status: '',
    sort: getSortField('deals'),
    order: 'desc'
  })

  useEffect(() => { loadStats() }, [])
  useEffect(() => { loadData() }, [activeTab, filters])

  const loadStats = async () => {
    try { setStats(await adminApi.getStats()) } catch (err) { console.error('Failed to load stats:', err) }
  }

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      let result
      if (activeTab === 'deals') { result = await adminApi.getDeals(filters); setData(result.deals || []) }
      else if (activeTab === 'queue') { result = await adminApi.getQueue(filters); setData(result.queue || []) }
      else if (activeTab === 'published') { result = await adminApi.getPublished(filters); setData(result.published || []) }
      setPagination(result.pagination || {})
    } catch (err) { setError(err.message); setData([]) }
    finally { setLoading(false) }
  }

  const showToast = (message, type = 'success') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3000)
  }

  const handleDelete = async (id, type = activeTab) => {
    if (!confirm('Are you sure you want to delete this item?')) return
    try {
      if (type === 'deals') await adminApi.deleteDeal(id)
      else if (type === 'queue') await adminApi.deleteQueueItem(id)
      else if (type === 'published') await adminApi.deletePublished(id)
      showToast('Item deleted successfully')
      loadData(); loadStats()
    } catch (err) { showToast(err.message, 'error') }
  }

  const handleBulkDelete = async () => {
    if (selected.size === 0) return
    if (!confirm(`Delete ${selected.size} selected items?`)) return
    try {
      await Promise.all([...selected].map(id => {
        if (activeTab === 'deals') return adminApi.deleteDeal(id)
        if (activeTab === 'queue') return adminApi.deleteQueueItem(id)
        if (activeTab === 'published') return adminApi.deletePublished(id)
      }))
      showToast(`${selected.size} items deleted successfully`)
      setSelected(new Set()); loadData(); loadStats()
    } catch (err) { showToast(err.message, 'error') }
  }

  const handleAddToQueue = async (dealId) => {
    try { await adminApi.addToQueue({ deal_id: dealId }); showToast('Deal added to queue'); loadStats() }
    catch (err) { showToast(err.message, 'error') }
  }

  // Edit handlers
  const openEdit = (item, tab) => {
    setEditItem({ ...item, _tab: tab })
    if (tab === 'deals') {
      setEditForm({
        origin: item.origin || '', destination: item.destination || '', price: item.price || '',
        departure_date: item.departure_date || '', nights: item.nights || '', strategy: item.strategy || '',
        is_direct: item.is_direct ? true : false,
        published_telegram: item.published_telegram ? true : false,
        published_twitter: item.published_twitter ? true : false,
        published_blog: item.published_blog ? true : false,
      })
    } else if (tab === 'queue') {
      setEditForm({ position: item.position || 0, status: item.status || 'pending' })
    }
  }

  const handleSaveEdit = async () => {
    setSaving(true)
    try {
      const tab = editItem._tab
      if (tab === 'deals') {
        const payload = { ...editForm, price: Number(editForm.price), nights: Number(editForm.nights) }
        await adminApi.updateDeal(editItem.id, payload)
      } else if (tab === 'queue') {
        await adminApi.updateQueueItem(editItem.id, { position: Number(editForm.position), status: editForm.status })
      }
      showToast('Updated successfully')
      setEditItem(null); loadData()
    } catch (err) { showToast(err.message, 'error') }
    finally { setSaving(false) }
  }

  // Queue reorder
  const handleMoveQueue = async (index, direction) => {
    const swapIndex = index + direction
    if (swapIndex < 0 || swapIndex >= data.length) return
    const newData = [...data]
    ;[newData[index], newData[swapIndex]] = [newData[swapIndex], newData[index]]
    const items = newData.map((item, i) => ({ id: item.id, position: i + 1 }))
    setData(newData)
    try { await adminApi.reorderQueue(items); loadData() }
    catch (err) { showToast(err.message, 'error'); loadData() }
  }

  // Toggle expanded row for published
  const toggleExpanded = (id) => {
    setExpandedRows(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const updateFilter = (key, value) => setFilters(prev => ({ ...prev, [key]: value, page: 1 }))
  const formatDate = (dateStr) => { if (!dateStr) return '-'; try { return new Date(dateStr).toLocaleDateString() } catch { return dateStr } }
  const formatPrice = (price) => price ? `€${price}` : '-'

  const toggleSelect = (id) => {
    const n = new Set(selected); if (n.has(id)) n.delete(id); else n.add(id); setSelected(n)
  }
  const toggleSelectAll = () => {
    setSelected(selected.size === data.length ? new Set() : new Set(data.map(i => i.id)))
  }

  return (
    <div className="space-y-6">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg ${toast.type === 'error' ? 'bg-red-500 text-white' : 'bg-green-500 text-white'}`}>
          {toast.message}
        </div>
      )}

      {/* Edit Modal - Deals */}
      {editItem && editItem._tab === 'deals' && (
        <Modal title="Edit Deal" onClose={() => setEditItem(null)}>
          <div className="space-y-3">
            {['origin', 'destination', 'departure_date'].map(f => (
              <div key={f}>
                <label className="block text-sm font-medium text-warm-700 mb-1 capitalize">{f.replace('_', ' ')}</label>
                <input type="text" value={editForm[f]} onChange={e => setEditForm(p => ({ ...p, [f]: e.target.value }))}
                  className="w-full px-3 py-2 border border-warm-200 rounded-lg text-sm focus:ring-2 focus:ring-coral-500" />
              </div>
            ))}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-warm-700 mb-1">Price</label>
                <input type="number" value={editForm.price} onChange={e => setEditForm(p => ({ ...p, price: e.target.value }))}
                  className="w-full px-3 py-2 border border-warm-200 rounded-lg text-sm focus:ring-2 focus:ring-coral-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-warm-700 mb-1">Nights</label>
                <input type="number" value={editForm.nights} onChange={e => setEditForm(p => ({ ...p, nights: e.target.value }))}
                  className="w-full px-3 py-2 border border-warm-200 rounded-lg text-sm focus:ring-2 focus:ring-coral-500" />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-warm-700 mb-1">Strategy</label>
              <select value={editForm.strategy} onChange={e => setEditForm(p => ({ ...p, strategy: e.target.value }))}
                className="w-full px-3 py-2 border border-warm-200 rounded-lg text-sm focus:ring-2 focus:ring-coral-500">
                <option value="">Select...</option>
                {STRATEGIES.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
              </select>
            </div>
            {['is_direct', 'published_telegram', 'published_twitter', 'published_blog'].map(f => (
              <label key={f} className="flex items-center gap-2 text-sm text-warm-700">
                <input type="checkbox" checked={editForm[f] || false} onChange={e => setEditForm(p => ({ ...p, [f]: e.target.checked }))}
                  className="rounded border-warm-300 text-coral-600 focus:ring-coral-500" />
                {f.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
              </label>
            ))}
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setEditItem(null)} className="px-4 py-2 text-sm border border-warm-200 rounded-lg hover:bg-warm-50">Cancel</button>
              <button onClick={handleSaveEdit} disabled={saving}
                className="px-4 py-2 text-sm bg-coral-500 text-white rounded-lg hover:bg-coral-600 disabled:opacity-50">
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Edit Modal - Queue */}
      {editItem && editItem._tab === 'queue' && (
        <Modal title="Edit Queue Item" onClose={() => setEditItem(null)}>
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-warm-700 mb-1">Position</label>
              <input type="number" value={editForm.position} onChange={e => setEditForm(p => ({ ...p, position: e.target.value }))}
                className="w-full px-3 py-2 border border-warm-200 rounded-lg text-sm focus:ring-2 focus:ring-coral-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-warm-700 mb-1">Status</label>
              <select value={editForm.status} onChange={e => setEditForm(p => ({ ...p, status: e.target.value }))}
                className="w-full px-3 py-2 border border-warm-200 rounded-lg text-sm focus:ring-2 focus:ring-coral-500">
                <option value="pending">Pending</option>
                <option value="ready">Ready</option>
                <option value="skipped">Skipped</option>
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setEditItem(null)} className="px-4 py-2 text-sm border border-warm-200 rounded-lg hover:bg-warm-50">Cancel</button>
              <button onClick={handleSaveEdit} disabled={saving}
                className="px-4 py-2 text-sm bg-coral-500 text-white rounded-lg hover:bg-coral-600 disabled:opacity-50">
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* View Modal - Published (all copy types) */}
      {viewItem && (
        <Modal title={`Published: ${viewItem.origin}→${viewItem.destination}`} onClose={() => setViewItem(null)}>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <span className="text-warm-600">Price:</span><span className="font-medium">{formatPrice(viewItem.price)}</span>
              <span className="text-warm-600">Date:</span><span>{formatDate(viewItem.departure_date)}</span>
              <span className="text-warm-600">Published:</span><span>{formatDate(viewItem.published_at)}</span>
            </div>
            {[
              { key: 'telegram_copy', label: 'Telegram Copy' },
              { key: 'twitter_copy', label: 'Twitter Copy' },
              { key: 'blog_copy', label: 'Blog Copy' },
            ].map(({ key, label }) => (
              <div key={key}>
                <label className="block text-sm font-medium text-warm-700 mb-1">{label}</label>
                <pre className="bg-warm-50 p-3 rounded-lg text-sm text-warm-800 whitespace-pre-wrap max-h-40 overflow-y-auto border border-warm-200">
                  {viewItem[key] || '(empty)'}
                </pre>
              </div>
            ))}
          </div>
        </Modal>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { icon: Database, color: 'blue', label: 'Total Deals', value: stats.total_deals },
          { icon: Clock, color: 'amber', label: 'Queue', value: stats.total_queue },
          { icon: CheckCircle, color: 'green', label: 'Published', value: stats.total_published },
          { icon: Plus, color: 'coral', label: 'Today', value: stats.deals_today },
        ].map(({ icon: Icon, color, label, value }) => (
          <div key={label} className="bg-white rounded-lg border border-warm-200 p-4">
            <div className="flex items-center gap-3">
              <div className={`p-2 bg-${color}-100 rounded-lg`}><Icon className={`h-5 w-5 text-${color}-600`} /></div>
              <div>
                <p className="text-sm text-warm-600">{label}</p>
                <p className="text-2xl font-bold text-warm-900">{value || 0}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-warm-200">
        <nav className="flex space-x-8">
          {TABS.map((tab) => {
            const Icon = tab.icon
            return (
              <button key={tab.id} onClick={() => {
                setActiveTab(tab.id); setSelected(new Set()); setExpandedRows(new Set())
                setFilters(prev => ({ ...prev, page: 1, sort: getSortField(tab.id), order: tab.id === 'queue' ? 'asc' : 'desc' }))
              }} className={`flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === tab.id ? 'border-coral-500 text-coral-600' : 'border-transparent text-warm-500 hover:text-warm-700 hover:border-warm-300'
              }`}>
                <Icon className="h-4 w-4" />
                {tab.label}
                <span className="ml-1 text-xs px-2 py-1 bg-warm-100 rounded-full">
                  {tab.id === 'deals' && (stats.total_deals || 0)}
                  {tab.id === 'queue' && (stats.total_queue || 0)}
                  {tab.id === 'published' && (stats.total_published || 0)}
                </span>
              </button>
            )
          })}
        </nav>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg border border-warm-200 p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-warm-400" />
            <input type="text" placeholder="Search destinations..." value={filters.search}
              onChange={(e) => updateFilter('search', e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-warm-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-coral-500 focus:border-coral-500" />
          </div>
          <select value={filters.continent} onChange={(e) => updateFilter('continent', e.target.value)}
            className="px-3 py-2 border border-warm-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-coral-500 focus:border-coral-500">
            {CONTINENTS.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
          </select>
          <input type="text" placeholder="Origin city..." value={filters.origin}
            onChange={(e) => updateFilter('origin', e.target.value)}
            className="px-3 py-2 border border-warm-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-coral-500 focus:border-coral-500" />
          <div className="flex gap-2">
            <input type="number" placeholder="Min €" value={filters.min_price} onChange={(e) => updateFilter('min_price', e.target.value)}
              className="w-1/2 px-2 py-2 border border-warm-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-coral-500 focus:border-coral-500" />
            <input type="number" placeholder="Max €" value={filters.max_price} onChange={(e) => updateFilter('max_price', e.target.value)}
              className="w-1/2 px-2 py-2 border border-warm-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-coral-500 focus:border-coral-500" />
          </div>
          <select value={filters.strategy} onChange={(e) => updateFilter('strategy', e.target.value)}
            className="px-3 py-2 border border-warm-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-coral-500 focus:border-coral-500">
            <option value="">All strategies</option>
            {STRATEGIES.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
          </select>
          {activeTab === 'queue' && (
            <select value={filters.status} onChange={(e) => updateFilter('status', e.target.value)}
              className="px-3 py-2 border border-warm-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-coral-500 focus:border-coral-500">
              <option value="">All status</option>
              <option value="pending">Pending</option>
              <option value="ready">Ready</option>
              <option value="skipped">Skipped</option>
            </select>
          )}
        </div>
      </div>

      {/* Actions Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {data.length > 0 && (
            <label className="flex items-center gap-2 text-sm text-warm-600">
              <input type="checkbox" checked={selected.size === data.length && data.length > 0} onChange={toggleSelectAll}
                className="rounded border-warm-300 text-coral-600 focus:ring-coral-500" />
              Select all ({data.length})
            </label>
          )}
          {selected.size > 0 && (
            <button onClick={handleBulkDelete}
              className="flex items-center gap-2 px-3 py-2 bg-red-500 text-white rounded-lg text-sm hover:bg-red-600 transition">
              <Trash2 className="h-4 w-4" /> Delete ({selected.size})
            </button>
          )}
        </div>
        <div className="text-sm text-warm-500">{pagination.total || 0} total items</div>
      </div>

      {/* Data Table */}
      <div className="bg-white rounded-lg border border-warm-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-coral-500 mx-auto mb-4"></div>
            <p className="text-warm-500">Loading...</p>
          </div>
        ) : error ? (
          <div className="p-8 text-center">
            <AlertCircle className="h-8 w-8 text-red-500 mx-auto mb-4" />
            <p className="text-red-600 mb-4">{error}</p>
            <button onClick={loadData} className="px-4 py-2 bg-coral-500 text-white rounded-lg hover:bg-coral-600 transition">Retry</button>
          </div>
        ) : data.length === 0 ? (
          <div className="p-8 text-center text-warm-500">No {activeTab} found</div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-warm-50">
                  <tr>
                    <th className="w-12 p-4">
                      <input type="checkbox" checked={selected.size === data.length && data.length > 0} onChange={toggleSelectAll}
                        className="rounded border-warm-300 text-coral-600 focus:ring-coral-500" />
                    </th>
                    {activeTab === 'deals' && <>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">ID</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Origin</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Destination</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Country</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Price</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Date</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Nights</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Strategy</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Direct?</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Found At</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Actions</th>
                    </>}
                    {activeTab === 'queue' && <>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Pos</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Reorder</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Origin→Dest</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Price</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Date</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Nights</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Status</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Telegram Copy</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Created</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Actions</th>
                    </>}
                    {activeTab === 'published' && <>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">ID</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Origin→Dest</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Price</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Date</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Telegram</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Twitter</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Published</th>
                      <th className="text-left p-4 text-sm font-medium text-warm-700">Actions</th>
                    </>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-warm-200">
                  {data.map((item, index) => (
                    <>
                      <tr key={item.id} className="hover:bg-warm-50">
                        <td className="p-4">
                          <input type="checkbox" checked={selected.has(item.id)} onChange={() => toggleSelect(item.id)}
                            className="rounded border-warm-300 text-coral-600 focus:ring-coral-500" />
                        </td>
                        {activeTab === 'deals' && <>
                          <td className="p-4 text-sm text-warm-900">{item.id}</td>
                          <td className="p-4 text-sm text-warm-900">{item.origin}</td>
                          <td className="p-4 text-sm text-warm-900">{item.destination}</td>
                          <td className="p-4 text-sm text-warm-600">{item.country}</td>
                          <td className="p-4 text-sm font-medium text-warm-900">{formatPrice(item.price)}</td>
                          <td className="p-4 text-sm text-warm-600">{formatDate(item.departure_date)}</td>
                          <td className="p-4 text-sm text-warm-600">{item.nights}</td>
                          <td className="p-4 text-sm text-warm-600 capitalize">{item.strategy?.replace('_', ' ')}</td>
                          <td className="p-4 text-sm">{item.is_direct ? '✓' : '✗'}</td>
                          <td className="p-4 text-sm text-warm-600">{formatDate(item.found_at)}</td>
                          <td className="p-4">
                            <div className="flex items-center gap-2">
                              <button onClick={() => openEdit(item, 'deals')} className="p-1 text-blue-600 hover:text-blue-800 transition" title="Edit"><Edit className="h-4 w-4" /></button>
                              <button onClick={() => handleAddToQueue(item.id)} className="p-1 text-green-600 hover:text-green-800 transition" title="Add to Queue"><Plus className="h-4 w-4" /></button>
                              <button onClick={() => handleDelete(item.id)} className="p-1 text-red-600 hover:text-red-800 transition" title="Delete"><Trash2 className="h-4 w-4" /></button>
                            </div>
                          </td>
                        </>}
                        {activeTab === 'queue' && <>
                          <td className="p-4 text-sm font-medium text-warm-900">{item.position}</td>
                          <td className="p-4">
                            <div className="flex flex-col gap-1">
                              <button onClick={() => handleMoveQueue(index, -1)} disabled={index === 0}
                                className="p-0.5 text-warm-500 hover:text-warm-800 disabled:opacity-30 disabled:cursor-not-allowed" title="Move up">
                                <ChevronUp className="h-4 w-4" />
                              </button>
                              <button onClick={() => handleMoveQueue(index, 1)} disabled={index === data.length - 1}
                                className="p-0.5 text-warm-500 hover:text-warm-800 disabled:opacity-30 disabled:cursor-not-allowed" title="Move down">
                                <ChevronDown className="h-4 w-4" />
                              </button>
                            </div>
                          </td>
                          <td className="p-4 text-sm text-warm-900">{item.origin}→{item.destination}</td>
                          <td className="p-4 text-sm font-medium text-warm-900">{formatPrice(item.price)}</td>
                          <td className="p-4 text-sm text-warm-600">{formatDate(item.departure_date)}</td>
                          <td className="p-4 text-sm text-warm-600">{item.nights}</td>
                          <td className="p-4">
                            <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${
                              item.status === 'ready' ? 'bg-green-100 text-green-800' :
                              item.status === 'pending' ? 'bg-yellow-100 text-yellow-800' : 'bg-gray-100 text-gray-800'
                            }`}>{item.status}</span>
                          </td>
                          <td className="p-4 text-sm text-warm-600 max-w-xs truncate">{item.telegram_copy?.substring(0, 100) || '-'}...</td>
                          <td className="p-4 text-sm text-warm-600">{formatDate(item.created_at)}</td>
                          <td className="p-4">
                            <div className="flex items-center gap-2">
                              <button onClick={() => openEdit(item, 'queue')} className="p-1 text-blue-600 hover:text-blue-800 transition" title="Edit"><Edit className="h-4 w-4" /></button>
                              <button onClick={() => handleDelete(item.id, 'queue')} className="p-1 text-red-600 hover:text-red-800 transition" title="Delete"><Trash2 className="h-4 w-4" /></button>
                            </div>
                          </td>
                        </>}
                        {activeTab === 'published' && <>
                          <td className="p-4 text-sm text-warm-900">{item.id}</td>
                          <td className="p-4 text-sm text-warm-900">{item.origin}→{item.destination}</td>
                          <td className="p-4 text-sm font-medium text-warm-900">{formatPrice(item.price)}</td>
                          <td className="p-4 text-sm text-warm-600">{formatDate(item.departure_date)}</td>
                          <td className="p-4 text-sm">{item.telegram_sent ? '✓' : '✗'}</td>
                          <td className="p-4 text-sm">{item.twitter_sent ? '✓' : '✗'}</td>
                          <td className="p-4 text-sm text-warm-600">{formatDate(item.published_at)}</td>
                          <td className="p-4">
                            <div className="flex items-center gap-2">
                              <button onClick={() => toggleExpanded(item.id)} className="p-1 text-blue-600 hover:text-blue-800 transition" title="Show copies">
                                <Eye className="h-4 w-4" />
                              </button>
                              <button onClick={() => setViewItem(item)} className="p-1 text-blue-600 hover:text-blue-800 transition" title="View detail"><Edit className="h-4 w-4" /></button>
                              <button onClick={() => handleDelete(item.id, 'published')} className="p-1 text-red-600 hover:text-red-800 transition" title="Delete"><Trash2 className="h-4 w-4" /></button>
                            </div>
                          </td>
                        </>}
                      </tr>
                      {/* Expanded row for published copies */}
                      {activeTab === 'published' && expandedRows.has(item.id) && (
                        <tr key={`${item.id}-expanded`} className="bg-warm-50">
                          <td colSpan={9} className="p-4">
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                              {[
                                { key: 'telegram_copy', label: '📱 Telegram' },
                                { key: 'twitter_copy', label: '🐦 Twitter' },
                                { key: 'blog_copy', label: '📝 Blog' },
                              ].map(({ key, label }) => (
                                <div key={key}>
                                  <p className="text-sm font-medium text-warm-700 mb-1">{label}</p>
                                  <pre className="bg-white p-2 rounded border border-warm-200 text-xs text-warm-800 whitespace-pre-wrap max-h-32 overflow-y-auto">
                                    {item[key] || '(empty)'}
                                  </pre>
                                </div>
                              ))}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {pagination.total_pages > 1 && (
              <div className="border-t border-warm-200 px-4 py-3 flex items-center justify-between">
                <div className="text-sm text-warm-500">
                  Page {pagination.current_page} of {pagination.total_pages} ({pagination.total} total)
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => updateFilter('page', pagination.current_page - 1)} disabled={pagination.current_page <= 1}
                    className="px-3 py-2 text-sm border border-warm-200 rounded-lg hover:bg-warm-50 disabled:opacity-50 disabled:cursor-not-allowed">Previous</button>
                  <button onClick={() => updateFilter('page', pagination.current_page + 1)} disabled={pagination.current_page >= pagination.total_pages}
                    className="px-3 py-2 text-sm border border-warm-200 rounded-lg hover:bg-warm-50 disabled:opacity-50 disabled:cursor-not-allowed">Next</button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
