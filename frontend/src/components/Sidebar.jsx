import { NavLink } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const navItems = [
  { path: '/', icon: 'dashboard', label: 'Dashboard' },
  { path: '/clients', icon: 'group', label: 'Client Portfolios' },
  { path: '/leads', icon: 'person_search', label: 'Leads Pipeline' },
  { path: '/analytics', icon: 'analytics', label: 'Analytics' },
  { path: '/settings', icon: 'settings', label: 'Settings' },
]

export default function Sidebar() {
  const { logout } = useAuth()

  return (
    <aside className="h-screen w-64 fixed left-0 top-0 bg-slate-50 flex-col py-8 font-headline text-sm tracking-wide z-40 hidden md:flex">
      <div className="px-6 mb-10">
        <h1 className="text-lg font-extrabold text-blue-950">Clinical Curator</h1>
        <p className="text-xs text-slate-500 uppercase tracking-widest mt-1">Institutional Access</p>
      </div>

      <nav className="flex-1 space-y-4 px-4">
        {navItems.map(({ path, icon, label }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                isActive
                  ? 'bg-blue-100/50 text-blue-900 font-semibold'
                  : 'text-slate-600 hover:bg-slate-100 hover:translate-x-1'
              }`
            }
          >
            <span className="material-symbols-outlined">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-6 mt-auto">
        <NavLink
          to="/clients"
          className="block w-full py-3 bg-primary text-on-primary rounded-lg font-semibold shadow-sm shadow-primary/20 hover:opacity-90 transition-opacity text-center"
        >
          New Application
        </NavLink>
        <div className="mt-6 space-y-2">
          <NavLink to="/support" className="flex items-center gap-3 px-4 py-2 text-slate-500 hover:text-primary transition-colors text-xs">
            <span className="material-symbols-outlined text-lg">help</span>
            Support
          </NavLink>
          <button
            onClick={logout}
            className="flex items-center gap-3 px-4 py-2 text-slate-500 hover:text-error transition-colors text-xs w-full"
          >
            <span className="material-symbols-outlined text-lg">logout</span>
            Sign Out
          </button>
        </div>
      </div>
    </aside>
  )
}
