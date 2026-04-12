import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const INITIAL_NOTIFICATIONS = [
  { id: 1, group: 'today', icon: 'verified', iconBg: 'bg-primary/10 text-primary', iconFill: true, title: 'Network Update Verified', time: '2:30 PM', desc: 'Provider network changes have been finalized and synced to your dashboard.', action: 'VIEW REVISIONS', actionColor: 'text-primary', unread: true, borderColor: 'border-primary', link: '/network' },
  { id: 2, group: 'today', icon: 'leaderboard', iconBg: 'bg-secondary/10 text-secondary', title: 'High-Intent Lead Captured', time: '11:05 AM', desc: 'A new enterprise inquiry was received for a group coverage assessment.', action: 'VIEW LEADS', actionColor: 'text-secondary', unread: false, link: '/leads' },
  { id: 3, group: 'yesterday', icon: 'error', iconBg: 'bg-error/10 text-error', title: 'Compliance Alert: Licensing', time: 'Yesterday, 9:12 AM', desc: 'Your broker license renewal is approaching. Immediate action recommended.', unread: false, link: '/settings' },
  { id: 4, group: 'yesterday', icon: 'history', iconBg: 'bg-tertiary/10 text-tertiary', title: 'Comparison Report Generated', time: 'Yesterday, 4:45 PM', desc: 'The side-by-side analysis is ready for clinical review and delivery.', action: 'OPEN REPORT', actionColor: 'text-primary', unread: false, link: '/history' },
  { id: 5, group: 'thisWeek', icon: 'update', iconBg: 'bg-outline/10 text-outline', title: 'System Maintenance Completed', time: 'This Week', desc: 'HealthFlow clinical database was optimized successfully. No downtime recorded.', unread: false, link: '/support' },
  { id: 6, group: 'thisWeek', icon: 'person_add', iconBg: 'bg-secondary/10 text-secondary', title: 'New Client Onboarded', time: 'This Week', desc: 'Client profile has been created and synced with the HealthFlow network.', action: 'VIEW PROFILE', actionColor: 'text-primary', unread: false, link: '/clients' },
  { id: 7, group: 'thisWeek', icon: 'analytics', iconBg: 'bg-primary/10 text-primary', title: 'Analytics Report Ready', time: 'This Week', desc: 'Monthly performance analytics have been compiled and are available for review.', action: 'VIEW ANALYTICS', actionColor: 'text-primary', unread: false, link: '/analytics' },
]

const GROUP_LABELS = { today: 'Today', yesterday: 'Yesterday', thisWeek: 'This Week' }
const GROUP_ORDER = ['today', 'yesterday', 'thisWeek']

function NotificationItem({ n, onNavigate, onDismiss }) {
  function handleClick() {
    if (n.link) onNavigate(n.link)
  }

  return (
    <div
      onClick={handleClick}
      className={`flex gap-4 p-4 rounded-lg transition-all cursor-pointer group/item ${
        n.unread
          ? 'bg-primary-container/5 border-l-4 ' + (n.borderColor || 'border-primary')
          : 'bg-surface-container-low/50 hover:bg-surface-container-low'
      } relative`}
    >
      {/* Unread dot */}
      {n.unread && <div className="w-2 h-2 bg-primary rounded-full absolute top-5 right-12"></div>}

      {/* Dismiss X button */}
      <button
        onClick={(e) => { e.stopPropagation(); onDismiss(n.id) }}
        className="absolute top-3 right-3 p-1 rounded-full opacity-0 group-hover/item:opacity-100 hover:bg-slate-200 transition-all"
        title="Dismiss"
      >
        <span className="material-symbols-outlined text-slate-400 text-[16px]">close</span>
      </button>

      {/* Icon */}
      <div className={`shrink-0 w-10 h-10 rounded-lg ${n.iconBg} flex items-center justify-center`}>
        <span className="material-symbols-outlined" style={n.iconFill ? { fontVariationSettings: "'FILL' 1" } : {}}>{n.icon}</span>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 pr-6">
        <div className="flex justify-between items-start mb-1">
          <p className="font-headline font-bold text-sm text-primary truncate">{n.title}</p>
          <span className="text-[9px] font-medium text-outline whitespace-nowrap ml-2">{n.time}</span>
        </div>
        <p className="text-xs text-on-surface-variant leading-relaxed mb-3">{n.desc}</p>
        {n.action && (
          <button
            onClick={(e) => { e.stopPropagation(); handleClick() }}
            className={`text-[10px] font-bold uppercase tracking-widest ${n.actionColor} flex items-center gap-1 hover:gap-2 transition-all`}
          >
            {n.action} <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
          </button>
        )}
      </div>
    </div>
  )
}

export default function NotificationPanel({ open, onClose }) {
  const navigate = useNavigate()
  const [notifications, setNotifications] = useState(INITIAL_NOTIFICATIONS)

  if (!open) return null

  function handleNavigate(path) {
    onClose()
    navigate(path)
  }

  function handleDismiss(id) {
    setNotifications(prev => prev.filter(n => n.id !== id))
  }

  function handleMarkAllRead() {
    setNotifications(prev => prev.map(n => ({ ...n, unread: false })))
  }

  function handleClearAll() {
    setNotifications([])
  }

  const groups = GROUP_ORDER
    .map(g => ({ key: g, label: GROUP_LABELS[g], items: notifications.filter(n => n.group === g) }))
    .filter(g => g.items.length > 0)

  const unreadCount = notifications.filter(n => n.unread).length

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-slate-900/10 backdrop-blur-sm" onClick={onClose}></div>
      <div className="relative w-full max-w-lg bg-surface-container-lowest h-full shadow-2xl flex flex-col border-l border-outline-variant/15 animate-slide-in-right">
        {/* Header */}
        <div className="px-8 py-8 border-b border-surface-container-high">
          <div className="flex justify-between items-end">
            <div>
              <span className="text-[10px] uppercase tracking-[0.2em] font-bold text-secondary mb-1 block">Clinical Sanctuary</span>
              <div className="flex items-center gap-3">
                <h2 className="text-3xl font-headline font-extrabold text-primary">Notifications</h2>
                {unreadCount > 0 && (
                  <span className="px-2 py-0.5 bg-primary text-white text-[10px] font-bold rounded-full">{unreadCount}</span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-4">
              <button onClick={handleMarkAllRead} className="text-[10px] uppercase tracking-widest font-bold text-secondary hover:text-primary transition-colors pb-1 border-b-2 border-secondary/20">
                Mark all read
              </button>
              {notifications.length > 0 && (
                <button onClick={handleClearAll} className="text-[10px] uppercase tracking-widest font-bold text-slate-400 hover:text-error transition-colors pb-1">
                  Clear all
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Feed */}
        <div className="flex-1 overflow-y-auto px-8 py-6 space-y-10">
          {groups.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <span className="material-symbols-outlined text-5xl text-slate-200 mb-4">notifications_off</span>
              <p className="font-headline font-bold text-lg text-slate-400 mb-2">All Clear</p>
              <p className="text-sm text-slate-400">No notifications to display.</p>
            </div>
          ) : (
            groups.map(g => (
              <section key={g.key}>
                <h3 className="text-[10px] uppercase tracking-widest font-bold text-outline mb-6">{g.label}</h3>
                <div className="space-y-4">
                  {g.items.map(n => (
                    <NotificationItem key={n.id} n={n} onNavigate={handleNavigate} onDismiss={handleDismiss} />
                  ))}
                </div>
              </section>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="px-8 py-6 bg-surface-container-low/30 flex items-center justify-between border-t border-surface-container-high">
          <button onClick={() => handleNavigate('/settings')} className="flex items-center gap-2">
            <span className="material-symbols-outlined text-outline text-[18px]">settings</span>
            <span className="text-[10px] font-bold uppercase tracking-widest text-outline">Notification Settings</span>
          </button>
          <button onClick={onClose} className="p-2 hover:bg-surface-container-high rounded-full transition-colors">
            <span className="material-symbols-outlined text-primary">close</span>
          </button>
        </div>
      </div>
    </div>
  )
}
