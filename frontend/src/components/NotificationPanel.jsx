import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const INITIAL_NOTIFICATIONS = [
  { id: 1, group: 'today', icon: 'verified', iconBg: 'bg-primary/10 text-primary', iconFill: true, title: 'Network Update Verified', time: '2:30 PM', desc: 'Provider network changes have been finalized and synced to your dashboard.', action: 'VIEW REVISIONS', actionColor: 'text-primary', unread: true, borderColor: 'border-primary', link: '/network' },
  { id: 2, group: 'today', icon: 'leaderboard', iconBg: 'bg-secondary/10 text-secondary', title: 'High-Intent Lead Captured', time: '11:05 AM', desc: 'A new enterprise inquiry was received for a group coverage assessment.', action: 'VIEW LEADS', actionColor: 'text-secondary', unread: false, link: '/leads' },
  { id: 3, group: 'yesterday', icon: 'error', iconBg: 'bg-error/10 text-error', title: 'Compliance Alert', time: 'Yesterday', desc: 'Your broker license renewal is approaching. Immediate action recommended.', unread: false, link: '/settings' },
  { id: 4, group: 'yesterday', icon: 'history', iconBg: 'bg-tertiary/10 text-tertiary', title: 'Report Generated', time: 'Yesterday', desc: 'Side-by-side analysis is ready for clinical review.', action: 'OPEN REPORT', actionColor: 'text-primary', unread: false, link: '/history' },
  { id: 5, group: 'thisWeek', icon: 'update', iconBg: 'bg-outline/10 text-outline', title: 'System Maintenance', time: 'This Week', desc: 'Database optimized successfully. No downtime recorded.', unread: false, link: '/support' },
  { id: 6, group: 'thisWeek', icon: 'person_add', iconBg: 'bg-secondary/10 text-secondary', title: 'Client Onboarded', time: 'This Week', desc: 'New client profile synced with HealthFlow network.', action: 'VIEW', actionColor: 'text-primary', unread: false, link: '/clients' },
  { id: 7, group: 'thisWeek', icon: 'analytics', iconBg: 'bg-primary/10 text-primary', title: 'Analytics Ready', time: 'This Week', desc: 'Monthly performance analytics compiled.', action: 'VIEW', actionColor: 'text-primary', unread: false, link: '/analytics' },
]

const GROUP_LABELS = { today: 'Today', yesterday: 'Yesterday', thisWeek: 'This Week' }
const GROUP_ORDER = ['today', 'yesterday', 'thisWeek']

function NotificationItem({ n, onNavigate, onDismiss }) {
  return (
    <div
      onClick={() => n.link && onNavigate(n.link)}
      className={`flex gap-3 p-3 sm:p-4 rounded-lg transition-all cursor-pointer group/item ${
        n.unread
          ? 'bg-primary-container/5 border-l-4 ' + (n.borderColor || 'border-primary')
          : 'bg-surface-container-low/50 hover:bg-surface-container-low'
      } relative`}
    >
      {n.unread && <div className="w-2 h-2 bg-primary rounded-full absolute top-3 right-10 sm:top-4 sm:right-12"></div>}

      {/* Dismiss */}
      <button
        onClick={(e) => { e.stopPropagation(); onDismiss(n.id) }}
        className="absolute top-2 right-2 sm:top-3 sm:right-3 p-1 rounded-full hover:bg-slate-200 transition-all sm:opacity-0 sm:group-hover/item:opacity-100"
        title="Dismiss"
      >
        <span className="material-symbols-outlined text-slate-400 text-[16px]">close</span>
      </button>

      {/* Icon */}
      <div className={`shrink-0 w-9 h-9 sm:w-10 sm:h-10 rounded-lg ${n.iconBg} flex items-center justify-center`}>
        <span className="material-symbols-outlined text-[20px] sm:text-[24px]" style={n.iconFill ? { fontVariationSettings: "'FILL' 1" } : {}}>{n.icon}</span>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 pr-5">
        <div className="flex justify-between items-start mb-0.5">
          <p className="font-headline font-bold text-sm text-primary truncate">{n.title}</p>
          <span className="text-[9px] font-medium text-outline whitespace-nowrap ml-2 hidden sm:inline">{n.time}</span>
        </div>
        <p className="text-xs text-on-surface-variant leading-relaxed mb-2 line-clamp-2">{n.desc}</p>
        <div className="flex items-center justify-between">
          {n.action ? (
            <button
              onClick={(e) => { e.stopPropagation(); n.link && onNavigate(n.link) }}
              className={`text-[10px] font-bold uppercase tracking-widest ${n.actionColor} flex items-center gap-1 hover:gap-2 transition-all`}
            >
              {n.action} <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
            </button>
          ) : <span></span>}
          <span className="text-[9px] font-medium text-outline sm:hidden">{n.time}</span>
        </div>
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
      {/* Backdrop — hidden on mobile since panel is full-screen */}
      <div className="absolute inset-0 bg-slate-900/10 backdrop-blur-sm hidden sm:block" onClick={onClose}></div>

      {/* Panel — full-screen on mobile, max-w-lg on desktop */}
      <div className="relative w-full sm:max-w-lg bg-surface-container-lowest h-full shadow-2xl flex flex-col border-l border-outline-variant/15 animate-slide-in-right">

        {/* Header */}
        <div className="px-4 sm:px-8 py-5 sm:py-8 border-b border-surface-container-high">
          <div className="flex justify-between items-center sm:items-end">
            <div className="flex items-center gap-3">
              {/* Close for mobile — top-left */}
              <button onClick={onClose} className="sm:hidden p-1 rounded-lg hover:bg-slate-100 -ml-1">
                <span className="material-symbols-outlined text-primary">arrow_back</span>
              </button>
              <div>
                <span className="text-[10px] uppercase tracking-[0.2em] font-bold text-secondary mb-0.5 block hidden sm:block">Clinical Sanctuary</span>
                <div className="flex items-center gap-2">
                  <h2 className="text-xl sm:text-3xl font-headline font-extrabold text-primary">Notifications</h2>
                  {unreadCount > 0 && (
                    <span className="px-2 py-0.5 bg-primary text-white text-[10px] font-bold rounded-full">{unreadCount}</span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 sm:gap-4">
              <button onClick={handleMarkAllRead} className="text-[10px] uppercase tracking-widest font-bold text-secondary hover:text-primary transition-colors">
                Read all
              </button>
              {notifications.length > 0 && (
                <button onClick={handleClearAll} className="text-[10px] uppercase tracking-widest font-bold text-slate-400 hover:text-error transition-colors">
                  Clear
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Feed */}
        <div className="flex-1 overflow-y-auto px-4 sm:px-8 py-4 sm:py-6 space-y-8 sm:space-y-10">
          {groups.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 sm:py-20 text-center">
              <span className="material-symbols-outlined text-5xl text-slate-200 mb-4">notifications_off</span>
              <p className="font-headline font-bold text-lg text-slate-400 mb-2">All Clear</p>
              <p className="text-sm text-slate-400">No notifications to display.</p>
            </div>
          ) : (
            groups.map(g => (
              <section key={g.key}>
                <h3 className="text-[10px] uppercase tracking-widest font-bold text-outline mb-4 sm:mb-6">{g.label}</h3>
                <div className="space-y-3 sm:space-y-4">
                  {g.items.map(n => (
                    <NotificationItem key={n.id} n={n} onNavigate={handleNavigate} onDismiss={handleDismiss} />
                  ))}
                </div>
              </section>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="px-4 sm:px-8 py-4 sm:py-6 bg-surface-container-low/30 flex items-center justify-between border-t border-surface-container-high">
          <button onClick={() => handleNavigate('/settings?tab=notifications')} className="flex items-center gap-2">
            <span className="material-symbols-outlined text-outline text-[18px]">settings</span>
            <span className="text-[10px] font-bold uppercase tracking-widest text-outline hidden sm:inline">Notification Settings</span>
          </button>
          <button onClick={onClose} className="p-2 hover:bg-surface-container-high rounded-full transition-colors hidden sm:block">
            <span className="material-symbols-outlined text-primary">close</span>
          </button>
        </div>
      </div>
    </div>
  )
}
