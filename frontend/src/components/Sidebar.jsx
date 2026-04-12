import { NavLink, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const navItems = [
  { path: '/', icon: 'dashboard', label: 'Dashboard' },
  { path: '/clients', icon: 'group', label: 'Client Portfolios' },
  { path: '/compare', icon: 'compare_arrows', label: 'Plan Comparison' },
  { path: '/network', icon: 'verified_user', label: 'Network Verify' },
  { path: '/translator', icon: 'translate', label: 'Translator' },
  { path: '/calculator', icon: 'calculate', label: 'Cost Calculator' },
  { path: '/appeals', icon: 'medical_services', label: 'Claims Appeal' },
  { path: '/history', icon: 'history', label: 'History' },
  { path: '/leads', icon: 'person_search', label: 'Leads' },
  { path: '/analytics', icon: 'analytics', label: 'Analytics' },
  { path: '/settings', icon: 'settings', label: 'Settings' },
]

export default function Sidebar({ open, onClose }) {
  const { logout } = useAuth()
  const location = useLocation()

  const sidebarContent = (
    <>
      <div className="px-6 mb-10">
        <h1 className="text-lg font-extrabold text-blue-950">Clinical Curator</h1>
        <p className="text-xs text-slate-500 uppercase tracking-widest mt-1">Institutional Access</p>
      </div>

      <nav className="flex-1 space-y-1 px-4 overflow-y-auto">
        {navItems.map(({ path, icon, label }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            onClick={onClose}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all duration-200 text-sm ${
                isActive
                  ? 'bg-blue-100/50 text-blue-900 font-semibold'
                  : 'text-slate-600 hover:bg-slate-100 hover:translate-x-1'
              }`
            }
          >
            <span className="material-symbols-outlined text-xl">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-6 mt-auto pt-4">
        <NavLink
          to="/clients/new"
          onClick={onClose}
          className="block w-full py-3 bg-primary text-on-primary rounded-lg font-semibold shadow-sm shadow-primary/20 hover:opacity-90 transition-opacity text-center text-sm"
        >
          New Application
        </NavLink>
        <div className="mt-4 space-y-1">
          <NavLink to="/support" onClick={onClose} className="flex items-center gap-3 px-4 py-2 text-slate-500 hover:text-primary transition-colors text-xs">
            <span className="material-symbols-outlined text-lg">help</span>
            Support
          </NavLink>
          <button
            onClick={() => { logout(); onClose?.() }}
            className="flex items-center gap-3 px-4 py-2 text-slate-500 hover:text-error transition-colors text-xs w-full"
          >
            <span className="material-symbols-outlined text-lg">logout</span>
            Sign Out
          </button>
        </div>
      </div>
    </>
  )

  return (
    <>
      {/* Desktop sidebar — always visible */}
      <aside className="h-screen w-64 fixed left-0 top-0 bg-slate-50 flex-col py-8 font-headline tracking-wide z-40 hidden md:flex">
        {sidebarContent}
      </aside>

      {/* Mobile overlay sidebar */}
      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/40 z-50 md:hidden"
            onClick={onClose}
          ></div>
          {/* Drawer */}
          <aside className="fixed left-0 top-0 h-screen w-72 bg-slate-50 flex flex-col py-8 font-headline tracking-wide z-50 md:hidden shadow-2xl animate-slide-in">
            {/* Close button */}
            <button
              onClick={onClose}
              className="absolute top-4 right-4 p-2 rounded-lg hover:bg-slate-100 transition-colors"
            >
              <span className="material-symbols-outlined text-slate-500">close</span>
            </button>
            {sidebarContent}
          </aside>
        </>
      )}
    </>
  )
}
