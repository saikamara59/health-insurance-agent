import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import api from '../api/client'

export default function DashboardPage() {
  const { user } = useAuth()
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/clients').then(data => {
      setClients(Array.isArray(data) ? data : [])
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const displayName = user?.full_name || user?.email?.split('@')[0] || 'Doctor'

  return (
    <>
      {/* Hero Header */}
      <section className="mb-10 flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <span className="text-primary font-label text-xs tracking-[0.2em] font-semibold uppercase block mb-2">
            Institutional Dashboard
          </span>
          <h1 className="text-4xl md:text-5xl font-display font-bold text-primary tracking-tight">
            Welcome, {displayName}
          </h1>
          <p className="text-on-surface-variant mt-3 max-w-lg leading-relaxed">
            System HealthFlow is currently operating at optimal capacity.
            {clients.length > 0 && ` You have ${clients.length} active client${clients.length !== 1 ? 's' : ''} in your portfolio.`}
          </p>
        </div>
        <div className="flex gap-3">
          <button className="px-6 py-3 rounded-lg border border-outline-variant bg-surface-container-lowest text-primary font-semibold text-sm hover:bg-surface-container-low transition-colors">
            Export Report
          </button>
          <button
            onClick={() => window.location.href = '/clients'}
            className="px-6 py-3 rounded-lg bg-primary text-on-primary font-semibold text-sm shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all"
          >
            Launch Analysis
          </button>
        </div>
      </section>

      {/* Metrics Bento Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-10">
        <div className="md:col-span-1 bg-surface-container-lowest p-6 rounded-xl shadow-sm shadow-blue-900/5 transition-transform hover:-translate-y-1">
          <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center text-primary mb-4">
            <span className="material-symbols-outlined">group</span>
          </div>
          <p className="text-on-surface-variant text-xs font-label tracking-wider font-medium">TOTAL CLIENTS</p>
          <h3 className="text-3xl font-headline font-bold text-primary mt-1">
            {loading ? '...' : clients.length.toLocaleString()}
          </h3>
          <div className="mt-4 flex items-center text-xs text-secondary font-semibold">
            <span className="material-symbols-outlined text-sm mr-1">trending_up</span>
            Active portfolio
          </div>
        </div>

        <div className="md:col-span-1 bg-surface-container-lowest p-6 rounded-xl shadow-sm shadow-blue-900/5 transition-transform hover:-translate-y-1 border-b-2 border-primary">
          <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center text-primary mb-4">
            <span className="material-symbols-outlined">compare_arrows</span>
          </div>
          <p className="text-on-surface-variant text-xs font-label tracking-wider font-medium">PENDING COMPARISONS</p>
          <h3 className="text-3xl font-headline font-bold text-primary mt-1">
            {loading ? '...' : Math.min(clients.length, 8).toString().padStart(2, '0')}
          </h3>
          <div className="mt-4 flex items-center text-xs text-error font-semibold">
            <span className="material-symbols-outlined text-sm mr-1">priority_high</span>
            Action Required
          </div>
        </div>

        <div className="md:col-span-2 bg-primary text-on-primary p-6 rounded-xl shadow-lg shadow-primary/10 overflow-hidden relative">
          <div className="relative z-10 h-full flex flex-col justify-between">
            <div>
              <p className="text-primary-fixed/70 text-xs font-label tracking-wider font-medium uppercase">Active Portfolio Performance</p>
              <h3 className="text-3xl font-headline font-bold mt-1">Institutional Tier</h3>
            </div>
            <div className="flex items-end justify-between mt-4">
              <div className="flex -space-x-3">
                {clients.slice(0, 3).map((c, i) => {
                  const initials = c.full_name?.split(' ').map(n => n[0]).join('').toUpperCase() || '?'
                  return (
                    <div key={i} className="w-10 h-10 rounded-full border-2 border-primary bg-primary-container flex items-center justify-center text-[10px] font-bold text-on-primary">
                      {initials}
                    </div>
                  )
                })}
                {clients.length > 3 && (
                  <div className="w-10 h-10 rounded-full border-2 border-primary bg-primary-container flex items-center justify-center text-[10px] font-bold text-on-primary">
                    +{clients.length - 3}
                  </div>
                )}
              </div>
              <button
                onClick={() => window.location.href = '/clients'}
                className="text-sm font-medium bg-white/10 px-3 py-1 rounded-full backdrop-blur-sm hover:bg-white/20 transition-colors"
              >
                View Ecosystem
              </button>
            </div>
          </div>
          <div className="absolute -right-10 -bottom-10 w-48 h-48 bg-white/5 rounded-full blur-3xl"></div>
        </div>
      </div>

      {/* Content Split */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
        {/* Activity Feed */}
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-6">
            <h4 className="text-xl font-display font-bold text-primary">Recent Clinical Activity</h4>
            <button className="text-secondary text-sm font-semibold hover:underline">View All Activities</button>
          </div>

          <div className="space-y-4">
            {clients.length === 0 && !loading && (
              <div className="bg-surface-container-low p-8 rounded-xl text-center">
                <span className="material-symbols-outlined text-4xl text-outline mb-4">group_off</span>
                <p className="text-on-surface-variant">No clients yet. Add your first client to get started.</p>
              </div>
            )}

            {clients.slice(0, 3).map((client, idx) => (
              <div key={client.id} className="group bg-surface-container-low hover:bg-surface-container-lowest p-5 rounded-xl transition-all flex gap-5 items-start">
                <div className="relative">
                  <div className="w-12 h-12 rounded-lg bg-white shadow-sm flex items-center justify-center text-primary font-bold">
                    {client.full_name?.split(' ').map(n => n[0]).join('').toUpperCase()}
                  </div>
                  <div className={`absolute -bottom-1 -right-1 w-5 h-5 rounded-full border-2 border-surface flex items-center justify-center ${
                    idx === 0 ? 'bg-secondary' : idx === 1 ? 'bg-tertiary-container' : 'bg-slate-400'
                  }`}>
                    <span className="material-symbols-outlined text-[10px] text-white" style={{ fontVariationSettings: "'FILL' 1" }}>
                      {idx === 0 ? 'check' : idx === 1 ? 'sync' : 'schedule'}
                    </span>
                  </div>
                </div>

                <div className="flex-1">
                  <div className="flex justify-between items-start">
                    <div>
                      <h5 className="font-headline font-bold text-blue-900 group-hover:text-primary transition-colors">
                        {client.full_name}
                      </h5>
                      <p className="text-on-surface-variant text-sm mt-1 leading-relaxed">
                        {client.zip_code} · Age {client.age} · {client.income_level} income
                        {client.prescriptions?.length > 0 && ` · ${client.prescriptions.length} prescriptions`}
                      </p>
                    </div>
                    <span className="text-xs text-slate-400 font-medium whitespace-nowrap ml-4">
                      {new Date(client.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <div className="mt-3 flex items-center gap-4">
                    <span className="text-[10px] uppercase tracking-wider font-bold text-secondary bg-secondary-fixed/30 px-2 py-0.5 rounded">
                      {client.income_level} income
                    </span>
                    {client.doctors?.length > 0 && (
                      <span className="text-xs text-slate-500">
                        {client.doctors.length} provider{client.doctors.length !== 1 ? 's' : ''}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Sidebar */}
        <div className="space-y-8">
          {/* System Status */}
          <div className="bg-surface-container-high rounded-2xl p-6 relative overflow-hidden">
            <h4 className="text-lg font-display font-bold text-primary mb-4">System Status</h4>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-on-surface-variant">Data Pipeline</span>
                <span className="flex items-center text-xs font-bold text-secondary uppercase">
                  <span className="w-2 h-2 rounded-full bg-secondary mr-2 animate-pulse"></span>
                  Operational
                </span>
              </div>
              <div className="w-full bg-white/50 h-1.5 rounded-full">
                <div className="bg-secondary h-full rounded-full" style={{ width: '94%' }}></div>
              </div>
              <div className="flex items-center justify-between pt-2">
                <span className="text-sm font-medium text-on-surface-variant">Verification Node</span>
                <span className="flex items-center text-xs font-bold text-secondary uppercase">
                  <span className="w-2 h-2 rounded-full bg-secondary mr-2"></span>
                  Active
                </span>
              </div>
              <div className="w-full bg-white/50 h-1.5 rounded-full">
                <div className="bg-secondary h-full rounded-full" style={{ width: '88%' }}></div>
              </div>
            </div>
            <div className="absolute top-0 right-0 p-4 opacity-5">
              <span className="material-symbols-outlined text-6xl">cloud_done</span>
            </div>
          </div>

          {/* Curator Insights */}
          <div className="bg-surface-container-lowest border border-outline-variant/20 rounded-2xl p-6 shadow-xl shadow-blue-900/5">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-8 h-8 rounded bg-tertiary/10 text-tertiary flex items-center justify-center">
                <span className="material-symbols-outlined text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
              </div>
              <h4 className="text-md font-display font-bold text-primary">Curator Insights</h4>
            </div>
            <p className="text-sm text-on-surface-variant leading-relaxed mb-6 italic">
              "Recent data shifts suggest a 14% increase in respiratory specialty claims within the Northeast corridor. Consider adjusting portfolio weightings."
            </p>
            <button
              onClick={() => window.location.href = '/clients'}
              className="w-full py-3 rounded-lg border-2 border-primary text-primary font-bold text-sm hover:bg-primary hover:text-white transition-all"
            >
              Run Simulations
            </button>
          </div>

          {/* Upcoming Deadlines */}
          <div className="px-2">
            <h4 className="text-xs font-label tracking-widest text-slate-400 font-bold uppercase mb-4">Upcoming Deadlines</h4>
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="flex flex-col items-center justify-center w-10 h-12 bg-white rounded-lg border border-slate-100 shadow-sm">
                  <span className="text-[10px] font-bold text-slate-400 uppercase">Apr</span>
                  <span className="text-sm font-bold text-primary">15</span>
                </div>
                <div>
                  <h6 className="text-sm font-bold text-blue-900">Annual Audit Report</h6>
                  <p className="text-xs text-slate-500">Compliance Submission</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex flex-col items-center justify-center w-10 h-12 bg-white rounded-lg border border-slate-100 shadow-sm">
                  <span className="text-[10px] font-bold text-slate-400 uppercase">Apr</span>
                  <span className="text-sm font-bold text-primary">22</span>
                </div>
                <div>
                  <h6 className="text-sm font-bold text-blue-900">Insurers Conference</h6>
                  <p className="text-xs text-slate-500">Global Health Summit</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
