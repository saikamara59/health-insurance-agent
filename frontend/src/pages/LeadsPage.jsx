import { useState, useEffect } from 'react';
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
  return `${Math.floor(days / 7)}w ago`;
}

export default function LeadsPage() {
  const navigate = useNavigate();
  const { openMenu, openNotifications } = useLayout();
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/clients')
      .then((d) => setClients(Array.isArray(d) ? d : []))
      .catch(() => setClients([]))
      .finally(() => setLoading(false));
  }, []);

  // Treat clients newer than 14 days as "leads" in flight
  const leads = clients.filter((c) => Date.now() - new Date(c.created_at).getTime() < 14 * 86400000);
  const stale = clients
    .filter((c) => Date.now() - new Date(c.updated_at).getTime() > 30 * 86400000)
    .slice(0, 5);

  return (
    <>
      <TopBar
        crumbs={['Workspace', 'Leads']}
        onMenuClick={openMenu}
        onNotificationsClick={openNotifications}
        action={
          <button className="btn accent" onClick={() => navigate('/clients/new')}>
            <Icon name="plus" size={14} /> Add lead
          </button>
        }
      />
      <div className="page wide">
        <div className="page-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>Pipeline</div>
            <h1 className="page-title"><em>Leads</em></h1>
            <p className="page-sub">
              Prospects added in the last 14 days, plus any clients who've gone quiet for a month or more. Convert a
              lead by running a comparison — it marks activity on the account.
            </p>
          </div>
        </div>

        <div className="grid-12">
          <div style={{ gridColumn: 'span 8' }}>
            <div className="section-head" style={{ marginTop: 0 }}>
              <h2>New this fortnight</h2>
              <div className="after">{leads.length} leads</div>
            </div>
            <div className="card" style={{ overflow: 'hidden' }}>
              {loading && <div className="empty"><div className="loader" /></div>}
              {!loading && leads.length === 0 && (
                <div className="empty">
                  <div className="empty-title">No new leads</div>
                  <div>Add a prospect to start a new engagement.</div>
                </div>
              )}
              {!loading && leads.length > 0 && (
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>ZIP · Age</th>
                      <th>Income</th>
                      <th>Added</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {leads.map((c) => {
                      const tone = c.income_level === 'high' ? 'accent' : c.income_level === 'medium' ? 'pos' : 'warn';
                      return (
                        <tr key={c.id} className="row" onClick={() => navigate(`/clients/${c.id}`)}>
                          <td>
                            <div className="row" style={{ gap: 12 }}>
                              <Avatar name={c.full_name} />
                              <div style={{ fontWeight: 500 }}>{c.full_name}</div>
                            </div>
                          </td>
                          <td>{c.zip_code} · {c.age}</td>
                          <td><Chip tone={tone} dot>{c.income_level}</Chip></td>
                          <td className="muted">{sinceLabel(c.created_at)}</td>
                          <td style={{ textAlign: 'right' }}>
                            <button className="btn sm">Run comparison</button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          <div style={{ gridColumn: 'span 4' }}>
            <div className="section-head" style={{ marginTop: 0 }}>
              <h2>Stale accounts</h2>
              <div className="after">30+ days quiet</div>
            </div>
            <div className="card card-pad">
              {stale.length === 0 ? (
                <div className="muted" style={{ fontSize: 13 }}>Everyone's been touched this month.</div>
              ) : (
                stale.map((c, i, a) => (
                  <div
                    key={c.id}
                    onClick={() => navigate(`/clients/${c.id}`)}
                    style={{
                      padding: '10px 0',
                      borderBottom: i < a.length - 1 ? '1px dashed var(--line)' : 0,
                      cursor: 'pointer',
                    }}
                  >
                    <div className="between">
                      <div>
                        <div style={{ fontWeight: 500 }}>{c.full_name}</div>
                        <div className="muted sub">Last touch {sinceLabel(c.updated_at)}</div>
                      </div>
                      <Chip tone="warn" dot>Reach out</Chip>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
