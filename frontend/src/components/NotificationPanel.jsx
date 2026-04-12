const NOTIFICATIONS = {
  today: [
    { id: 1, icon: 'verified', iconBg: 'bg-primary/10 text-primary', iconFill: true, title: 'Network Update Verified', time: '2:30 PM', desc: 'Provider network changes have been finalized and synced to your dashboard.', action: 'VIEW REVISIONS', actionColor: 'text-primary', unread: true, borderColor: 'border-primary' },
    { id: 2, icon: 'leaderboard', iconBg: 'bg-secondary/10 text-secondary', title: 'High-Intent Lead Captured', time: '11:05 AM', desc: 'A new enterprise inquiry was received for a group coverage assessment.', action: 'ASSIGN BROKER', actionColor: 'text-secondary', unread: false },
  ],
  yesterday: [
    { id: 3, icon: 'error', iconBg: 'bg-error/10 text-error', title: 'Compliance Alert: Licensing', time: 'Yesterday, 9:12 AM', desc: 'Your broker license renewal is approaching. Immediate action recommended to avoid disruption.', buttons: [{ label: 'RENEW NOW', cls: 'bg-primary text-on-primary' }, { label: 'DISMISS', cls: 'border border-outline-variant text-outline' }], unread: false },
    { id: 4, icon: 'history', iconBg: 'bg-tertiary/10 text-tertiary', title: 'Comparison Report Generated', time: 'Yesterday, 4:45 PM', desc: 'The side-by-side analysis is ready for clinical review and delivery.', action: 'OPEN REPORT', actionColor: 'text-primary', unread: false },
  ],
  thisWeek: [
    { id: 5, icon: 'update', iconBg: 'bg-outline/10 text-outline', title: 'System Maintenance Completed', time: 'This Week', desc: 'HealthFlow clinical database was optimized successfully. No downtime recorded.', unread: false },
    { id: 6, icon: 'person_add', iconBg: 'bg-secondary/10 text-secondary', title: 'New Client Onboarded', time: 'This Week', desc: 'Client profile has been created and synced with the HealthFlow network.', action: 'VIEW PROFILE', actionColor: 'text-primary', unread: false },
  ],
}

function NotificationItem({ n }) {
  return (
    <div className={`flex gap-4 p-4 rounded-lg transition-all cursor-pointer ${n.unread ? 'bg-primary-container/5 border-l-4 ' + (n.borderColor || 'border-primary') : 'bg-surface-container-low/50 hover:bg-surface-container-low'} relative`}>
      {n.unread && <div className="w-2 h-2 bg-primary rounded-full absolute top-5 right-5"></div>}
      <div className={`shrink-0 w-10 h-10 rounded-lg ${n.iconBg} flex items-center justify-center`}>
        <span className="material-symbols-outlined" style={n.iconFill ? { fontVariationSettings: "'FILL' 1" } : {}}>{n.icon}</span>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex justify-between items-start mb-1">
          <p className="font-headline font-bold text-sm text-primary truncate">{n.title}</p>
          <span className="text-[9px] font-medium text-outline whitespace-nowrap ml-2">{n.time}</span>
        </div>
        <p className="text-xs text-on-surface-variant leading-relaxed mb-3">{n.desc}</p>
        {n.action && (
          <button className={`text-[10px] font-bold uppercase tracking-widest ${n.actionColor} flex items-center gap-1 hover:gap-2 transition-all`}>
            {n.action} <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
          </button>
        )}
        {n.buttons && (
          <div className="flex gap-3">
            {n.buttons.map((b, i) => (
              <button key={i} className={`px-3 py-1.5 rounded text-[10px] font-bold uppercase tracking-widest ${b.cls}`}>{b.label}</button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default function NotificationPanel({ open, onClose }) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-slate-900/10 backdrop-blur-sm" onClick={onClose}></div>

      {/* Panel */}
      <div className="relative w-full max-w-lg bg-surface-container-lowest h-full shadow-2xl flex flex-col border-l border-outline-variant/15 animate-slide-in-right">
        {/* Header */}
        <div className="px-8 py-8 border-b border-surface-container-high flex justify-between items-end">
          <div>
            <span className="text-[10px] uppercase tracking-[0.2em] font-bold text-secondary mb-1 block">Clinical Sanctuary</span>
            <h2 className="text-3xl font-headline font-extrabold text-primary">Notifications</h2>
          </div>
          <button className="text-[10px] uppercase tracking-widest font-bold text-secondary hover:text-primary transition-colors pb-1 border-b-2 border-secondary/20">
            Mark all as read
          </button>
        </div>

        {/* Feed */}
        <div className="flex-1 overflow-y-auto px-8 py-6 space-y-10">
          <section>
            <h3 className="text-[10px] uppercase tracking-widest font-bold text-outline mb-6">Today</h3>
            <div className="space-y-4">
              {NOTIFICATIONS.today.map(n => <NotificationItem key={n.id} n={n} />)}
            </div>
          </section>

          <section>
            <h3 className="text-[10px] uppercase tracking-widest font-bold text-outline mb-6">Yesterday</h3>
            <div className="space-y-4">
              {NOTIFICATIONS.yesterday.map(n => <NotificationItem key={n.id} n={n} />)}
            </div>
          </section>

          <section>
            <h3 className="text-[10px] uppercase tracking-widest font-bold text-outline mb-6">This Week</h3>
            <div className="space-y-4">
              {NOTIFICATIONS.thisWeek.map(n => <NotificationItem key={n.id} n={n} />)}
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="px-8 py-6 bg-surface-container-low/30 flex items-center justify-between border-t border-surface-container-high">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-outline text-[18px]">settings</span>
            <span className="text-[10px] font-bold uppercase tracking-widest text-outline">Notification Settings</span>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-surface-container-high rounded-full transition-colors">
            <span className="material-symbols-outlined text-primary">close</span>
          </button>
        </div>
      </div>
    </div>
  )
}
