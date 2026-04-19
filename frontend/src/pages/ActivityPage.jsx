import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import TopBar from '../components/TopBar';
import Icon from '../components/ui/Icon';
import Chip from '../components/ui/Chip';
import useLayout from '../components/ui/useLayout';

function sinceLabel(iso) {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.max(0, Math.floor(diff / 86400000));
  if (days === 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

function groupByDay(items) {
  const groups = {};
  items.forEach((a) => {
    const date = new Date(a.created_at);
    const key = date.toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' });
    (groups[key] = groups[key] || []).push(a);
  });
  return groups;
}

export default function ActivityPage() {
  const navigate = useNavigate();
  const { openMenu, openNotifications } = useLayout();
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/history?limit=200')
      .then((d) => setHistory(Array.isArray(d) ? d : []))
      .catch(() => setHistory([]))
      .finally(() => setLoading(false));
  }, []);

  const grouped = groupByDay(history);
  const dayKeys = Object.keys(grouped);

  return (
    <>
      <TopBar crumbs={['Workspace', 'Activity']} onMenuClick={openMenu} onNotificationsClick={openNotifications} />
      <div className="page">
        <div className="page-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>{history.length} actions logged</div>
            <h1 className="page-title"><em>Activity</em></h1>
            <p className="page-sub">
              A real-time log of every comparison, verification, calculation, and appeal you've run — grouped by day.
            </p>
          </div>
        </div>

        {loading && <div className="empty"><div className="loader" /></div>}
        {!loading && history.length === 0 && (
          <div className="card card-pad">
            <div className="empty">
              <div className="empty-title">Nothing logged yet</div>
              <div>Run any tool on a client to start building a timeline.</div>
            </div>
          </div>
        )}

        {dayKeys.map((day) => (
          <div key={day} style={{ marginBottom: 28 }}>
            <div className="eyebrow" style={{ marginBottom: 12 }}>{day}</div>
            <div className="card card-pad">
              <div className="activity">
                {grouped[day].map((a, i, arr) => (
                  <div
                    key={a.id || i}
                    className="act-row"
                    style={{ borderBottom: i < arr.length - 1 ? '1px dashed var(--line)' : 0, cursor: a.client_id ? 'pointer' : 'default' }}
                    onClick={() => a.client_id && navigate(`/clients/${a.client_id}`)}
                  >
                    <span className="act-time mono">{sinceLabel(a.created_at)}</span>
                    <Chip tone={a.action_type === 'appeal' ? 'accent' : a.action_type === 'verify' ? 'warn' : 'pos'}>
                      {a.action_type}
                    </Chip>
                    <div className="act-body">
                      <span className="who">{a.client_name || 'Session'}</span>
                      <span className="muted"> · {a.action_type.replace(/_/g, ' ')} session run</span>
                    </div>
                    {a.client_id && <Icon name="chev_r" size={14} className="ink-4" />}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
