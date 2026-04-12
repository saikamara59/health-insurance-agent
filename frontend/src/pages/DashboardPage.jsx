import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import api from '../api/client'

export default function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
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
      {/* Hero */}
      <section className="mb-10 flex flex-col lg:flex-row lg:items-end justify-between gap-6">
        <div>
          <span className="text-primary font-bold text-xs tracking-widest uppercase block mb-2 font-headline">Institutional Dashboard</span>
          <h1 className="text-4xl font-headline font-extrabold text-sky-950 tracking-tight">Welcome, {displayName}</h1>
          <p className="text-slate-600 mt-2 max-w-2xl text-lg font-medium leading-relaxed">
            System HealthFlow is operating at <span className="text-sky-700 font-bold">optimal capacity</span>.
            {clients.length > 0 && <> There {clients.length === 1 ? 'is' : 'are'} <span className="text-primary font-bold">{clients.length} active client{clients.length !== 1 ? 's' : ''}</span> in your portfolio.</>}
          </p>
        </div>
        <div className="flex gap-3 shrink-0">
          <button className="px-5 py-2.5 rounded border border-slate-200 bg-white text-slate-700 font-bold text-sm hover:bg-slate-50 transition-colors shadow-sm">
            Export Report
          </button>
          <button onClick={() => navigate('/clients')} className="px-5 py-2.5 rounded bg-primary text-white font-bold text-sm shadow-md hover:bg-primary-container transition-all">
            Launch Analysis
          </button>
        </div>
      </section>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
        <div className="bg-white p-6 rounded border border-slate-200 shadow-sm transition-all hover:shadow-md">
          <div className="flex items-center justify-between mb-4">
            <div className="w-10 h-10 rounded bg-sky-50 flex items-center justify-center text-primary">
              <span className="material-symbols-outlined">group</span>
            </div>
            <span className="flex items-center text-xs text-green-600 font-bold">
              <span className="material-symbols-outlined text-sm mr-1">trending_up</span>Active
            </span>
          </div>
          <p className="text-slate-500 text-[10px] font-bold tracking-widest uppercase">Total Clients</p>
          <h3 className="text-3xl font-headline font-extrabold text-sky-950 mt-1">{loading ? '...' : clients.length.toLocaleString()}</h3>
        </div>

        <div className="bg-white p-6 rounded border-b-4 border-primary shadow-sm transition-all hover:shadow-md">
          <div className="flex items-center justify-between mb-4">
            <div className="w-10 h-10 rounded bg-sky-50 flex items-center justify-center text-primary">
              <span className="material-symbols-outlined">compare_arrows</span>
            </div>
            <span className="flex items-center text-xs text-orange-600 font-bold">
              <span className="material-symbols-outlined text-sm mr-1">priority_high</span>Action
            </span>
          </div>
          <p className="text-slate-500 text-[10px] font-bold tracking-widest uppercase">Pending Comparisons</p>
          <h3 className="text-3xl font-headline font-extrabold text-sky-950 mt-1">{loading ? '...' : Math.min(clients.length, 8).toString().padStart(2, '0')}</h3>
        </div>

        <div className="lg:col-span-2 bg-sky-900 text-white p-6 rounded shadow-lg relative overflow-hidden flex flex-col justify-between group">
          <div className="relative z-10">
            <p className="text-sky-300 text-[10px] font-bold tracking-widest uppercase">Portfolio Performance</p>
            <h3 className="text-2xl font-headline font-bold mt-1">Institutional Tier</h3>
          </div>
          <div className="flex items-end justify-between relative z-10 mt-6">
            <div className="flex -space-x-2">
              {clients.slice(0, 3).map((c, i) => {
                const initials = c.full_name?.split(' ').map(n => n[0]).join('').toUpperCase() || '?'
                return (
                  <div key={i} className="w-9 h-9 rounded-full border-2 border-sky-800 bg-sky-700 flex items-center justify-center text-[10px] font-bold text-white">
                    {initials}
                  </div>
                )
              })}
              {clients.length > 3 && (
                <div className="w-9 h-9 rounded-full border-2 border-sky-800 bg-sky-700 flex items-center justify-center text-[10px] font-bold">
                  +{clients.length - 3}
                </div>
              )}
            </div>
            <button onClick={() => navigate('/clients')} className="text-xs font-bold bg-white/10 hover:bg-white/20 px-4 py-2 rounded transition-colors backdrop-blur-sm">
              View Ecosystem
            </button>
          </div>
          <div className="absolute right-0 bottom-0 translate-x-1/4 translate-y-1/4 w-32 h-32 bg-sky-500/10 rounded-full blur-2xl group-hover:scale-125 transition-transform duration-700"></div>
        </div>
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
        {/* Activity Feed */}
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-6">
            <h4 className="text-lg font-headline font-bold text-sky-950">Recent Clinical Activity</h4>
            <button onClick={() => navigate('/activity')} className="text-primary text-sm font-bold hover:underline">View All</button>
          </div>

          <div className="space-y-4">
            {clients.length === 0 && !loading && (
              <div className="bg-white p-8 rounded border border-slate-100 text-center">
                <span className="material-symbols-outlined text-4xl text-slate-300 mb-4">group_off</span>
                <p className="text-slate-500">No clients yet. Add your first client to get started.</p>
              </div>
            )}

            {clients.slice(0, 3).map((client, idx) => (
              <div key={client.id} onClick={() => navigate(`/clients/${client.id}`)}
                className="bg-white p-5 rounded border border-slate-100 shadow-sm flex gap-4 items-start hover:border-sky-200 transition-colors cursor-pointer group">
                <div className="relative shrink-0">
                  <div className="w-14 h-14 rounded bg-slate-50 flex items-center justify-center overflow-hidden border border-slate-100 text-primary font-bold text-lg">
                    {client.full_name?.split(' ').map(n => n[0]).join('').toUpperCase()}
                  </div>
                  <div className={`absolute -bottom-1 -right-1 w-5 h-5 rounded-full border-2 border-white flex items-center justify-center ${
                    idx === 0 ? 'bg-sky-600 text-white' : idx === 1 ? 'bg-violet-600 text-white' : 'bg-slate-400 text-white'
                  }`}>
                    <span className="material-symbols-outlined text-[10px]" style={idx === 0 ? { fontVariationSettings: "'FILL' 1" } : {}}>
                      {idx === 0 ? 'check' : idx === 1 ? 'sync' : 'schedule'}
                    </span>
                  </div>
                </div>

                <div className="flex-1">
                  <div className="flex justify-between items-start mb-1">
                    <h5 className="font-bold text-sky-900 text-base group-hover:text-primary transition-colors">{client.full_name}</h5>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-tighter">
                      {new Date(client.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <p className="text-slate-600 text-sm leading-relaxed mb-3">
                    {client.zip_code} · Age {client.age} · {client.income_level} income
                    {client.prescriptions?.length > 0 && ` · ${client.prescriptions.length} active prescriptions`}
                  </p>
                  <div className="flex items-center gap-4">
                    <span className="text-[9px] font-extrabold text-sky-700 bg-sky-50 px-2 py-0.5 rounded border border-sky-100 uppercase tracking-wider">
                      {client.income_level} tier
                    </span>
                    {client.doctors?.length > 0 && (
                      <div className="flex items-center text-xs text-slate-400 font-medium">
                        <span className="material-symbols-outlined text-sm mr-1">stethoscope</span>
                        {client.doctors.length} provider{client.doctors.length !== 1 ? 's' : ''}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-8">
          {/* System Status */}
          <div className="bg-white rounded border border-slate-200 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-6">
              <h4 className="font-headline font-bold text-sky-950">System Integrity</h4>
              <span className="material-symbols-outlined text-sky-200">shield_with_heart</span>
            </div>
            <div className="space-y-6">
              <div>
                <div className="flex items-center justify-between text-xs mb-2">
                  <span className="text-slate-500 font-bold uppercase tracking-widest">Data Pipeline</span>
                  <span className="text-sky-600 font-extrabold flex items-center">
                    <span className="w-1.5 h-1.5 rounded-full bg-sky-500 mr-2 animate-pulse"></span>OPERATIONAL
                  </span>
                </div>
                <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
                  <div className="bg-sky-500 h-full" style={{ width: '94%' }}></div>
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between text-xs mb-2">
                  <span className="text-slate-500 font-bold uppercase tracking-widest">Verification Node</span>
                  <span className="text-sky-600 font-extrabold flex items-center">
                    <span className="w-1.5 h-1.5 rounded-full bg-sky-500 mr-2"></span>ACTIVE
                  </span>
                </div>
                <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
                  <div className="bg-sky-500 h-full" style={{ width: '88%' }}></div>
                </div>
              </div>
            </div>
          </div>

          {/* Curator Insight */}
          <div className="bg-sky-50 rounded border border-sky-200 p-6 shadow-sm relative overflow-hidden">
            <div className="relative z-10">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-8 h-8 rounded bg-sky-600 text-white flex items-center justify-center shadow-sm">
                  <span className="material-symbols-outlined text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
                </div>
                <h4 className="text-base font-headline font-extrabold text-sky-900 uppercase tracking-tight">Curator Insight</h4>
              </div>
              <p className="text-sky-800 text-sm leading-relaxed mb-6 font-medium">
                "Recent data shifts suggest a <span className="text-sky-600 font-bold">14% increase</span> in respiratory specialty claims within the Northeast corridor. Strategic adjustment is recommended."
              </p>
              <button onClick={() => navigate('/clients')} className="w-full py-2.5 rounded bg-sky-600 text-white font-bold text-sm hover:bg-sky-700 transition-all shadow-sm">
                Run Impact Simulations
              </button>
            </div>
            <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none">
              <span className="material-symbols-outlined text-7xl">lightbulb</span>
            </div>
          </div>

          {/* Deadlines */}
          <div className="px-2">
            <h4 className="text-[10px] font-bold tracking-[0.2em] text-slate-400 uppercase mb-5">Upcoming Milestones</h4>
            <div className="space-y-4">
              <div className="flex items-center gap-4 group cursor-pointer">
                <div className="flex flex-col items-center justify-center w-11 h-11 bg-white rounded border border-slate-200 group-hover:border-primary transition-colors">
                  <span className="text-[9px] font-bold text-slate-400 uppercase leading-none mb-1">Apr</span>
                  <span className="text-sm font-bold text-sky-900 leading-none">15</span>
                </div>
                <div>
                  <h6 className="text-sm font-bold text-sky-950 group-hover:text-primary transition-colors">Annual Audit Report</h6>
                  <p className="text-[11px] text-slate-500">Compliance Submission</p>
                </div>
              </div>
              <div className="flex items-center gap-4 group cursor-pointer">
                <div className="flex flex-col items-center justify-center w-11 h-11 bg-white rounded border border-slate-200 group-hover:border-primary transition-colors">
                  <span className="text-[9px] font-bold text-slate-400 uppercase leading-none mb-1">Apr</span>
                  <span className="text-sm font-bold text-sky-900 leading-none">22</span>
                </div>
                <div>
                  <h6 className="text-sm font-bold text-sky-950 group-hover:text-primary transition-colors">Insurers Conference</h6>
                  <p className="text-[11px] text-slate-500">Global Health Summit</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
