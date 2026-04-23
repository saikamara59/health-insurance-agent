import { NavLink } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Icon from './ui/Icon';
import Avatar from './ui/Avatar';

const NAV = [
  {
    group: 'Workspace',
    items: [
      { path: '/', label: 'Overview', icon: 'dashboard', end: true },
      { path: '/clients', label: 'Clients', icon: 'users' },
      { path: '/leads', label: 'Leads', icon: 'leads' },
      { path: '/activity', label: 'Activity', icon: 'history' },
    ],
  },
  {
    group: 'Tools',
    items: [
      { path: '/compare', label: 'Plan comparison', icon: 'compare' },
      { path: '/translator', label: 'Coverage translator', icon: 'translate' },
      { path: '/network', label: 'Network verify', icon: 'network' },
      { path: '/calculator', label: 'Cost calculator', icon: 'calculator' },
      { path: '/appeals', label: 'Claim appeals', icon: 'appeal' },
    ],
  },
  {
    group: 'Review',
    items: [
      { path: '/history', label: 'History', icon: 'history' },
      { path: '/analytics', label: 'Analytics', icon: 'analytics' },
      { path: '/feedback', label: 'Feedback', icon: 'feedback' },
      { path: '/settings', label: 'Settings', icon: 'settings' },
      { path: '/support', label: 'Support', icon: 'support' },
    ],
  },
];

export default function Sidebar({ open, onClose }) {
  const { user, logout } = useAuth();
  const brokerName = user?.email?.split('@')[0] || 'Broker';
  const display = brokerName.charAt(0).toUpperCase() + brokerName.slice(1);

  return (
    <>
      <div className={`side-backdrop ${open ? 'open' : ''}`} onClick={onClose} />
      <aside className={`side ${open ? 'open' : ''}`}>
        <div className="brand">
          <span className="brand-mark">h</span>
          <span className="brand-name">HealthFlow</span>
          <span className="brand-tag">v3</span>
        </div>

        {NAV.map((group) => (
          <div key={group.group} className="nav-group">
            <div className="nav-group-label">{group.group}</div>
            {group.items.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.end}
                onClick={onClose}
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
              >
                <span className="nav-dot" />
                <Icon name={item.icon} className="nav-ic" />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </div>
        ))}

        <div className="bottom">
          <div className="user-chip">
            <Avatar name={display} />
            <div style={{ lineHeight: 1.2, minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {display}
              </div>
              <div style={{ fontSize: 11, color: 'var(--ink-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {user?.email || 'broker@healthflow.com'}
              </div>
            </div>
            <button
              className="btn icon ghost sm"
              onClick={logout}
              title="Sign out"
              aria-label="Sign out"
            >
              <Icon name="logout" size={14} />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
