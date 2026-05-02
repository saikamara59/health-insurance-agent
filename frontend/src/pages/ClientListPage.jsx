import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import TopBar from '../components/TopBar';
import Icon from '../components/ui/Icon';
import Chip from '../components/ui/Chip';
import Avatar from '../components/ui/Avatar';
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

function riskLevel(client) {
  const rx = client.prescriptions?.length || 0;
  const dr = client.doctors?.length || 0;
  const score = rx + dr * 0.5 + (client.age > 70 ? 2 : 0);
  if (score >= 6) return 'high';
  if (score >= 3) return 'med';
  return 'low';
}

export default function ClientListPage() {
  const navigate = useNavigate();
  const { openMenu, openNotifications } = useLayout();
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    api.get('/clients')
      .then((d) => setClients(Array.isArray(d) ? d : []))
      .catch(() => setClients([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    let out = clients;
    if (filter === 'low' || filter === 'medium' || filter === 'high') {
      out = out.filter((c) => (c.income_level || '').toLowerCase() === filter);
    } else if (filter === 'complex') {
      out = out.filter((c) => (c.prescriptions?.length || 0) >= 3);
    } else if (filter === 'senior') {
      out = out.filter((c) => (c.age || 0) >= 65);
    }
    if (query.trim()) {
      const q = query.toLowerCase();
      out = out.filter(
        (c) =>
          c.full_name?.toLowerCase().includes(q) ||
          c.zip_code?.includes(q) ||
          c.id?.toLowerCase().includes(q),
      );
    }
    return out;
  }, [clients, query, filter]);

  const filters = [
    { key: 'all', label: 'All', count: clients.length },
    { key: 'high', label: 'High income', count: clients.filter((c) => c.income_level === 'high').length },
    { key: 'medium', label: 'Medium', count: clients.filter((c) => c.income_level === 'medium').length },
    { key: 'low', label: 'Low income', count: clients.filter((c) => c.income_level === 'low').length },
    { key: 'senior', label: 'Age 65+', count: clients.filter((c) => (c.age || 0) >= 65).length },
    { key: 'complex', label: 'Complex Rx', count: clients.filter((c) => (c.prescriptions?.length || 0) >= 3).length },
  ];

  return (
    <>
      <TopBar
        crumbs={['Workspace', 'Clients']}
        onMenuClick={openMenu}
        onNotificationsClick={openNotifications}
        action={
          <button className="btn accent" onClick={() => navigate('/clients/new')}>
            <Icon name="plus" size={14} /> Add client
          </button>
        }
      />
      <div className="page wide">
        <div className="page-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>Book · {clients.length} active</div>
            <h1 className="page-title" style={{ fontFamily: 'Georgia' }}><em>Clients</em></h1>
            <p className="page-sub">
              Everyone you're advising. Filter by income tier or type a name, ZIP, or ID to jump to someone.
            </p>
          </div>
        </div>

        <div className="between" style={{ marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
          <div className="row" style={{ gap: 6, flexWrap: 'wrap', fontFamily: 'Georgia' }}>
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
          <div className="search" style={{ width: 260, fontFamily: 'Times' }}>
            <Icon name="search" size={14} />
            <input placeholder="Search name, ZIP, or ID…" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
        </div>

        <div className="card" style={{ overflow: 'hidden', fontFamily: 'Georgia' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: '28%', fontFamily: 'Georgia' }}>Client</th>
                <th>ZIP · Age</th>
                <th>Income</th>
                <th>Risk</th>
                <th>Rx / Providers</th>
                <th>Last touch</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={7} style={{ padding: 40, textAlign: 'center' }}>
                    <div className="loader" />
                  </td>
                </tr>
              )}
              {!loading && filtered.map((c) => {
                const risk = riskLevel(c);
                const tone = c.income_level === 'high' ? 'accent' : c.income_level === 'medium' ? 'pos' : 'warn';
                return (
                  <tr key={c.id} data-testid="client-row" className="row" onClick={() => navigate(`/clients/${c.id}`)}>
                    <td>
                      <div className="row" style={{ gap: 12 }}>
                        <Avatar name={c.full_name} />
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.full_name}</div>
                          <div className="sub mono">#{c.id.slice(0, 8)}</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <div>{c.zip_code}</div>
                      <div className="sub">Age {c.age}</div>
                    </td>
                    <td>
                      <Chip tone={tone} dot>{c.income_level}</Chip>
                    </td>
                    <td>
                      <div className="row" style={{ gap: 8 }}>
                        <span className={`risk-dot ${risk}`} />
                        <span style={{ textTransform: 'capitalize', fontSize: 13 }}>{risk}</span>
                      </div>
                    </td>
                    <td className="num">
                      <span>{c.prescriptions?.length || 0} Rx</span>
                      <span className="muted"> · {c.doctors?.length || 0} dr</span>
                    </td>
                    <td className="muted">{sinceLabel(c.updated_at || c.created_at)}</td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        className="btn ghost icon sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/clients/${c.id}`);
                        }}
                        aria-label="Open client"
                      >
                        <Icon name="chev_r" size={14} />
                      </button>
                    </td>
                  </tr>
                );
              })}
              {!loading && filtered.length === 0 && (
                <tr>
                  <td colSpan={7}>
                    <div className="empty">
                      <div className="empty-title">
                        {clients.length === 0 ? 'No clients yet' : 'No matches'}
                      </div>
                      <div>
                        {clients.length === 0
                          ? 'Add your first client to start tracking renewals and running comparisons.'
                          : 'Try clearing the filter or searching a different name.'}
                      </div>
                      {clients.length === 0 && (
                        <div style={{ marginTop: 18 }}>
                          <button className="btn accent" onClick={() => navigate('/clients/new')}>
                            <Icon name="plus" size={14} /> Add client
                          </button>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {!loading && clients.length > 0 && (
          <div className="between" style={{ marginTop: 16, color: 'var(--ink-3)', fontSize: 12.5 }}>
            <span>Showing {filtered.length} of {clients.length}</span>
          </div>
        )}
      </div>
    </>
  );
}
