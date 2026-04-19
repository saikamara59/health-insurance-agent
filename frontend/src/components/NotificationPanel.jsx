import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import Icon from './ui/Icon';
import Chip from './ui/Chip';

function sinceLabel(iso) {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.max(0, Math.floor(diff / 86400000));
  if (days === 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days}d ago`;
  return `${Math.floor(days / 7)}w ago`;
}

function iconForAction(type) {
  if (type === 'compare') return 'compare';
  if (type === 'verify') return 'network';
  if (type === 'calculate') return 'calculator';
  if (type === 'appeal') return 'appeal';
  if (type === 'translate') return 'translate';
  return 'history';
}

export default function NotificationPanel({ open, onClose }) {
  const navigate = useNavigate();
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!open) return;
    api.get('/history?limit=20')
      .then((d) => setHistory(Array.isArray(d) ? d : []))
      .catch(() => setHistory([]))
      .finally(() => setLoading(false));
  }, [open]);

  if (!open) return null;

  function handleNavigate(path) {
    onClose();
    navigate(path);
  }

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer">
        <header
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '18px 24px',
            borderBottom: '1px solid var(--line)',
          }}
        >
          <div>
            <div className="eyebrow">Live feed</div>
            <h2 style={{ fontFamily: 'var(--serif)', fontSize: 26, letterSpacing: '-0.01em', marginTop: 4 }}>
              Notifications
            </h2>
          </div>
          <button className="btn icon ghost" onClick={onClose} aria-label="Close">
            <Icon name="x" size={16} />
          </button>
        </header>

        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px' }}>
          {loading && <div className="empty"><div className="loader" /></div>}
          {!loading && history.length === 0 && (
            <div className="empty">
              <div className="empty-title">All quiet</div>
              <div>Run a comparison or verification to start receiving activity notifications here.</div>
            </div>
          )}
          {!loading && history.length > 0 && (
            <div className="col" style={{ gap: 2 }}>
              {history.map((h, i) => (
                <div
                  key={h.id || i}
                  onClick={() => h.client_id && handleNavigate(`/clients/${h.client_id}`)}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '36px 1fr auto',
                    gap: 12,
                    padding: '14px 0',
                    borderBottom: i < history.length - 1 ? '1px dashed var(--line)' : 0,
                    cursor: h.client_id ? 'pointer' : 'default',
                    alignItems: 'start',
                  }}
                >
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: 6,
                      background: 'var(--bg-2)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--ink-2)',
                    }}
                  >
                    <Icon name={iconForAction(h.action_type)} size={14} />
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div className="between" style={{ alignItems: 'baseline', marginBottom: 4 }}>
                      <span style={{ fontSize: 14, fontWeight: 500, textTransform: 'capitalize' }}>
                        {h.action_type.replace(/_/g, ' ')}
                      </span>
                      <span className="muted mono" style={{ fontSize: 11 }}>{sinceLabel(h.created_at)}</span>
                    </div>
                    <div className="muted" style={{ fontSize: 12.5, lineHeight: 1.5 }}>
                      {h.client_name ? <>Ran on <strong style={{ color: 'var(--ink-2)' }}>{h.client_name}</strong></> : 'Anonymous session'}
                      {h.response_summary?.plans && <> · {h.response_summary.plans} plans returned</>}
                    </div>
                  </div>
                  <Chip tone={h.action_type === 'appeal' ? 'accent' : h.action_type === 'verify' ? 'warn' : 'pos'}>
                    {h.action_type}
                  </Chip>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ padding: '14px 24px', borderTop: '1px solid var(--line)', display: 'flex', justifyContent: 'space-between' }}>
          <button className="btn ghost" onClick={() => handleNavigate('/activity')}>
            Full activity log
          </button>
          <button className="btn" onClick={() => handleNavigate('/settings')}>
            <Icon name="settings" size={14} /> Settings
          </button>
        </div>
      </aside>
    </>
  );
}
