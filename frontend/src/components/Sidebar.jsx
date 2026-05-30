import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/client';
import Icon from './ui/Icon';
import Avatar from './ui/Avatar';
import BrandLogo from './ui/BrandLogo';

const NAV = [
  {
    group: 'Workspace',
    items: [
      { path: '/dashboard', label: 'Overview', icon: 'dashboard', end: true },
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
  {
    group: 'Administration',
    adminOnly: true,
    items: [
      { path: '/admin', label: 'Workspace admin', icon: 'settings' },
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

  // Lightweight backend liveness check — polls /health every 30s. A red dot
  // makes "is the API up?" visible without opening DevTools.
  const [apiHealth, setApiHealth] = useState('checking');
  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const res = await fetch('/health');
        if (alive) setApiHealth(res.ok ? 'healthy' : 'down');
      } catch {
        if (alive) setApiHealth('down');
      }
    };
    check();
    const handle = setInterval(check, 30_000);
    return () => { alive = false; clearInterval(handle); };
  }, []);

  const healthColor =
    apiHealth === 'healthy' ? 'var(--pos)' :
    apiHealth === 'down' ? 'var(--neg)' :
    'var(--ink-4)';
  const healthLabel =
    apiHealth === 'healthy' ? 'API up' :
    apiHealth === 'down' ? 'API down' :
    'Checking…';

  return (
    <>
      <div className={`side-backdrop ${open ? 'open' : ''}`} onClick={onClose} />
      <aside className={`side ${open ? 'open' : ''}`}>
        <div className="brand">
          <BrandLogo size={28} />
          <span className="brand-name">HealthFlow</span>
          <span className="brand-tag">v3</span>
        </div>

        {/* Scrollable nav region so the bottom user-chip (with Sign out) stays
            in the viewport even when nav groups exceed 100vh — caught by an
            e2e failure after the Tools group grew past 6 items. */}
        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
          {NAV.filter((group) => !group.adminOnly || user?.role === 'admin').map((group) => (
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
        </div>

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
            <span
              aria-hidden="true"
              title={`Backend ${healthLabel}`}
              style={{
                width: 8, height: 8, borderRadius: '50%',
                background: healthColor, flex: '0 0 auto', marginRight: 4,
              }}
            />
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
