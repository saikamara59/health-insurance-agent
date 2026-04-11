import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'

const INTENT_BADGES = [
  { label: 'High Intent', cls: 'bg-secondary-fixed text-on-secondary-container' },
  { label: 'Premium Review', cls: 'bg-tertiary-fixed text-on-tertiary-fixed-variant' },
  { label: 'Urgent Intake', cls: 'bg-error-container text-on-error-container' },
  { label: 'Standard Review', cls: 'bg-slate-100 text-slate-500' },
]

const ROLES = [
  'Enterprise Executive | Private Equity',
  'Founder | Tech Strategy Group',
  'Director | Global Logistics',
  'VP Engineering | Robotics Corp',
  'CFO | Healthcare Systems',
  'Managing Partner | Legal',
]

const AVATARS = [
  'bg-blue-100 text-blue-600',
  'bg-slate-200 text-slate-600',
  'bg-purple-100 text-purple-600',
  'bg-emerald-100 text-emerald-600',
]

function getInitials(name) {
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const hours = Math.floor(diff / 3600000)
  if (hours < 1) return 'Just now'
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export default function LeadsPage() {
  const navigate = useNavigate()
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    api.get('/clients').then(data => {
      setClients(Array.isArray(data) ? data : [])
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const urgentCount = Math.min(clients.length, 4)
  const onboardingPct = clients.length > 0 ? 88 : 0

  return (
    <>
      {/* Hero Banner */}
      <section className="mb-12 relative overflow-hidden rounded-2xl bg-primary-container p-12 text-white">
        <div className="absolute inset-0 opacity-20">
          <img
            className="w-full h-full object-cover"
            alt="abstract medical facility"
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuA1YQhEQJjJdHZ8OlZEqgKzsOwHGRH60M9YLty6qHELV0FVBT56X24l7fQBM7fRKvlGh071NRnp3tArouhP0Mgi1zFl4C8x2LNesKcfXnLodbO5axBZM8yDZQ5S7pzNHq3twf5Aoefdy_sYfY33WJSIFQC2YkqJCIv8l_tbpyL8luuY-tSMs6yBe8yU3t73rtpAMCxBX0CwquNYpJHdI77XOZUtj6owHfBaoCfV9NfMmG2YNjbSlkf3bgE4Iuy5GzPftNYSjvFN7Kw"
          />
        </div>
        <div className="relative z-10 max-w-2xl">
          <span className="inline-block px-3 py-1 rounded-full bg-white/20 backdrop-blur-md text-[10px] font-bold uppercase tracking-widest mb-4">
            Institutional Intake
          </span>
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tighter mb-4 leading-none font-headline">
            New Leads Pipeline
          </h1>
          <p className="text-blue-100 text-lg font-light leading-relaxed">
            Prioritizing health outcomes through data-driven client curation.
            {clients.length > 0 && ` Managing ${clients.length} active prospect${clients.length !== 1 ? 's' : ''} awaiting review.`}
          </p>
        </div>
      </section>

      {/* Metrics Bento Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
        <div className="col-span-1 md:col-span-2 bg-surface-container-lowest p-8 rounded-xl shadow-sm border border-outline-variant/10 flex flex-col justify-between">
          <div>
            <h3 className="text-slate-400 text-xs font-bold uppercase tracking-widest mb-1">Conversion Velocity</h3>
            <p className="text-4xl font-bold text-primary tracking-tighter font-headline">14.2 Days</p>
          </div>
          <div className="mt-6 flex items-center gap-2 text-secondary text-sm font-medium">
            <span className="material-symbols-outlined">trending_up</span>
            <span>12% faster than last quarter</span>
          </div>
        </div>
        <div className="bg-white p-8 rounded-xl shadow-sm border border-outline-variant/10">
          <h3 className="text-slate-400 text-xs font-bold uppercase tracking-widest mb-1">Urgent Review</h3>
          <p className="text-4xl font-bold text-error tracking-tighter font-headline">
            {urgentCount.toString().padStart(2, '0')}
          </p>
          <div className="mt-4 h-1 w-full bg-slate-100 rounded-full overflow-hidden">
            <div className="h-full bg-error w-1/4"></div>
          </div>
        </div>
        <div className="bg-white p-8 rounded-xl shadow-sm border border-outline-variant/10">
          <h3 className="text-slate-400 text-xs font-bold uppercase tracking-widest mb-1">Onboarding Pulse</h3>
          <p className="text-4xl font-bold text-secondary tracking-tighter font-headline">{onboardingPct}%</p>
          <div className="mt-4 h-1 w-full bg-slate-100 rounded-full overflow-hidden">
            <div className="h-full bg-secondary" style={{ width: `${onboardingPct}%` }}></div>
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center justify-between mb-8 gap-4">
        <div className="flex items-center gap-4">
          <button
            onClick={() => setFilter('all')}
            className={`px-5 py-2.5 rounded-lg text-sm font-semibold flex items-center gap-2 transition-all ${
              filter === 'all' ? 'bg-primary text-white' : 'bg-white text-slate-600 border border-slate-200 hover:border-primary/30'
            }`}
          >
            <span className="material-symbols-outlined text-lg">filter_list</span>
            All Leads
          </button>
          <button
            onClick={() => setFilter('high')}
            className={`px-5 py-2.5 rounded-lg text-sm font-medium border transition-all ${
              filter === 'high' ? 'bg-primary text-white border-primary' : 'bg-white text-slate-600 border-slate-200 hover:border-primary/30'
            }`}
          >
            High Intent
          </button>
          <button
            onClick={() => setFilter('urgent')}
            className={`px-5 py-2.5 rounded-lg text-sm font-medium border transition-all ${
              filter === 'urgent' ? 'bg-primary text-white border-primary' : 'bg-white text-slate-600 border-slate-200 hover:border-primary/30'
            }`}
          >
            Urgent Intake
          </button>
        </div>
        <div className="text-slate-400 text-sm italic">
          Showing {clients.length} institutional prospects
        </div>
      </div>

      {/* Pipeline Cards */}
      {loading ? (
        <div className="p-12 text-center">
          <span className="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
          <p className="text-slate-500 text-sm mt-4">Loading pipeline...</p>
        </div>
      ) : clients.length === 0 ? (
        <div className="p-12 text-center bg-white rounded-2xl">
          <span className="material-symbols-outlined text-4xl text-outline mb-4">group_off</span>
          <p className="text-slate-500">No leads in the pipeline. Add clients to see them here.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {clients.map((client, idx) => {
            const badge = INTENT_BADGES[idx % INTENT_BADGES.length]
            const role = ROLES[idx % ROLES.length]
            const avatarCls = AVATARS[idx % AVATARS.length]
            return (
              <div
                key={client.id}
                className="bg-white rounded-2xl p-1 shadow-sm border border-slate-100 flex flex-col md:flex-row overflow-hidden group hover:shadow-xl hover:shadow-primary/5 transition-all duration-300"
              >
                {/* Avatar side */}
                <div className="md:w-48 h-48 md:h-auto bg-slate-100 flex items-center justify-center">
                  <div className={`w-20 h-20 rounded-full ${avatarCls} flex items-center justify-center text-2xl font-bold`}>
                    {getInitials(client.full_name)}
                  </div>
                </div>

                {/* Content */}
                <div className="flex-1 p-6 flex flex-col justify-between">
                  <div>
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <h2 className="text-xl font-bold text-primary tracking-tight font-headline">{client.full_name}</h2>
                        <p className="text-sm text-slate-500 font-medium">{role}</p>
                      </div>
                      <div className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest ${badge.cls}`}>
                        {badge.label}
                      </div>
                    </div>
                    <div className="flex gap-4 mt-4">
                      <div className="flex items-center gap-1.5 text-xs text-slate-400">
                        <span className="material-symbols-outlined text-base">calendar_today</span>
                        Received {timeAgo(client.created_at)}
                      </div>
                      <div className="flex items-center gap-1.5 text-xs text-slate-400">
                        <span className="material-symbols-outlined text-base">location_on</span>
                        {client.zip_code}
                      </div>
                      {client.prescriptions?.length > 0 && (
                        <div className="flex items-center gap-1.5 text-xs text-slate-400">
                          <span className="material-symbols-outlined text-base">medication</span>
                          {client.prescriptions.length} Rx
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="mt-8 flex items-center justify-between">
                    <div className="flex -space-x-2">
                      <div className="w-8 h-8 rounded-full border-2 border-white bg-blue-100 flex items-center justify-center text-[10px] font-bold text-blue-600">
                        {getInitials(client.full_name)}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button className="p-2 text-slate-400 hover:text-primary transition-colors">
                        <span className="material-symbols-outlined">more_horiz</span>
                      </button>
                      <button
                        onClick={() => navigate(`/clients/${client.id}`)}
                        className="bg-primary hover:bg-primary-container text-white px-6 py-2 rounded-lg text-sm font-bold transition-all transform active:scale-95"
                      >
                        Initiate Intake
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* FAB */}
      <button
        onClick={() => navigate('/clients')}
        className="fixed bottom-8 right-8 w-16 h-16 bg-primary text-white rounded-full shadow-2xl shadow-primary/40 flex items-center justify-center transform hover:scale-110 active:scale-90 transition-all z-50"
      >
        <span className="material-symbols-outlined text-3xl">add</span>
      </button>
    </>
  )
}
