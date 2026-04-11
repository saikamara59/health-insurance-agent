import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function getInitials(name) {
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

const STATUS_ICONS = [
  { icon: 'check', bg: 'bg-secondary', fill: true },
  { icon: 'sync', bg: 'bg-tertiary-container', fill: false },
  { icon: 'schedule', bg: 'bg-slate-400', fill: false },
  { icon: 'analytics', bg: 'bg-primary', fill: true },
  { icon: 'medication', bg: 'bg-secondary', fill: true },
]

const ACTIVITY_TYPES = [
  'Profile Created',
  'Plan Comparison Run',
  'Cost Analysis Complete',
  'Network Verification',
  'Appeal Draft Generated',
  'Coverage Translation',
  'Prescription Update',
]

export default function ActivityPage() {
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

  // Generate activity items from clients
  const activities = clients.flatMap((client, idx) => {
    const items = [
      {
        id: `${client.id}-created`,
        client,
        type: 'Profile Created',
        detail: `New client profile created with ${client.prescriptions?.length || 0} prescriptions and ${client.doctors?.length || 0} providers`,
        timestamp: client.created_at,
        statusIdx: 0,
      },
    ]
    if (client.prescriptions?.length > 0) {
      items.push({
        id: `${client.id}-rx`,
        client,
        type: 'Prescription Update',
        detail: `${client.prescriptions.length} active prescriptions: ${client.prescriptions.slice(0, 3).join(', ')}${client.prescriptions.length > 3 ? '...' : ''}`,
        timestamp: client.updated_at || client.created_at,
        statusIdx: 4,
      })
    }
    if (client.doctors?.length > 0) {
      items.push({
        id: `${client.id}-network`,
        client,
        type: 'Network Verification',
        detail: `${client.doctors.length} provider${client.doctors.length !== 1 ? 's' : ''} pending network verification`,
        timestamp: client.updated_at || client.created_at,
        statusIdx: 3,
      })
    }
    return items
  }).sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))

  const filteredActivities = filter === 'all'
    ? activities
    : activities.filter(a => a.type === filter)

  const uniqueTypes = [...new Set(activities.map(a => a.type))]

  return (
    <>
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
        <div>
          <span className="text-secondary font-label text-xs tracking-[0.2em] font-semibold uppercase block mb-2">
            Activity Monitor
          </span>
          <h1 className="text-4xl font-display font-bold text-primary tracking-tight">
            Clinical Activity Feed
          </h1>
          <p className="text-on-surface-variant mt-3 max-w-lg leading-relaxed">
            Complete audit trail of all client interactions, analyses, and system events across your institutional portfolio.
          </p>
        </div>
        <div className="flex gap-3">
          <button className="px-6 py-3 rounded-lg border border-outline-variant bg-surface-container-lowest text-primary font-semibold text-sm hover:bg-surface-container-low transition-colors flex items-center gap-2">
            <span className="material-symbols-outlined text-lg">download</span>
            Export Log
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
        <div className="bg-white p-6 rounded-xl shadow-sm shadow-blue-900/5">
          <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">Total Events</p>
          <p className="text-3xl font-extrabold text-primary font-headline">
            {loading ? '...' : activities.length}
          </p>
        </div>
        <div className="bg-white p-6 rounded-xl shadow-sm shadow-blue-900/5">
          <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">Active Clients</p>
          <p className="text-3xl font-extrabold text-primary font-headline">
            {loading ? '...' : clients.length}
          </p>
        </div>
        <div className="bg-white p-6 rounded-xl shadow-sm shadow-blue-900/5">
          <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">Event Types</p>
          <p className="text-3xl font-extrabold text-primary font-headline">
            {loading ? '...' : uniqueTypes.length}
          </p>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3 mb-8">
        <button
          onClick={() => setFilter('all')}
          className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
            filter === 'all' ? 'bg-primary text-white' : 'bg-white text-slate-600 border border-slate-200 hover:border-primary/30'
          }`}
        >
          All Events
        </button>
        {uniqueTypes.map(type => (
          <button
            key={type}
            onClick={() => setFilter(type)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              filter === type ? 'bg-primary text-white' : 'bg-white text-slate-600 border border-slate-200 hover:border-primary/30'
            }`}
          >
            {type}
          </button>
        ))}
      </div>

      {/* Activity Feed */}
      {loading ? (
        <div className="p-12 text-center">
          <span className="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
          <p className="text-slate-500 text-sm mt-4">Loading activity feed...</p>
        </div>
      ) : filteredActivities.length === 0 ? (
        <div className="p-12 text-center bg-white rounded-2xl">
          <span className="material-symbols-outlined text-4xl text-outline mb-4">event_busy</span>
          <p className="text-slate-500">No activities found.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredActivities.map((activity) => {
            const status = STATUS_ICONS[activity.statusIdx % STATUS_ICONS.length]
            return (
              <div
                key={activity.id}
                className="group bg-surface-container-low hover:bg-surface-container-lowest p-5 rounded-xl transition-all flex gap-5 items-start cursor-pointer"
                onClick={() => navigate(`/clients/${activity.client.id}`)}
              >
                {/* Avatar + status */}
                <div className="relative">
                  <div className="w-12 h-12 rounded-lg bg-white shadow-sm flex items-center justify-center text-primary font-bold text-sm">
                    {getInitials(activity.client.full_name)}
                  </div>
                  <div className={`absolute -bottom-1 -right-1 w-5 h-5 ${status.bg} rounded-full border-2 border-surface flex items-center justify-center`}>
                    <span
                      className="material-symbols-outlined text-[10px] text-white"
                      style={status.fill ? { fontVariationSettings: "'FILL' 1" } : {}}
                    >
                      {status.icon}
                    </span>
                  </div>
                </div>

                {/* Content */}
                <div className="flex-1">
                  <div className="flex justify-between items-start">
                    <div>
                      <h5 className="font-headline font-bold text-blue-900 group-hover:text-primary transition-colors">
                        {activity.client.full_name}
                      </h5>
                      <p className="text-on-surface-variant text-sm mt-1 leading-relaxed">{activity.detail}</p>
                    </div>
                    <span className="text-xs text-slate-400 font-medium whitespace-nowrap ml-4">
                      {timeAgo(activity.timestamp)}
                    </span>
                  </div>
                  <div className="mt-3 flex items-center gap-4">
                    <span className="text-[10px] uppercase tracking-wider font-bold text-secondary bg-secondary-fixed/30 px-2 py-0.5 rounded">
                      {activity.type}
                    </span>
                    <span className="text-xs text-slate-400">
                      {activity.client.zip_code} · Age {activity.client.age}
                    </span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </>
  )
}
