import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'

function getInitials(name) {
  return name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)
}

const AVATAR_BG = ['bg-blue-100', 'bg-purple-100', 'bg-sky-100', 'bg-slate-200', 'bg-emerald-100']
function avatarBg(name) {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return AVATAR_BG[Math.abs(hash) % AVATAR_BG.length]
}

const RISK_LEVELS = ['Low', 'Medium', 'Low', 'Critical']
const RISK_COLORS = {
  Low: { text: 'text-emerald-600', bg: 'bg-emerald-500', width: 'w-1/4' },
  Medium: { text: 'text-amber-600', bg: 'bg-amber-500', width: 'w-2/3' },
  Critical: { text: 'text-red-600', bg: 'bg-red-500', width: 'w-5/6' },
}
const STATUS_BADGES = [
  { label: 'Active Recovery', cls: 'bg-emerald-50 text-emerald-700' },
  { label: 'Awaiting Triage', cls: 'bg-amber-50 text-amber-700' },
  { label: 'Maintenance', cls: 'bg-blue-50 text-blue-700' },
  { label: 'High Alert', cls: 'bg-red-50 text-red-700' },
]

const PAGE_SIZE = 10

export default function ClientListPage() {
  const navigate = useNavigate()
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [filterRisk, setFilterRisk] = useState('')
  const [filterTime, setFilterTime] = useState('')
  const [page, setPage] = useState(1)

  const [showAddModal, setShowAddModal] = useState(false)
  const [newClient, setNewClient] = useState({ full_name: '', zip_code: '', age: '', income_level: 'medium', prescriptions: [], doctors: [], procedures: [] })
  const [rxInput, setRxInput] = useState('')
  const [docName, setDocName] = useState('')
  const [docNpi, setDocNpi] = useState('')
  const [procInput, setProcInput] = useState('')
  const [addError, setAddError] = useState('')
  const [addLoading, setAddLoading] = useState(false)

  useEffect(() => { loadClients() }, [])

  async function loadClients() {
    setLoading(true)
    try {
      const data = await api.get('/clients')
      setClients(Array.isArray(data) ? data : [])
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  const filteredClients = useMemo(() => clients, [clients])
  const totalPages = Math.max(1, Math.ceil(filteredClients.length / PAGE_SIZE))
  const pagedClients = filteredClients.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  function clearFilters() { setFilterRisk(''); setFilterTime(''); setPage(1) }

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
        prescriptions: newClient.prescriptions,
        doctors: newClient.doctors,
        procedures: newClient.procedures,
      })
      setShowAddModal(false)
      setNewClient({ full_name: '', zip_code: '', age: '', income_level: 'medium', prescriptions: [], doctors: [], procedures: [] })
      setRxInput(''); setDocName(''); setDocNpi(''); setProcInput('')
      await loadClients()
    } catch (err) { setAddError(err.message) }
    finally { setAddLoading(false) }
  }

  async function handleDeleteClient(id) {
    if (!confirm('Delete this client?')) return
    try {
      await api.del(`/clients/${id}`)
      setClients((prev) => prev.filter((c) => c.id !== id))
    } catch (err) { alert(err.message) }
  }

  return (
    <>
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
        <div>
          <span className="text-secondary font-bold tracking-widest text-xs uppercase mb-2 block">Enterprise Management</span>
          <h1 className="text-4xl font-extrabold text-blue-900 tracking-tight font-headline">Client Portfolios</h1>
          <p className="text-slate-500 mt-2 max-w-xl">Centralized oversight of patient clinical paths, insurance statuses, and institutional compliance records.</p>
        </div>
        <div className="flex items-center gap-3">
          <button className="px-6 py-2.5 rounded-lg font-semibold bg-surface-container-highest text-primary border border-outline-variant/10 hover:bg-surface-container-high transition-colors flex items-center gap-2">
            <span className="material-symbols-outlined text-lg">download</span>
            Export Records
          </button>
          <button
            onClick={() => navigate('/clients/new')}
            className="px-6 py-2.5 rounded-lg font-semibold bg-primary text-white shadow-xl shadow-primary/10 hover:shadow-primary/20 transition-all flex items-center gap-2"
          >
            <span className="material-symbols-outlined text-lg">person_add</span>
            Add Client
          </button>
        </div>
      </div>

      {/* Stats Bento Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white p-6 rounded-xl shadow-sm shadow-blue-900/5">
          <p className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-1">Total Active</p>
          <div className="flex items-end justify-between">
            <span className="text-3xl font-extrabold text-blue-950 font-headline">
              {loading ? '...' : clients.length.toLocaleString()}
            </span>
            <span className="text-emerald-600 text-sm font-bold flex items-center">
              Active <span className="material-symbols-outlined text-xs ml-0.5">trending_up</span>
            </span>
          </div>
        </div>
        <div className="bg-white p-6 rounded-xl shadow-sm shadow-blue-900/5">
          <p className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-1">Pending Approval</p>
          <div className="flex items-end justify-between">
            <span className="text-3xl font-extrabold text-blue-950 font-headline">
              {loading ? '...' : Math.min(clients.length, 42)}
            </span>
            <span className="text-amber-600 text-sm font-bold">Action Required</span>
          </div>
        </div>
        <div className="bg-white p-6 rounded-xl shadow-sm shadow-blue-900/5">
          <p className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-1">Risk Profile</p>
          <div className="flex items-end justify-between">
            <span className="text-3xl font-extrabold text-blue-950 font-headline">3%</span>
            <span className="text-slate-400 text-sm font-medium">Lower than avg</span>
          </div>
        </div>
        <div className="bg-white p-6 rounded-xl shadow-sm shadow-blue-900/5">
          <p className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-1">Avg Stay</p>
          <div className="flex items-end justify-between">
            <span className="text-3xl font-extrabold text-blue-950 font-headline">14d</span>
            <span className="text-slate-400 text-sm font-medium">Standard range</span>
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-white rounded-2xl shadow-sm shadow-blue-900/5 mb-6 overflow-hidden">
        <div className="p-4 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-2 bg-slate-50 rounded-lg border border-slate-100 min-w-[200px]">
            <span className="material-symbols-outlined text-slate-400 text-sm">filter_list</span>
            <select
              className="bg-transparent border-none text-sm font-medium text-slate-700 w-full focus:ring-0"
              value={filterRisk}
              onChange={(e) => setFilterRisk(e.target.value)}
            >
              <option value="">All Risk Tiers</option>
              <option value="high">High Priority</option>
              <option value="standard">Standard Care</option>
            </select>
          </div>
          <div className="flex items-center gap-2 px-3 py-2 bg-slate-50 rounded-lg border border-slate-100 min-w-[200px]">
            <span className="material-symbols-outlined text-slate-400 text-sm">verified</span>
            <select className="bg-transparent border-none text-sm font-medium text-slate-700 w-full focus:ring-0">
              <option>All Insurers</option>
              <option>HealthFirst Platinum</option>
              <option>UnitedCare Prime</option>
            </select>
          </div>
          <div className="flex items-center gap-2 px-3 py-2 bg-slate-50 rounded-lg border border-slate-100 min-w-[200px]">
            <span className="material-symbols-outlined text-slate-400 text-sm">calendar_month</span>
            <select
              className="bg-transparent border-none text-sm font-medium text-slate-700 w-full focus:ring-0"
              value={filterTime}
              onChange={(e) => setFilterTime(e.target.value)}
            >
              <option value="">Last 30 Days</option>
              <option value="6m">Last 6 Months</option>
              <option value="ytd">Year to Date</option>
            </select>
          </div>
          <button onClick={clearFilters} className="ml-auto text-sm font-bold text-primary hover:text-blue-600 transition-colors px-4">
            Clear All Filters
          </button>
        </div>
      </div>

      {/* Premium Data Table */}
      <div className="bg-white rounded-2xl shadow-sm shadow-blue-900/5 overflow-hidden">
        {loading ? (
          <div className="p-12 text-center">
            <span className="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
            <p className="text-slate-500 text-sm mt-4">Loading clients...</p>
          </div>
        ) : error ? (
          <div className="p-12 text-center">
            <p className="text-error text-sm">{error}</p>
          </div>
        ) : filteredClients.length === 0 ? (
          <div className="p-12 text-center">
            <span className="material-symbols-outlined text-4xl text-outline mb-2">group_off</span>
            <p className="text-slate-500 text-sm">No clients found. Add your first client to get started.</p>
          </div>
        ) : (
          <>
            <table className="w-full text-left border-collapse">
              <thead className="bg-slate-50/80 border-b border-slate-100">
                <tr>
                  <th className="px-6 py-4 text-xs font-extrabold text-slate-500 uppercase tracking-widest">Client Identity</th>
                  <th className="px-6 py-4 text-xs font-extrabold text-slate-500 uppercase tracking-widest">Clinical Status</th>
                  <th className="px-6 py-4 text-xs font-extrabold text-slate-500 uppercase tracking-widest">Insurer</th>
                  <th className="px-6 py-4 text-xs font-extrabold text-slate-500 uppercase tracking-widest text-center">Risk Factor</th>
                  <th className="px-6 py-4 text-xs font-extrabold text-slate-500 uppercase tracking-widest">Last Activity</th>
                  <th className="px-6 py-4 text-xs font-extrabold text-slate-500 uppercase tracking-widest text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {pagedClients.map((client, idx) => {
                  const risk = RISK_LEVELS[idx % RISK_LEVELS.length]
                  const riskStyle = RISK_COLORS[risk]
                  const status = STATUS_BADGES[idx % STATUS_BADGES.length]
                  return (
                    <tr key={client.id} className="hover:bg-slate-50/50 transition-colors group">
                      <td className="px-6 py-5">
                        <div className="flex items-center gap-4">
                          <div className={`w-10 h-10 rounded-full ${avatarBg(client.full_name)} flex items-center justify-center text-primary font-bold text-xs`}>
                            {getInitials(client.full_name)}
                          </div>
                          <div>
                            <p className="font-bold text-blue-950 font-headline">{client.full_name}</p>
                            <p className="text-xs text-slate-400">ID: {client.id?.slice(0, 8)}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-5">
                        <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold ${status.cls}`}>
                          {status.label}
                        </span>
                      </td>
                      <td className="px-6 py-5">
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-blue-600"></div>
                          <span className="text-sm font-medium text-slate-700">{client.income_level} tier</span>
                        </div>
                      </td>
                      <td className="px-6 py-5 text-center">
                        <div className="inline-flex flex-col items-center">
                          <span className={`text-xs font-bold ${riskStyle.text}`}>{risk}</span>
                          <div className="w-16 h-1 bg-slate-100 rounded-full mt-1 overflow-hidden">
                            <div className={`h-full ${riskStyle.bg} ${riskStyle.width}`}></div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-5">
                        <p className="text-sm text-slate-700">{new Date(client.created_at).toLocaleDateString()}</p>
                        <p className="text-[10px] text-slate-400 font-bold uppercase tracking-tight">
                          {client.prescriptions?.length > 0 ? 'Prescription Active' : 'Profile Created'}
                        </p>
                      </td>
                      <td className="px-6 py-5 text-right">
                        <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => navigate(`/clients/${client.id}`)}
                            className="p-2 hover:bg-white rounded-lg text-primary"
                            title="View Profile"
                          >
                            <span className="material-symbols-outlined text-lg">visibility</span>
                          </button>
                          <button
                            onClick={() => navigate(`/clients/${client.id}`)}
                            className="p-2 hover:bg-white rounded-lg text-slate-400"
                            title="Edit"
                          >
                            <span className="material-symbols-outlined text-lg">edit</span>
                          </button>
                          <button
                            onClick={() => handleDeleteClient(client.id)}
                            className="p-2 hover:bg-white rounded-lg text-slate-400"
                            title="Delete"
                          >
                            <span className="material-symbols-outlined text-lg">more_vert</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {/* Pagination */}
            <div className="p-6 bg-slate-50 flex items-center justify-between border-t border-slate-100">
              <p className="text-sm text-slate-500 font-medium">
                Showing <span className="text-blue-950 font-bold">{(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, filteredClients.length)}</span> of {filteredClients.length} clients
              </p>
              <div className="flex items-center gap-2">
                <button
                  className="p-2 rounded-lg border border-slate-200 text-slate-400 hover:bg-white hover:text-primary transition-all disabled:opacity-30"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  <span className="material-symbols-outlined text-lg">chevron_left</span>
                </button>
                {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => i + 1).map((p) => (
                  <button
                    key={p}
                    className={`w-9 h-9 rounded-lg font-bold text-sm transition-all ${
                      p === page ? 'bg-primary text-white shadow-md' : 'hover:bg-white text-slate-600'
                    }`}
                    onClick={() => setPage(p)}
                  >
                    {p}
                  </button>
                ))}
                {totalPages > 5 && <span className="px-2 text-slate-300">...</span>}
                {totalPages > 5 && (
                  <button
                    className="w-9 h-9 rounded-lg hover:bg-white text-slate-600 font-bold text-sm transition-all"
                    onClick={() => setPage(totalPages)}
                  >
                    {totalPages}
                  </button>
                )}
                <button
                  className="p-2 rounded-lg border border-slate-200 text-slate-400 hover:bg-white hover:text-primary transition-all disabled:opacity-30"
                  disabled={page >= totalPages}
                  onClick={() => setPage(page + 1)}
                >
                  <span className="material-symbols-outlined text-lg">chevron_right</span>
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Insight Banner */}
      <div className="mt-12 rounded-3xl overflow-hidden relative min-h-[160px] flex items-center p-8 bg-primary">
        <div className="absolute inset-0 bg-gradient-to-r from-primary via-primary/80 to-transparent z-10"></div>
        <div className="relative z-20 max-w-2xl">
          <h3 className="text-2xl font-bold text-white mb-2 font-headline">Predictive Compliance Check</h3>
          <p className="text-blue-100 mb-6 leading-relaxed">
            Our clinical curation engine has identified upcoming insurer renewals for your portfolio. We recommend reviewing these before the quarterly deadline.
          </p>
          <button className="px-6 py-2 bg-white text-primary rounded-lg font-bold hover:bg-blue-50 transition-colors">
            Start Review
          </button>
        </div>
      </div>

      {/* Add Client Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-2xl shadow-xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between px-8 py-6 border-b border-slate-100 sticky top-0 bg-white rounded-t-2xl z-10">
              <h2 className="font-headline text-xl font-bold text-blue-950">Add New Client</h2>
              <button onClick={() => { setShowAddModal(false); setAddError('') }} className="p-2 rounded-lg hover:bg-slate-50">
                <span className="material-symbols-outlined text-slate-400">close</span>
              </button>
            </div>
            <form className="p-8 space-y-6" onSubmit={handleAddClient}>
              {addError && (
                <div className="p-4 bg-error-container rounded-xl">
                  <p className="text-sm text-on-error-container">{addError}</p>
                </div>
              )}

              {/* Basic Info */}
              <div>
                <h3 className="text-xs font-bold text-primary uppercase tracking-widest mb-4 flex items-center gap-2">
                  <span className="material-symbols-outlined text-sm">person</span> Basic Information
                </h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Full Name</label>
                    <input type="text" placeholder="John Doe" required
                      className="w-full px-4 py-3 bg-slate-50 rounded-lg border border-slate-100 text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary"
                      value={newClient.full_name} onChange={(e) => setNewClient({ ...newClient, full_name: e.target.value })} />
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Zip Code</label>
                      <input type="text" placeholder="90210" required maxLength={5} pattern="\d{5}"
                        className="w-full px-4 py-3 bg-slate-50 rounded-lg border border-slate-100 text-sm focus:ring-2 focus:ring-primary/20"
                        value={newClient.zip_code} onChange={(e) => setNewClient({ ...newClient, zip_code: e.target.value })} />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Age</label>
                      <input type="number" placeholder="35" required min={18} max={120}
                        className="w-full px-4 py-3 bg-slate-50 rounded-lg border border-slate-100 text-sm focus:ring-2 focus:ring-primary/20"
                        value={newClient.age} onChange={(e) => setNewClient({ ...newClient, age: e.target.value })} />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Income</label>
                      <select className="w-full px-4 py-3 bg-slate-50 rounded-lg border border-slate-100 text-sm focus:ring-2 focus:ring-primary/20"
                        value={newClient.income_level} onChange={(e) => setNewClient({ ...newClient, income_level: e.target.value })}>
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>

              <hr className="border-slate-100" />

              {/* Prescriptions */}
              <div>
                <h3 className="text-xs font-bold text-primary uppercase tracking-widest mb-4 flex items-center gap-2">
                  <span className="material-symbols-outlined text-sm">medication</span> Prescriptions
                </h3>
                <div className="flex gap-2 mb-3">
                  <input type="text" placeholder="e.g. Metformin, Lisinopril..."
                    className="flex-1 px-4 py-2.5 bg-slate-50 rounded-lg border border-slate-100 text-sm focus:ring-2 focus:ring-primary/20"
                    value={rxInput} onChange={(e) => setRxInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        if (rxInput.trim()) {
                          setNewClient({ ...newClient, prescriptions: [...newClient.prescriptions, rxInput.trim()] })
                          setRxInput('')
                        }
                      }
                    }} />
                  <button type="button" onClick={() => {
                    if (rxInput.trim()) {
                      setNewClient({ ...newClient, prescriptions: [...newClient.prescriptions, rxInput.trim()] })
                      setRxInput('')
                    }
                  }} className="px-4 py-2.5 bg-primary text-white rounded-lg text-sm font-semibold hover:bg-primary-container transition-colors">
                    Add
                  </button>
                </div>
                {newClient.prescriptions.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {newClient.prescriptions.map((rx, i) => (
                      <span key={i} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-secondary-fixed/30 text-on-secondary-container rounded-full text-xs font-bold">
                        <span className="material-symbols-outlined text-xs">medication</span>
                        {rx}
                        <button type="button" onClick={() => setNewClient({ ...newClient, prescriptions: newClient.prescriptions.filter((_, j) => j !== i) })}
                          className="ml-1 hover:text-error transition-colors">
                          <span className="material-symbols-outlined text-xs">close</span>
                        </button>
                      </span>
                    ))}
                  </div>
                )}
                {newClient.prescriptions.length === 0 && (
                  <p className="text-xs text-slate-400 italic">No prescriptions added. Type a name and press Enter or click Add.</p>
                )}
              </div>

              <hr className="border-slate-100" />

              {/* Preferred Doctors */}
              <div>
                <h3 className="text-xs font-bold text-primary uppercase tracking-widest mb-4 flex items-center gap-2">
                  <span className="material-symbols-outlined text-sm">stethoscope</span> Preferred Doctors
                </h3>
                <div className="flex gap-2 mb-3">
                  <input type="text" placeholder="Doctor name"
                    className="flex-1 px-4 py-2.5 bg-slate-50 rounded-lg border border-slate-100 text-sm focus:ring-2 focus:ring-primary/20"
                    value={docName} onChange={(e) => setDocName(e.target.value)} />
                  <input type="text" placeholder="NPI (optional)"
                    className="w-36 px-4 py-2.5 bg-slate-50 rounded-lg border border-slate-100 text-sm focus:ring-2 focus:ring-primary/20"
                    value={docNpi} onChange={(e) => setDocNpi(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        if (docName.trim()) {
                          setNewClient({ ...newClient, doctors: [...newClient.doctors, { name: docName.trim(), npi: docNpi.trim() || null }] })
                          setDocName(''); setDocNpi('')
                        }
                      }
                    }} />
                  <button type="button" onClick={() => {
                    if (docName.trim()) {
                      setNewClient({ ...newClient, doctors: [...newClient.doctors, { name: docName.trim(), npi: docNpi.trim() || null }] })
                      setDocName(''); setDocNpi('')
                    }
                  }} className="px-4 py-2.5 bg-primary text-white rounded-lg text-sm font-semibold hover:bg-primary-container transition-colors">
                    Add
                  </button>
                </div>
                {newClient.doctors.length > 0 && (
                  <div className="space-y-2">
                    {newClient.doctors.map((doc, i) => (
                      <div key={i} className="flex items-center justify-between px-4 py-2.5 bg-surface-container-low rounded-lg">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                            <span className="material-symbols-outlined text-primary text-sm">person</span>
                          </div>
                          <div>
                            <p className="text-sm font-medium text-on-surface">{doc.name}</p>
                            {doc.npi && <p className="text-[10px] text-slate-400">NPI: {doc.npi}</p>}
                          </div>
                        </div>
                        <button type="button" onClick={() => setNewClient({ ...newClient, doctors: newClient.doctors.filter((_, j) => j !== i) })}
                          className="p-1 hover:text-error transition-colors text-slate-400">
                          <span className="material-symbols-outlined text-sm">close</span>
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                {newClient.doctors.length === 0 && (
                  <p className="text-xs text-slate-400 italic">No doctors added. Enter a name and optional NPI.</p>
                )}
              </div>

              <hr className="border-slate-100" />

              {/* Procedures */}
              <div>
                <h3 className="text-xs font-bold text-primary uppercase tracking-widest mb-4 flex items-center gap-2">
                  <span className="material-symbols-outlined text-sm">medical_services</span> Expected Procedures
                </h3>
                <div className="flex gap-2 mb-3">
                  <input type="text" placeholder="e.g. MRI, Blood work, Annual physical..."
                    className="flex-1 px-4 py-2.5 bg-slate-50 rounded-lg border border-slate-100 text-sm focus:ring-2 focus:ring-primary/20"
                    value={procInput} onChange={(e) => setProcInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        if (procInput.trim()) {
                          setNewClient({ ...newClient, procedures: [...newClient.procedures, procInput.trim()] })
                          setProcInput('')
                        }
                      }
                    }} />
                  <button type="button" onClick={() => {
                    if (procInput.trim()) {
                      setNewClient({ ...newClient, procedures: [...newClient.procedures, procInput.trim()] })
                      setProcInput('')
                    }
                  }} className="px-4 py-2.5 bg-primary text-white rounded-lg text-sm font-semibold hover:bg-primary-container transition-colors">
                    Add
                  </button>
                </div>
                {newClient.procedures.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {newClient.procedures.map((proc, i) => (
                      <span key={i} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-tertiary-fixed/30 text-on-tertiary-fixed-variant rounded-full text-xs font-bold">
                        <span className="material-symbols-outlined text-xs">medical_services</span>
                        {proc}
                        <button type="button" onClick={() => setNewClient({ ...newClient, procedures: newClient.procedures.filter((_, j) => j !== i) })}
                          className="ml-1 hover:text-error transition-colors">
                          <span className="material-symbols-outlined text-xs">close</span>
                        </button>
                      </span>
                    ))}
                  </div>
                )}
                {newClient.procedures.length === 0 && (
                  <p className="text-xs text-slate-400 italic">No procedures added. Type a name and press Enter or click Add.</p>
                )}
              </div>

              {/* Actions */}
              <div className="flex gap-3 pt-4 border-t border-slate-100">
                <button type="button" onClick={() => { setShowAddModal(false); setAddError('') }}
                  className="flex-1 py-3 rounded-lg border border-slate-200 text-slate-600 font-medium text-sm hover:bg-slate-50 transition-colors">
                  Cancel
                </button>
                <button type="submit" disabled={addLoading}
                  className="flex-1 py-3 rounded-lg bg-primary text-white font-bold text-sm shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all disabled:opacity-50">
                  {addLoading ? 'Creating...' : 'Add Client'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  )
}
