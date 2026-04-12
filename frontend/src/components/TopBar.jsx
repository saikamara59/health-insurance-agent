import { useAuth } from '../contexts/AuthContext'

export default function TopBar({ onMenuClick, onNotificationsClick }) {
  const { user } = useAuth()

  return (
    <header className="fixed top-0 right-0 left-0 md:left-64 z-30 h-16 bg-white/70 backdrop-blur-[12px] shadow-sm shadow-blue-900/5 px-4 md:px-6 flex justify-between items-center font-headline tracking-tight">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="md:hidden p-2 -ml-1 rounded-lg hover:bg-slate-100 transition-colors"
        >
          <span className="material-symbols-outlined text-blue-900">menu</span>
        </button>
        <h2 className="text-xl font-logo tracking-tighter text-blue-900">HealthFlow</h2>
      </div>

      <div className="flex items-center gap-4 md:gap-6">
        <div className="relative hidden sm:block">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-lg">search</span>
          <input
            className="bg-surface-container-low border-none rounded-full py-2 pl-10 pr-4 text-sm w-48 md:w-64 focus:ring-2 focus:ring-primary/20"
            placeholder="Search clinical data..."
            type="text"
          />
        </div>

        <div className="flex items-center gap-2 md:gap-4">
          <button onClick={onNotificationsClick} className="text-slate-500 hover:text-blue-700 transition-colors relative">
            <span className="material-symbols-outlined">notifications</span>
            <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-error rounded-full ring-2 ring-white"></span>
          </button>
          <button className="text-slate-500 hover:text-blue-700 transition-colors hidden sm:block">
            <span className="material-symbols-outlined">account_circle</span>
          </button>
        </div>
      </div>

      <div className="absolute bottom-0 left-0 w-full h-[1px] bg-slate-100/50"></div>
    </header>
  )
}
