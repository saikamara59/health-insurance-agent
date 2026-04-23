import { useState, useEffect, useMemo } from 'react';
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

function actionTone(t) {
  if (t === 'appeal') return 'accent';
  if (t === 'verify') return 'warn';
  if (t === 'compare') return 'pos';
  if (t === 'calculate') return 'ghost';
  return '';
}

export default function ComparisonHistoryPage() {
  const navigate = useNavigate();
  const { openMenu, openNotifications } = useLayout();
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    api.get('/history?limit=200')
      .then((d) => setHistory(Array.isArray(d) ? d : []))
      .catch(() => setHistory([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(
    () => (filter === 'all' ? history : history.filter((h) => h.action_type === filter)),
    [history, filter],
  );

  const counts = history.reduce((acc, h) => {
    acc[h.action_type] = (acc[h.action_type] || 0) + 1;
    return acc;
  }, {});

  const filters = [
    { key: 'all', label: 'All', count: history.length },
    { key: 'compare', label: 'Comparisons', count: counts.compare || 0 },
    { key: 'verify', label: 'Verifications', count: counts.verify || 0 },
    { key: 'calculate', label: 'Calculations', count: counts.calculate || 0 },
    { key: 'appeal', label: 'Appeals', count: counts.appeal || 0 },
  ];

  return (
    <>
      <TopBar crumbs={['Review', 'History']} onMenuClick={openMenu} onNotificationsClick={openNotifications} />
      <div className="page wide">
        <div className="page-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>{history.length} actions logged</div>
            <h1 className="page-title"><em>History</em></h1>
            <p className="page-sub">
              Every comparison, verification, cost calculation, and appeal you've run — most recent first.
            </p>
          </div>
        </div>

        <div className="row" style={{ gap: 6, marginBottom: 20, flexWrap: 'wrap' }}>
          {filters.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`btn sm ${filter === f.key ? 'primary' : ''}`}
            >
              {f.label}
              <span className="mono" style={{ fontSize: 10, opacity: 0.7, marginLeft: 4 }}>{f.count}</span>
            </button>
          ))}
        </div>

        <div className="card">
          {loading && <div className="empty"><div className="loader" /></div>}
          {!loading && filtered.length === 0 && (
            <div className="empty">
              <div className="empty-title">{history.length === 0 ? 'No history yet' : 'No matches'}</div>
              <div>
                {history.length === 0
                  ? 'Run a comparison, verification, or appeal to start tracking here.'
                  : 'Try clearing the filter.'}
              </div>
            </div>
          )}
          {!loading && filtered.length > 0 && (
            <table className="tbl">
              <thead>
                <tr>
                  <th style={{ width: 120 }}>When</th>
                  <th style={{ width: 140 }}>Action</th>
                  <th>Client</th>
                  <th>Result</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((h) => (
                  <tr
                    key={h.id}
                    className="row"
                    onClick={() => h.client_id && navigate(`/clients/${h.client_id}`)}
                  >
                    <td className="muted mono">{sinceLabel(h.created_at)}</td>
                    <td><Chip tone={actionTone(h.action_type)}>{h.action_type}</Chip></td>
                    <td>{h.client_name || <span className="muted">—</span>}</td>
                    <td className="muted" style={{ fontSize: 12.5 }}>
                      {Object.entries(h.response_summary || {}).slice(0, 3).map(([k, v]) => `${k}: ${v}`).join(' · ') || '—'}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <Icon name="chev_r" size={14} className="ink-4" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}
