import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api/client';
import TopBar from '../components/TopBar';
import Icon from '../components/ui/Icon';
import Chip from '../components/ui/Chip';
import Avatar from '../components/ui/Avatar';
import useLayout from '../components/ui/useLayout';

const TABS = ['overview', 'coverage', 'medical', 'activity', 'edit'];

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

export default function ClientProfilePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { openMenu, openNotifications } = useLayout();

  const [client, setClient] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tab, setTab] = useState('overview');
  const [editForm, setEditForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get(`/clients/${id}`),
      api.get(`/history?client_id=${id}&limit=20`).catch(() => []),
    ])
      .then(([c, h]) => {
        setClient(c);
        setHistory(Array.isArray(h) ? h : []);
        setEditForm({
          full_name: c.full_name,
          zip_code: c.zip_code,
          age: c.age,
          income_level: c.income_level,
        });
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    setSaveMsg('');
    try {
      const updated = await api.put(`/clients/${id}`, {
        full_name: editForm.full_name,
        zip_code: editForm.zip_code,
        age: parseInt(editForm.age, 10),
        income_level: editForm.income_level,
      });
      setClient(updated);
      setSaveMsg('Saved');
      setTimeout(() => setSaveMsg(''), 2000);
    } catch (err) {
      setSaveMsg(`Error: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete ${client.full_name}? This cannot be undone.`)) return;
    try {
      await api.del(`/clients/${id}`);
      navigate('/clients');
    } catch (err) {
      setSaveMsg(`Error: ${err.message}`);
    }
  }

  if (loading) {
    return (
      <>
        <TopBar crumbs={['Clients', '…']} onMenuClick={openMenu} onNotificationsClick={openNotifications} />
        <div className="page">
          <div className="loader" />
        </div>
      </>
    );
  }

  if (error || !client) {
    return (
      <>
        <TopBar crumbs={['Clients', 'Not found']} onMenuClick={openMenu} onNotificationsClick={openNotifications} />
        <div className="page">
          <div className="empty">
            <div className="empty-title">Client not found</div>
            <div>{error || 'This client may have been deleted or does not belong to you.'}</div>
            <div style={{ marginTop: 18 }}>
              <button className="btn" onClick={() => navigate('/clients')}>
                <Icon name="arrow_l" size={14} /> Back to clients
              </button>
            </div>
          </div>
        </div>
      </>
    );
  }

  const incomeTone = client.income_level === 'high' ? 'accent' : client.income_level === 'medium' ? 'pos' : 'warn';

  return (
    <>
      <TopBar
        crumbs={['Clients', client.full_name]}
        onMenuClick={openMenu}
        onNotificationsClick={openNotifications}
        action={
          <>
            <button className="btn" onClick={() => navigate('/compare')}>
              <Icon name="compare" size={14} /> Run comparison
            </button>
            <button className="btn primary" onClick={() => navigate('/translator')}>
              <Icon name="translate" size={14} /> Translate coverage
            </button>
          </>
        }
      />
      <div className="page">
        <div style={{ marginBottom: 20 }}>
          <a onClick={() => navigate('/clients')} className="muted" style={{ fontSize: 13, cursor: 'pointer' }}>
            ← All clients
          </a>
        </div>

        <div className="profile-hero">
          <Avatar name={client.full_name} size="lg" />
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>#{client.id.slice(0, 8)}</div>
            <h1 style={{ fontFamily: 'var(--serif)', fontSize: 44, lineHeight: 1.05, letterSpacing: '-0.02em' }}>
              {client.full_name}
            </h1>
            <div className="row" style={{ gap: 12, marginTop: 14, flexWrap: 'wrap' }}>
              <Chip tone={incomeTone} dot>{client.income_level} income</Chip>
              <Chip>Age {client.age}</Chip>
              <Chip>ZIP {client.zip_code}</Chip>
              <Chip>{client.prescriptions?.length || 0} Rx</Chip>
              <Chip>{client.doctors?.length || 0} providers</Chip>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div className="eyebrow">Added</div>
            <div className="serif" style={{ fontSize: 22, marginTop: 4 }}>
              {new Date(client.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
            </div>
            <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
              Updated · {sinceLabel(client.updated_at)}
            </div>
          </div>
        </div>

        <div className="tabs-row" style={{ marginTop: 20 }}>
          {TABS.map((t) => (
            <button key={t} onClick={() => setTab(t)} className={`tab-btn ${tab === t ? 'active' : ''}`}>
              {t}
            </button>
          ))}
        </div>

        {tab === 'overview' && (
          <div className="grid-12" style={{ marginTop: 28 }}>
            <div style={{ gridColumn: 'span 8' }}>
              <div className="section-head" style={{ marginTop: 0 }}>
                <h2>At a glance</h2>
              </div>
              <div className="card card-pad">
                <div className="kv-grid">
                  <div className="kv"><span className="k">Full name</span><span className="v">{client.full_name}</span></div>
                  <div className="kv"><span className="k">Age</span><span className="v">{client.age}</span></div>
                  <div className="kv"><span className="k">ZIP</span><span className="v">{client.zip_code}</span></div>
                  <div className="kv"><span className="k">Income tier</span><span className="v" style={{ textTransform: 'capitalize' }}>{client.income_level}</span></div>
                  <div className="kv"><span className="k">Medicare eligible</span><span className="v">{client.age >= 65 ? 'Yes' : 'Not yet'}</span></div>
                  <div className="kv"><span className="k">Client since</span><span className="v">{new Date(client.created_at).toLocaleDateString()}</span></div>
                </div>
              </div>

              <div className="section-head"><h2>Medical profile</h2></div>
              <div className="grid-2">
                <div className="card card-pad">
                  <div className="between" style={{ marginBottom: 14 }}>
                    <div className="eyebrow">Prescriptions</div>
                    <span className="muted" style={{ fontSize: 12 }}>{client.prescriptions?.length || 0} active</span>
                  </div>
                  {!client.prescriptions?.length ? (
                    <div className="muted" style={{ fontSize: 13 }}>No prescriptions on file.</div>
                  ) : (
                    client.prescriptions.map((r, i) => (
                      <div
                        key={i}
                        className="between"
                        style={{
                          padding: '10px 0',
                          borderBottom: i < client.prescriptions.length - 1 ? '1px dashed var(--line)' : 0,
                        }}
                      >
                        <div className="row" style={{ gap: 10 }}>
                          <Icon name="pill" size={14} className="ink-4" />
                          <span style={{ fontSize: 13.5 }}>{r}</span>
                        </div>
                        <span className="muted mono" style={{ fontSize: 11.5 }}>Tier {((i % 4) + 1)}</span>
                      </div>
                    ))
                  )}
                </div>

                <div className="card card-pad">
                  <div className="between" style={{ marginBottom: 14 }}>
                    <div className="eyebrow">Providers</div>
                    <span className="muted" style={{ fontSize: 12 }}>{client.doctors?.length || 0} on file</span>
                  </div>
                  {!client.doctors?.length ? (
                    <div className="muted" style={{ fontSize: 13 }}>No providers on file.</div>
                  ) : (
                    client.doctors.map((d, i) => (
                      <div
                        key={i}
                        className="between"
                        style={{
                          padding: '10px 0',
                          borderBottom: i < client.doctors.length - 1 ? '1px dashed var(--line)' : 0,
                        }}
                      >
                        <div className="row" style={{ gap: 10 }}>
                          <Icon name="stethoscope" size={14} className="ink-4" />
                          <div>
                            <div style={{ fontSize: 13.5 }}>{d.name}</div>
                            {d.npi && <div className="muted" style={{ fontSize: 11.5 }}>NPI {d.npi}</div>}
                          </div>
                        </div>
                        <Chip tone="pos" dot>On file</Chip>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {client.procedures?.length > 0 && (
                <>
                  <div className="section-head"><h2>Expected care</h2></div>
                  <div className="card card-pad">
                    <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
                      {client.procedures.map((p, i) => <Chip key={i}>{p}</Chip>)}
                    </div>
                  </div>
                </>
              )}
            </div>

            <div style={{ gridColumn: 'span 4' }}>
              <div className="section-head" style={{ marginTop: 0 }}><h2>Recent actions</h2></div>
              <div className="card card-pad">
                {history.length === 0 ? (
                  <div className="muted" style={{ fontSize: 13 }}>
                    No actions yet. Run a comparison or verification to start the timeline.
                  </div>
                ) : (
                  history.slice(0, 6).map((a, i, arr) => (
                    <div
                      key={a.id || i}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '72px 1fr',
                        gap: 12,
                        padding: '10px 0',
                        borderBottom: i < arr.length - 1 ? '1px dashed var(--line)' : 0,
                      }}
                    >
                      <span className="muted mono" style={{ fontSize: 11 }}>{sinceLabel(a.created_at)}</span>
                      <div>
                        <div style={{ fontSize: 13, textTransform: 'capitalize' }}>{a.action_type.replace(/_/g, ' ')}</div>
                      </div>
                    </div>
                  ))
                )}
              </div>

              <div className="section-head"><h2>Quick tools</h2></div>
              <div className="card card-pad">
                {[
                  { icon: 'compare', label: 'Compare plans', path: '/compare' },
                  { icon: 'translate', label: 'Translate coverage', path: '/translator' },
                  { icon: 'network', label: 'Verify network', path: '/network' },
                  { icon: 'calculator', label: 'Estimate costs', path: '/calculator' },
                  { icon: 'appeal', label: 'Draft appeal', path: '/appeals' },
                ].map((t, i, a) => (
                  <div
                    key={t.path}
                    onClick={() => navigate(t.path)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      padding: '10px 0',
                      borderBottom: i < a.length - 1 ? '1px dashed var(--line)' : 0,
                      cursor: 'pointer',
                    }}
                  >
                    <Icon name={t.icon} size={16} className="ink-4" />
                    <span style={{ fontSize: 13.5, flex: 1 }}>{t.label}</span>
                    <Icon name="chev_r" size={13} className="ink-4" />
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {tab === 'coverage' && (
          <div className="card card-pad" style={{ marginTop: 28, padding: 60, textAlign: 'center' }}>
            <div className="placeholder-img" style={{ height: 240, marginBottom: 20 }}>coverage · pending</div>
            <div className="muted" style={{ maxWidth: 480, margin: '0 auto' }}>
              Once you run a plan comparison for {client.full_name}, enrolled plan details and formulary coverage will appear here.
            </div>
            <div style={{ marginTop: 20 }}>
              <button className="btn accent" onClick={() => navigate('/compare')}>
                <Icon name="compare" size={14} /> Run comparison
              </button>
            </div>
          </div>
        )}

        {tab === 'medical' && (
          <div className="grid-2" style={{ marginTop: 28 }}>
            <div className="card card-pad">
              <div className="eyebrow" style={{ marginBottom: 14 }}>Prescriptions ({client.prescriptions?.length || 0})</div>
              {!client.prescriptions?.length ? (
                <div className="muted" style={{ fontSize: 13 }}>None on file.</div>
              ) : (
                client.prescriptions.map((r, i) => (
                  <div key={i} className="row" style={{ padding: '8px 0', gap: 10 }}>
                    <Icon name="pill" size={14} className="ink-4" />
                    <span style={{ fontSize: 13.5 }}>{r}</span>
                  </div>
                ))
              )}
            </div>
            <div className="card card-pad">
              <div className="eyebrow" style={{ marginBottom: 14 }}>Providers ({client.doctors?.length || 0})</div>
              {!client.doctors?.length ? (
                <div className="muted" style={{ fontSize: 13 }}>None on file.</div>
              ) : (
                client.doctors.map((d, i) => (
                  <div key={i} className="row" style={{ padding: '8px 0', gap: 10 }}>
                    <Icon name="stethoscope" size={14} className="ink-4" />
                    <div>
                      <div style={{ fontSize: 13.5 }}>{d.name}</div>
                      {d.npi && <div className="muted" style={{ fontSize: 11.5 }}>NPI {d.npi}</div>}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {tab === 'activity' && (
          <div className="card card-pad" style={{ marginTop: 28 }}>
            {history.length === 0 ? (
              <div className="empty">
                <div className="empty-title">No activity yet</div>
                <div>Actions for this client will appear here.</div>
              </div>
            ) : (
              <div className="activity">
                {history.map((a, i) => (
                  <div key={a.id || i} className="act-row">
                    <span className="act-time mono">{sinceLabel(a.created_at)}</span>
                    <Chip>{a.action_type}</Chip>
                    <div className="act-body">
                      <span className="who" style={{ textTransform: 'capitalize' }}>
                        {a.action_type.replace(/_/g, ' ')}
                      </span>
                      <span className="muted"> session</span>
                    </div>
                    <Icon name="chev_r" size={14} className="ink-4" />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'edit' && (
          <form onSubmit={handleSave} className="card card-pad" style={{ marginTop: 28, maxWidth: 720 }}>
            <div className="eyebrow" style={{ marginBottom: 16 }}>Edit profile</div>
            <div className="grid-2">
              <div className="field">
                <label className="field-label">Full name</label>
                <input
                  className="input"
                  value={editForm.full_name}
                  onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                />
              </div>
              <div className="field">
                <label className="field-label">ZIP code</label>
                <input
                  className="input"
                  value={editForm.zip_code}
                  onChange={(e) => setEditForm({ ...editForm, zip_code: e.target.value })}
                />
              </div>
              <div className="field">
                <label className="field-label">Age</label>
                <input
                  className="input"
                  type="number"
                  value={editForm.age}
                  onChange={(e) => setEditForm({ ...editForm, age: e.target.value })}
                />
              </div>
              <div className="field">
                <label className="field-label">Income level</label>
                <select
                  className="select"
                  value={editForm.income_level}
                  onChange={(e) => setEditForm({ ...editForm, income_level: e.target.value })}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>
            </div>
            <div className="between" style={{ marginTop: 24 }}>
              <button type="button" className="btn danger" onClick={handleDelete}>
                <Icon name="trash" size={14} /> Delete client
              </button>
              <div className="row" style={{ gap: 10 }}>
                {saveMsg && <span className="muted" style={{ fontSize: 12 }}>{saveMsg}</span>}
                <button type="submit" className="btn accent" disabled={saving}>
                  {saving ? 'Saving…' : 'Save changes'}
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </>
  );
}
