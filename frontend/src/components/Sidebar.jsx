import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/client';
import Icon from './ui/Icon';
import Avatar from './ui/Avatar';

const NAV = [
  {
    group: 'Workspace',
    items: [
      { path: '/', label: 'Overview', icon: 'dashboard', end: true },
      { path: '/clients', label: 'Clients', icon: 'users', countKey: 'clients' },
      { path: '/leads', label: 'Leads', icon: 'leads', countKey: 'leads' },
      { path: '/activity', label: 'Activity', icon: 'history' },
    ],
  },
  {
    group: 'Tools',
    items: [
      { path: '/compare', label: 'Plan comparison', icon: 'compare' },
      { path: '/translator', label: 'Coverage translator', icon: 'translate' },
      { path: '/plan', label: 'Temporal plan', icon: 'history' },
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

  const [counts, setCounts] = useState({});
  useEffect(() => {
    let alive = true;
    Promise.all([
      api.get('/clients').catch(() => []),
      api.get('/leads').catch(() => []),
    ]).then(([clients, leads]) => {
      if (!alive) return;
      setCounts({
        clients: Array.isArray(clients) ? clients.length : 0,
        leads: Array.isArray(leads) ? leads.length : 0,
      });
    });
    return () => { alive = false; };
  }, []);

  return (
    <>
      <div className={`side-backdrop ${open ? 'open' : ''}`} onClick={onClose} />
      <aside className={`side ${open ? 'open' : ''}`}>
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" width="28" height="28" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
              <rect x="1" y="1" width="30" height="30" rx="9" fill="var(--brand-bg)" stroke="none" />
              <path d="M9 7 L9 25" strokeWidth="2.4" stroke="var(--brand-ink)" />
              <path d="M23 7 L23 25" strokeWidth="2.4" stroke="var(--brand-ink)" />
              <path d="M9 16 C 13 13, 19 19, 23 16" strokeWidth="2.4" stroke="var(--brand-accent)" fill="none" />
              <circle cx="23" cy="16" r="2" fill="var(--brand-accent)" stroke="none" />
            </svg>
          </span>
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
                {item.countKey && counts[item.countKey] != null && (
                  <span className="nav-count">{counts[item.countKey]}</span>
                )}
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
