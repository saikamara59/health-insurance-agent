import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'

function getInitials(name) {
  return name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

const AVATAR_COLORS = [
  'bg-primary', 'bg-secondary', 'bg-tertiary',
  'bg-primary-container', 'bg-tertiary-container',
]

function avatarColor(name) {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]
}

const INCOME_LABELS = { low: 'Low', medium: 'Medium', high: 'High' }

const PAGE_SIZE = 10

export default function ClientListPage() {
  const navigate = useNavigate()

  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Filters
  const [filterZip, setFilterZip] = useState('')
  const [filterAge, setFilterAge] = useState('')
  const [filterIncome, setFilterIncome] = useState('')
  const [appliedFilters, setAppliedFilters] = useState({ zip: '', age: '', income: '' })

  // Pagination
  const [page, setPage] = useState(1)

  // Add Client modal
  const [showAddModal, setShowAddModal] = useState(false)
  const [newClient, setNewClient] = useState({
    full_name: '', zip_code: '', age: '', income_level: 'medium',
  })
  const [addError, setAddError] = useState('')
  const [addLoading, setAddLoading] = useState(false)

  useEffect(() => {
    loadClients()
  }, [])

  async function loadClients() {
    setLoading(true)
    try {
      const data = await api.get('/clients')
      setClients(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const filteredClients = useMemo(() => {
    return clients.filter((c) => {
      if (appliedFilters.zip && !c.zip_code.startsWith(appliedFilters.zip)) return false
      if (appliedFilters.income && c.income_level !== appliedFilters.income) return false
      if (appliedFilters.age) {
        const [min, max] = appliedFilters.age.split('-').map(Number)
        if (c.age < min || c.age > max) return false
      }
      return true
    })
  }, [clients, appliedFilters])

  const totalPages = Math.max(1, Math.ceil(filteredClients.length / PAGE_SIZE))
  const pagedClients = filteredClients.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  function applyFilters() {
    setAppliedFilters({ zip: filterZip, age: filterAge, income: filterIncome })
    setPage(1)
  }

  async function handleAddClient(e) {
    e.preventDefault()
    setAddError('')
    setAddLoading(true)
    try {
      await api.post('/clients', {
        full_name: newClient.full_name,
        zip_code: newClient.zip_code,
        age: parseInt(newClient.age, 10),
        income_level: newClient.income_level,
      })
      setShowAddModal(false)
      setNewClient({ full_name: '', zip_code: '', age: '', income_level: 'medium' })
      await loadClients()
    } catch (err) {
      setAddError(err.message)
    } finally {
      setAddLoading(false)
    }
  }

  async function handleDeleteClient(id) {
    if (!confirm('Delete this client?')) return
    try {
      await api.del(`/clients/${id}`)
      setClients((prev) => prev.filter((c) => c.id !== id))
    } catch (err) {
      alert(err.message)
    }
  }

  // Summary stats (derived)
  const newLeadsCount = clients.filter((c) => {
    const created = new Date(c.created_at)
    const weekAgo = new Date()
    weekAgo.setDate(weekAgo.getDate() - 7)
    return created >= weekAgo
  }).length

  return (
    <div>
      {/* Page Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-headline text-3xl font-bold text-on-surface">Client Portfolio</h1>
          <p className="text-on-surface-variant text-sm mt-1">{clients.length} total clients</p>
        </div>
        <button
          className="flex items-center gap-2 bg-primary hover:bg-primary-container text-on-primary font-semibold px-6 py-3 rounded-xl transition-colors shadow-sm"
          onClick={() => setShowAddModal(true)}
        >
          <span className="material-symbols-outlined text-lg">add</span>
          Add Client
        </button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-surface-container-lowest rounded-xl p-6 border border-outline-variant">
          <div className="flex items-center gap-3 mb-2">
            <span className="material-symbols-outlined text-primary text-2xl">person_add</span>
            <span className="text-sm font-medium text-on-surface-variant">New Leads (7d)</span>
          </div>
          <p className="text-3xl font-bold text-on-surface font-headline">{newLeadsCount}</p>
        </div>
        <div className="bg-surface-container-lowest rounded-xl p-6 border border-outline-variant">
          <div className="flex items-center gap-3 mb-2">
            <span className="material-symbols-outlined text-secondary text-2xl">analytics</span>
            <span className="text-sm font-medium text-on-surface-variant">Analysis Score Avg</span>
          </div>
          <p className="text-3xl font-bold text-on-surface font-headline">--</p>
        </div>
        <div className="bg-surface-container-lowest rounded-xl p-6 border border-outline-variant">
          <div className="flex items-center gap-3 mb-2">
            <span className="material-symbols-outlined text-error text-2xl">warning</span>
            <span className="text-sm font-medium text-on-surface-variant">Urgent Renewals</span>
          </div>
          <p className="text-3xl font-bold text-on-surface font-headline">--</p>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-surface-container-lowest rounded-xl p-6 border border-outline-variant mb-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
              Zip Code
            </label>
            <input
              type="text"
              placeholder="e.g. 90210"
              className="w-full px-4 py-2.5 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface placeholder:text-outline focus:ring-2 focus:ring-primary/20"
              value={filterZip}
              onChange={(e) => setFilterZip(e.target.value)}
              maxLength={5}
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
              Age Range
            </label>
            <select
              className="w-full px-4 py-2.5 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface focus:ring-2 focus:ring-primary/20"
              value={filterAge}
              onChange={(e) => setFilterAge(e.target.value)}
            >
              <option value="">All Ages</option>
              <option value="18-30">18-30</option>
              <option value="31-45">31-45</option>
              <option value="46-60">46-60</option>
              <option value="61-120">61+</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
              Income Level
            </label>
            <select
              className="w-full px-4 py-2.5 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface focus:ring-2 focus:ring-primary/20"
              value={filterIncome}
              onChange={(e) => setFilterIncome(e.target.value)}
            >
              <option value="">All Incomes</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
          <div className="flex items-end">
            <button
              className="w-full bg-primary hover:bg-primary-container text-on-primary font-semibold py-2.5 rounded-xl transition-colors text-sm"
              onClick={applyFilters}
            >
              Apply Filters
            </button>
          </div>
        </div>
      </div>

      {/* Client Table */}
      <div className="bg-surface-container-lowest rounded-xl border border-outline-variant overflow-hidden">
        {loading ? (
          <div className="p-12 text-center">
            <span className="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
            <p className="text-on-surface-variant text-sm mt-4">Loading clients...</p>
          </div>
        ) : error ? (
          <div className="p-12 text-center">
            <p className="text-error text-sm">{error}</p>
          </div>
        ) : filteredClients.length === 0 ? (
          <div className="p-12 text-center">
            <span className="material-symbols-outlined text-4xl text-outline mb-2">group_off</span>
            <p className="text-on-surface-variant text-sm">No clients found. Add your first client to get started.</p>
          </div>
        ) : (
          <>
            <table className="w-full">
              <thead>
                <tr className="border-b border-outline-variant bg-surface-container-low">
                  <th className="text-left px-6 py-4 text-xs font-semibold text-on-surface-variant uppercase tracking-wider">Name</th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-on-surface-variant uppercase tracking-wider">Zip Code</th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-on-surface-variant uppercase tracking-wider">Age</th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-on-surface-variant uppercase tracking-wider">Income</th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-on-surface-variant uppercase tracking-wider">Created</th>
                  <th className="text-right px-6 py-4 text-xs font-semibold text-on-surface-variant uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pagedClients.map((client) => (
                  <tr
                    key={client.id}
                    className="border-b border-outline-variant last:border-b-0 hover:bg-surface-container-low transition-colors group"
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-9 h-9 rounded-full flex items-center justify-center text-on-primary text-xs font-bold ${avatarColor(client.full_name)}`}>
                          {getInitials(client.full_name)}
                        </div>
                        <span className="text-sm font-medium text-on-surface">{client.full_name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-on-surface-variant">{client.zip_code}</td>
                    <td className="px-6 py-4 text-sm text-on-surface-variant">{client.age}</td>
                    <td className="px-6 py-4">
                      <span className="inline-block px-3 py-1 text-xs font-medium rounded-full bg-surface-container-high text-on-surface-variant">
                        {INCOME_LABELS[client.income_level] || client.income_level}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-on-surface-variant">
                      {new Date(client.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          className="p-2 rounded-lg hover:bg-surface-container-high transition-colors"
                          title="View Profile"
                          onClick={() => navigate(`/clients/${client.id}`)}
                        >
                          <span className="material-symbols-outlined text-lg text-primary">person</span>
                        </button>
                        <button
                          className="p-2 rounded-lg hover:bg-surface-container-high transition-colors"
                          title="Run Analysis"
                          onClick={() => navigate(`/clients/${client.id}`)}
                        >
                          <span className="material-symbols-outlined text-lg text-secondary">analytics</span>
                        </button>
                        <button
                          className="p-2 rounded-lg hover:bg-error-container transition-colors"
                          title="Delete"
                          onClick={() => handleDeleteClient(client.id)}
                        >
                          <span className="material-symbols-outlined text-lg text-error">delete</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            <div className="flex items-center justify-between px-6 py-4 border-t border-outline-variant bg-surface-container-low">
              <p className="text-sm text-on-surface-variant">
                Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, filteredClients.length)} of {filteredClients.length}
              </p>
              <div className="flex items-center gap-2">
                <button
                  className="p-2 rounded-lg hover:bg-surface-container-high transition-colors disabled:opacity-30"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  <span className="material-symbols-outlined text-lg text-on-surface-variant">chevron_left</span>
                </button>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                  <button
                    key={p}
                    className={`w-8 h-8 rounded-lg text-sm font-medium transition-colors ${
                      p === page
                        ? 'bg-primary text-on-primary'
                        : 'hover:bg-surface-container-high text-on-surface-variant'
                    }`}
                    onClick={() => setPage(p)}
                  >
                    {p}
                  </button>
                ))}
                <button
                  className="p-2 rounded-lg hover:bg-surface-container-high transition-colors disabled:opacity-30"
                  disabled={page >= totalPages}
                  onClick={() => setPage(page + 1)}
                >
                  <span className="material-symbols-outlined text-lg text-on-surface-variant">chevron_right</span>
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Add Client Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-surface-container-lowest rounded-xl w-full max-w-lg shadow-xl">
            <div className="flex items-center justify-between px-8 py-6 border-b border-outline-variant">
              <h2 className="font-headline text-xl font-bold text-on-surface">Add New Client</h2>
              <button
                className="p-2 rounded-lg hover:bg-surface-container-high transition-colors"
                onClick={() => { setShowAddModal(false); setAddError('') }}
              >
                <span className="material-symbols-outlined text-on-surface-variant">close</span>
              </button>
            </div>

            <form className="p-8 space-y-5" onSubmit={handleAddClient}>
              {addError && (
                <div className="p-4 bg-error-container rounded-xl">
                  <p className="text-sm text-on-error-container">{addError}</p>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
                  Full Name
                </label>
                <input
                  type="text"
                  className="w-full px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface placeholder:text-outline focus:ring-2 focus:ring-primary/20"
                  placeholder="John Doe"
                  value={newClient.full_name}
                  onChange={(e) => setNewClient({ ...newClient, full_name: e.target.value })}
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
                    Zip Code
                  </label>
                  <input
                    type="text"
                    className="w-full px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface placeholder:text-outline focus:ring-2 focus:ring-primary/20"
                    placeholder="90210"
                    value={newClient.zip_code}
                    onChange={(e) => setNewClient({ ...newClient, zip_code: e.target.value })}
                    required
                    maxLength={5}
                    pattern="\d{5}"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
                    Age
                  </label>
                  <input
                    type="number"
                    className="w-full px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface placeholder:text-outline focus:ring-2 focus:ring-primary/20"
                    placeholder="35"
                    value={newClient.age}
                    onChange={(e) => setNewClient({ ...newClient, age: e.target.value })}
                    required
                    min={18}
                    max={120}
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
                  Income Level
                </label>
                <select
                  className="w-full px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface focus:ring-2 focus:ring-primary/20"
                  value={newClient.income_level}
                  onChange={(e) => setNewClient({ ...newClient, income_level: e.target.value })}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  className="flex-1 py-3 rounded-xl border border-outline-variant text-on-surface-variant font-medium text-sm hover:bg-surface-container-high transition-colors"
                  onClick={() => { setShowAddModal(false); setAddError('') }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 py-3 rounded-xl bg-primary text-on-primary font-semibold text-sm hover:bg-primary-container transition-colors disabled:opacity-50"
                  disabled={addLoading}
                >
                  {addLoading ? 'Creating...' : 'Add Client'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
