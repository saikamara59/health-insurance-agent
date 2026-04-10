import { useAuth } from '../contexts/AuthContext'

export default function TopBar() {
  const { user, logout } = useAuth()

  return (
    <header className="h-16 bg-surface-container-lowest border-b border-outline-variant flex items-center justify-between px-8">
      {/* Search */}
      <div className="relative w-96">
        <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-lg">search</span>
        <input
          type="text"
          placeholder="Search clients, plans, or analyses..."
          className="w-full pl-10 pr-4 py-2 bg-surface-container-high rounded-xl border-none text-sm text-on-surface placeholder:text-outline focus:ring-2 focus:ring-primary/20 outline-none"
        />
      </div>

      {/* Right actions */}
      <div className="flex items-center gap-2">
        {/* Notification bell */}
        <button className="relative p-2 rounded-xl hover:bg-surface-container-high transition-colors">
          <span className="material-symbols-outlined text-on-surface-variant">notifications</span>
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-error rounded-full"></span>
        </button>

        {/* Help */}
        <button className="p-2 rounded-xl hover:bg-surface-container-high transition-colors">
          <span className="material-symbols-outlined text-on-surface-variant">help_outline</span>
        </button>

        {/* Separator */}
        <div className="w-px h-8 bg-outline-variant mx-2"></div>

        {/* User info + avatar */}
        <button
          onClick={logout}
          className="flex items-center gap-3 pl-3 pr-4 py-1.5 rounded-xl hover:bg-surface-container-high transition-colors"
        >
          <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center">
            <span className="text-on-primary text-xs font-bold">
              {user?.email?.charAt(0)?.toUpperCase() || 'B'}
            </span>
          </div>
          <div className="text-left">
            <p className="text-sm font-medium text-on-surface">{user?.email || 'Broker'}</p>
            <p className="text-xs text-on-surface-variant">{user?.role || 'broker'}</p>
          </div>
        </button>
      </div>
    </header>
  )
}
