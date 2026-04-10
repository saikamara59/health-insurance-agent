import { NavLink } from 'react-router-dom'

const navItems = [
  { icon: 'dashboard', label: 'Dashboard', path: '/' },
  { icon: 'group', label: 'Clients', path: '/clients' },
  { icon: 'history', label: 'Comparison History', path: '#' },
  { icon: 'settings', label: 'Settings', path: '#' },
]

const footerItems = [
  { icon: 'support_agent', label: 'Support' },
  { icon: 'account_circle', label: 'Account' },
]

export default function Sidebar() {
  return (
    <aside className="w-64 bg-surface-container-lowest border-r border-outline-variant flex flex-col min-h-screen">
      {/* Logo */}
      <div className="p-6 flex items-center gap-3">
        <div className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
          <span className="material-symbols-outlined text-on-primary text-xl">health_and_safety</span>
        </div>
        <div>
          <span className="font-headline text-xl font-extrabold text-on-surface tracking-tight block">HealthFlow</span>
          <span className="text-xs text-on-surface-variant">Brokerage Portal</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 mt-4">
        <ul className="space-y-1">
          {navItems.map((item) => (
            <li key={item.label}>
              <NavLink
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-colors ${
                    isActive && item.path !== '#'
                      ? 'bg-primary/10 text-primary'
                      : 'text-on-surface-variant hover:bg-surface-container-high'
                  }`
                }
              >
                <span className="material-symbols-outlined text-xl">{item.icon}</span>
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* Footer */}
      <div className="px-4 pb-6 space-y-1">
        {footerItems.map((item) => (
          <button
            key={item.label}
            className="flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-on-surface-variant hover:bg-surface-container-high w-full text-left transition-colors"
          >
            <span className="material-symbols-outlined text-xl">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </div>
    </aside>
  )
}
