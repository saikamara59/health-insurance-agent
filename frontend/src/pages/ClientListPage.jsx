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

// Translate the client's profile into a concrete next-step recommendation so
// brokers can act from the list without opening every profile.
function nextAction(c) {
  const rx = c.prescriptions?.length || 0;
  const age = c.age || 0;
  if (age >= 70 && rx >= 3) {
    return { label: 'Review formulary', tone: 'warn' };
  }
  if (age >= 65) {
    return { label: 'Renewal window', tone: '' };
  }
  if (age >= 60 && age < 65) {
    return { label: 'Aging into Medicare', tone: 'accent' };
  }
  if (rx === 0 && (c.doctors?.length || 0) === 0) {
    return { label: 'Complete profile', tone: 'warn' };
  }
  return { label: 'No action', tone: 'ghost' };
}

const RISK_WEIGHT = { low: 0, med: 1, high: 2 };

function compareClients(a, b, key, dir) {
  const m = dir === 'asc' ? 1 : -1;
  if (key === 'name') return (a.full_name || '').localeCompare(b.full_name || '') * m;
  if (key === 'age') return ((a.age || 0) - (b.age || 0)) * m;
  if (key === 'risk') return (RISK_WEIGHT[riskLevel(a)] - RISK_WEIGHT[riskLevel(b)]) * m;
  if (key === 'touch') {
    const ta = new Date(a.updated_at || a.created_at || 0).getTime();
    const tb = new Date(b.updated_at || b.created_at || 0).getTime();
    return (ta - tb) * m;
  }
  return 0;
}

function Th({ k, sort, setSort, children, style }) {
  const active = sort.key === k;
  const handleClick = k
    ? () => setSort((s) => ({ key: k, dir: s.key === k && s.dir === 'asc' ? 'desc' : 'asc' }))
    : undefined;
  return (
    <th
      onClick={handleClick}
      style={{ cursor: k ? 'pointer' : 'default', userSelect: 'none', ...(style || {}) }}
    >
      <span className="row" style={{ gap: 4 }}>
        {children}
        {active && <Icon name={sort.dir === 'asc' ? 'arrow_u' : 'arrow_d'} size={11} />}
      </span>
    </th>
  );
}

function toCsv(rows) {
  const headers = ['id', 'name', 'zip', 'age', 'income', 'rx_count', 'provider_count', 'last_touch'];
  const escape = (v) => {
    const s = v == null ? '' : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [headers.join(',')];
  for (const c of rows) {
    lines.push([
      c.id,
      c.full_name,
      c.zip_code,
      c.age,
      c.income_level,
      c.prescriptions?.length || 0,
      c.doctors?.length || 0,
      c.updated_at || c.created_at || '',
    ].map(escape).join(','));
  }
  return lines.join('\n');
}

function downloadCsv(filename, csv) {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function ClientListPage() {
  const navigate = useNavigate();
  const { openMenu, openNotifications } = useLayout();
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState({ key: 'touch', dir: 'desc' });
  const [selected, setSelected] = useState(() => new Set());

  useEffect(() => {
    api.get('/clients')
      .then((d) => setClients(Array.isArray(d) ? d : []))
      .catch(() => setClients([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    let out = [...clients];
    if (filter === 'action') {
      out = out.filter((c) => nextAction(c).tone !== 'ghost');
    } else if (filter === 'low' || filter === 'medium' || filter === 'high') {
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
    out.sort((a, b) => compareClients(a, b, sort.key, sort.dir));
    return out;
  }, [clients, query, filter, sort]);

  const filters = [
    { key: 'all', label: 'All', count: clients.length },
    { key: 'action', label: 'Needs action', count: clients.filter((c) => nextAction(c).tone !== 'ghost').length },
    { key: 'senior', label: 'Age 65+', count: clients.filter((c) => (c.age || 0) >= 65).length },
    { key: 'complex', label: 'Complex Rx', count: clients.filter((c) => (c.prescriptions?.length || 0) >= 3).length },
    { key: 'high', label: 'High income', count: clients.filter((c) => c.income_level === 'high').length },
    { key: 'medium', label: 'Medium', count: clients.filter((c) => c.income_level === 'medium').length },
    { key: 'low', label: 'Low income', count: clients.filter((c) => c.income_level === 'low').length },
  ];

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const selectAll = () => {
    if (selected.size === filtered.length) setSelected(new Set());
    else setSelected(new Set(filtered.map((c) => c.id)));
  };
  const clearSelection = () => setSelected(new Set());

  const selectedClients = filtered.filter((c) => selected.has(c.id));
  const exportSelected = () => {
    const rows = selectedClients.length ? selectedClients : filtered;
    downloadCsv(`healthflow-clients-${new Date().toISOString().slice(0, 10)}.csv`, toCsv(rows));
  };
  const compareSelected = () => {
    if (selectedClients.length === 1) {
      navigate(`/clients/${selectedClients[0].id}`);
    } else {
      navigate('/compare');
    }
  };

  const headerChecked = selected.size > 0 && selected.size === filtered.length;
  const headerIndeterminate = selected.size > 0 && selected.size < filtered.length;

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
            <h1 className="page-title"><em>Clients</em></h1>
            <p className="page-sub">
              Sorted by most-recent touch. Click a row to open the profile, or select rows to act in bulk.
            </p>
          </div>
          <div className="row">
            <button className="btn" onClick={() => exportSelected()}>
              <Icon name="download" size={14} /> Export CSV
            </button>
          </div>
        </div>

        <div className="between" style={{ marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
          <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
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
          <div className="search" style={{ width: 260 }}>
            <Icon name="search" size={14} />
            <input placeholder="Search name, ZIP, or ID…" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
        </div>

        {selected.size > 0 && (
          <div
            className="between"
            style={{
              padding: '12px 16px',
              marginBottom: 16,
              background: 'var(--panel-2, var(--panel))',
              border: '1px solid var(--line)',
              borderRadius: 8,
              flexWrap: 'wrap',
              gap: 12,
            }}
          >
            <div className="row" style={{ gap: 12 }}>
              <span style={{ fontSize: 14, fontWeight: 500 }}>{selected.size} selected</span>
              <button className="btn ghost sm" onClick={clearSelection}>Clear</button>
            </div>
            <div className="row" style={{ gap: 6 }}>
              <button className="btn sm" onClick={compareSelected}>
                <Icon name="compare" size={12} /> {selected.size === 1 ? 'Open profile' : 'Compare'}
              </button>
              <button className="btn sm" onClick={exportSelected}>
                <Icon name="download" size={12} /> Export {selected.size}
              </button>
            </div>
          </div>
        )}

        <div className="card" style={{ overflow: 'hidden' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: 36, paddingRight: 0 }}>
                  <input
                    type="checkbox"
                    aria-label="Select all clients"
                    checked={headerChecked}
                    ref={(el) => { if (el) el.indeterminate = headerIndeterminate; }}
                    onChange={selectAll}
                  />
                </th>
                <Th k="name" sort={sort} setSort={setSort} style={{ width: '24%' }}>Client</Th>
                <Th k="age" sort={sort} setSort={setSort}>ZIP · Age</Th>
                <th>Income</th>
                <Th k="risk" sort={sort} setSort={setSort}>Risk</Th>
                <th>Rx / Providers</th>
                <th>Next action</th>
                <Th k="touch" sort={sort} setSort={setSort}>Last touch</Th>
                <th style={{ width: 80 }}></th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={9} style={{ padding: 40, textAlign: 'center' }}>
                    <div className="loader" />
                  </td>
                </tr>
              )}
              {!loading && filtered.map((c) => {
                const risk = riskLevel(c);
                const tone = c.income_level === 'high' ? 'accent' : c.income_level === 'medium' ? 'pos' : 'warn';
                const na = nextAction(c);
                const isSel = selected.has(c.id);
                return (
                  <tr
                    key={c.id}
                    data-testid="client-row"
                    className={`row ${isSel ? 'selected' : ''}`}
                    onClick={() => navigate(`/clients/${c.id}`)}
                  >
                    <td style={{ paddingRight: 0 }} onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        aria-label={`Select ${c.full_name}`}
                        checked={isSel}
                        onChange={() => toggleSelect(c.id)}
                      />
                    </td>
                    <td>
                      <div className="row" style={{ gap: 12 }}>
                        <Avatar name={c.full_name} />
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.full_name}</div>
                          <div className="sub">#{c.id.slice(0, 8)}</div>
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
                        <span style={{ textTransform: 'capitalize' }}>{risk}</span>
                      </div>
                    </td>
                    <td className="num">
                      <span>{c.prescriptions?.length || 0} Rx</span>
                      <span className="muted"> · {c.doctors?.length || 0} dr</span>
                    </td>
                    <td>
                      {na.tone === 'ghost' ? (
                        <span className="muted" style={{ fontSize: 13 }}>—</span>
                      ) : (
                        <Chip tone={na.tone} dot>{na.label}</Chip>
                      )}
                    </td>
                    <td className="muted">{sinceLabel(c.updated_at || c.created_at)}</td>
                    <td style={{ textAlign: 'right' }} onClick={(e) => e.stopPropagation()}>
                      <button
                        className="btn ghost icon sm"
                        onClick={() => navigate('/plan')}
                        title="Plan timeline"
                        aria-label="Plan timeline"
                      >
                        <Icon name="history" size={13} />
                      </button>
                      <button
                        className="btn ghost icon sm"
                        onClick={() => navigate(`/clients/${c.id}`)}
                        aria-label="Open client"
                        title="Open profile"
                      >
                        <Icon name="chev_r" size={14} />
                      </button>
                    </td>
                  </tr>
                );
              })}
              {!loading && filtered.length === 0 && (
                <tr>
                  <td colSpan={9}>
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
