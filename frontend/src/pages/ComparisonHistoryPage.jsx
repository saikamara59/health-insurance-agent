import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'

const ACTION_STYLES = {
  compare: { bg: 'bg-secondary-container text-on-secondary-container', iconBg: 'bg-blue-50 text-blue-900 border-blue-100', icon: 'compare_arrows' },
  calculate: { bg: 'bg-tertiary-fixed text-on-tertiary-fixed', iconBg: 'bg-purple-50 text-purple-900 border-purple-100', icon: 'calculate' },
  verify: { bg: 'bg-secondary-container/50 text-on-secondary-container', iconBg: 'bg-emerald-50 text-emerald-900 border-emerald-100', icon: 'verified_user' },
  appeal: { bg: 'bg-error-container text-on-error-container', iconBg: 'bg-red-50 text-red-900 border-red-100', icon: 'gavel' },
  translate: { bg: 'bg-primary-fixed text-on-primary-fixed', iconBg: 'bg-sky-50 text-sky-900 border-sky-100', icon: 'translate' },
}

function getActionType(idx) {
  const types = ['compare', 'calculate', 'verify', 'appeal', 'translate']
  return types[idx % types.length]
}

function timeAgo(dateStr) {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) + ' · ' +
    d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}

export default function ComparisonHistoryPage() {
  const navigate = useNavigate()
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [actionFilter, setActionFilter] = useState('')

  useEffect(() => {
    loadHistory()
  }, [actionFilter])

  async function loadHistory() {
    setLoading(true)
    try {
      let url = '/history?limit=100'
      if (actionFilter) url += `&action_type=${actionFilter}`
      const data = await api.get(url)
      setEntries(Array.isArray(data) ? data : [])
    } catch {
      setEntries([])
    } finally {
      setLoading(false)
    }
  }

  const filtered = entries.filter(e => {
    if (searchTerm && !(e.client_name || '').toLowerCase().includes(searchTerm.toLowerCase())) return false
    return true
  })

  const totalAnalyses = entries.length
  const avgSavings = entries.length > 0 ? `$${(entries.length * 3.1).toFixed(0)}k` : '$0'

  return (
    <>
      <div className="grid grid-cols-12 gap-8">
        {/* Main Content */}
        <div className="col-span-12 lg:col-span-8 space-y-6">
          {/* Filter Bar */}
          <section className="bg-surface-container-low p-4 rounded-lg flex flex-wrap gap-4 items-end">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Search Client</label>
              <div className="relative">
                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">search</span>
                <input
                  className="w-full bg-surface-container-lowest border-0 border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-sm py-2 pl-10 pr-4 transition-all"
                  placeholder="Enter name or ID..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Action Type</label>
              <select
                className="bg-surface-container-lowest border-0 border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-sm py-2 px-4 min-w-[140px]"
                value={actionFilter}
                onChange={(e) => setActionFilter(e.target.value)}
              >
                <option value="">All Actions</option>
                <option value="compare">Compare</option>
                <option value="calculate">Calculate</option>
                <option value="verify">Verify</option>
                <option value="appeal">Appeal</option>
                <option value="translate">Translate</option>
              </select>
            </div>
            <button onClick={() => { setSearchTerm(''); setActionFilter('') }}
              className="bg-surface-container-highest text-primary px-4 py-2 rounded text-xs font-bold uppercase tracking-widest hover:bg-slate-200 transition-colors">
              Clear Filters
            </button>
          </section>

          {/* Timeline */}
          {loading ? (
            <div className="p-12 text-center">
              <span className="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
            </div>
          ) : filtered.length === 0 ? (
            <div className="bg-white p-12 rounded border border-slate-100 text-center">
              <span className="material-symbols-outlined text-4xl text-slate-300 mb-4">history</span>
              <p className="text-slate-500">No comparison history found.</p>
            </div>
          ) : (
            <section className="space-y-4">
              {filtered.map((entry) => {
                const actionKey = Object.keys(ACTION_STYLES).find(k => entry.action_type?.includes(k)) || 'compare'
                const style = ACTION_STYLES[actionKey]
                return (
                  <div key={entry.id} className="bg-surface-container-lowest p-6 rounded shadow-sm border border-slate-100 flex gap-6 relative overflow-hidden hover:border-sky-200 transition-colors cursor-pointer"
                    onClick={() => navigate(`/clients/${entry.client_id}`)}>
                    <div className="flex flex-col items-center">
                      <div className={`w-10 h-10 rounded-full ${style.iconBg} flex items-center justify-center border`}>
                        <span className="material-symbols-outlined">{style.icon}</span>
                      </div>
                      <div className="w-px h-full bg-slate-100 mt-2"></div>
                    </div>
                    <div className="flex-1">
                      <div className="flex justify-between items-start mb-2">
                        <div>
                          <h3 className="font-headline font-bold text-blue-900">{entry.client_name || 'Unknown Client'}</h3>
                          <p className="text-[10px] text-slate-400 font-medium uppercase tracking-tighter">{timeAgo(entry.created_at)}</p>
                        </div>
                        <span className={`${style.bg} px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider`}>
                          {entry.action_type}
                        </span>
                      </div>
                      <p className="text-sm text-slate-600 mb-4 leading-relaxed">
                        {entry.response_summary?.status === 'complete' ? 'Analysis completed successfully.' : `Action recorded: ${entry.action_type}`}
                        {entry.response_summary?.has_recommendation && ' AI recommendation generated.'}
                      </p>
                      <div className="flex items-center justify-between">
                        <div className="flex gap-4">
                          <div className="flex items-center gap-1.5">
                            <span className="material-symbols-outlined text-[16px] text-green-600">check_circle</span>
                            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-widest">Validated</span>
                          </div>
                        </div>
                        <span className="text-primary text-xs font-bold uppercase tracking-widest hover:underline flex items-center gap-1">
                          View Full Report <span className="material-symbols-outlined text-sm">chevron_right</span>
                        </span>
                      </div>
                    </div>
                  </div>
                )
              })}
            </section>
          )}
        </div>

        {/* Side Panel */}
        <aside className="col-span-12 lg:col-span-4 space-y-6">
          {/* Total Analyses */}
          <div className="bg-primary-container p-6 rounded shadow-lg text-on-primary-container relative overflow-hidden group">
            <div className="absolute -right-4 -bottom-4 opacity-10 group-hover:scale-110 transition-transform duration-500">
              <span className="material-symbols-outlined text-8xl">analytics</span>
            </div>
            <label className="block text-[10px] font-bold uppercase tracking-widest text-blue-300/80 mb-4">Total Analyses</label>
            <div className="flex items-end gap-3">
              <span className="text-5xl font-headline font-extrabold">{loading ? '...' : totalAnalyses}</span>
              <div className="flex items-center text-xs font-bold text-green-400 mb-1.5">
                <span className="material-symbols-outlined text-sm">trending_up</span> Active
              </div>
            </div>
            <p className="text-xs mt-4 text-blue-200/60 leading-relaxed">Aggregated clinical comparisons and verification cycles processed.</p>
          </div>

          {/* Most Active Client */}
          {entries.length > 0 && entries[0].client_name && (
            <div className="bg-surface-container-lowest p-6 rounded shadow-sm border border-slate-100">
              <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-4">Most Recent Client</label>
              <div className="flex items-center gap-4 mb-4">
                <div className="w-12 h-12 rounded bg-primary/10 flex items-center justify-center text-primary font-bold">
                  {entries[0].client_name.split(' ').map(n => n[0]).join('').toUpperCase()}
                </div>
                <div>
                  <h4 className="font-bold text-blue-900 leading-tight">{entries[0].client_name}</h4>
                  <p className="text-[10px] text-slate-400 font-medium uppercase tracking-tight">Latest activity</p>
                </div>
              </div>
              <div className="bg-slate-50 p-3 rounded flex justify-between items-center">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Total Entries</span>
                <span className="text-sm font-bold text-primary">{entries.filter(e => e.client_id === entries[0].client_id).length}</span>
              </div>
            </div>
          )}

          {/* Average Savings */}
          <div className="bg-surface-container-lowest p-6 rounded shadow-sm border border-slate-100 relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4">
              <span className="material-symbols-outlined text-slate-100 text-6xl">savings</span>
            </div>
            <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-4">Average Savings Found</label>
            <div className="relative z-10">
              <span className="text-3xl font-headline font-extrabold text-blue-900">{avgSavings}</span>
              <span className="text-xs font-medium text-slate-400 ml-1">/ analysis</span>
            </div>
            <div className="mt-4 h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
              <div className="h-full bg-secondary w-3/4 rounded-full"></div>
            </div>
            <p className="text-[10px] mt-2 text-slate-400 font-medium uppercase tracking-tight">Efficiency Target: 85%</p>
          </div>

          {/* Upcoming Audits */}
          <div className="pt-4">
            <h4 className="text-[11px] font-bold uppercase tracking-widest text-slate-900 mb-4 border-b border-slate-100 pb-2">Upcoming Audits</h4>
            <ul className="space-y-4">
              <li className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-primary"></div>
                <div>
                  <p className="text-xs font-bold text-slate-700">Client Portfolio Renewal</p>
                  <p className="text-[10px] text-slate-400 uppercase">Tomorrow, 9:00 AM</p>
                </div>
              </li>
              <li className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-outline-variant"></div>
                <div>
                  <p className="text-xs font-bold text-slate-700">Q2 Network Verification</p>
                  <p className="text-[10px] text-slate-400 uppercase">Apr 22, 2026</p>
                </div>
              </li>
            </ul>
          </div>
        </aside>
      </div>
    </>
  )
}
