import { useState, useEffect } from 'react';
import api from '../api/client';
import TopBar from '../components/TopBar';
import Icon from '../components/ui/Icon';
import Chip from '../components/ui/Chip';
import useLayout from '../components/ui/useLayout';
import DrugAutocomplete from '../components/ui/DrugAutocomplete';

export default function NetworkVerificationPage() {
  const { openMenu, openNotifications } = useLayout();
  const [clients, setClients] = useState([]);
  const [clientId, setClientId] = useState('');
  const [zip, setZip] = useState('10001');
  const [income, setIncome] = useState('medium');
  const [providers, setProviders] = useState([]);
  const [pName, setPName] = useState('');
  const [pNpi, setPNpi] = useState('');
  const [rx, setRx] = useState([]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/clients').then((d) => setClients(Array.isArray(d) ? d : [])).catch(() => {});
  }, []);

  function applyClient(c) {
    if (!c) { setClientId(''); return; }
    setClientId(c.id);
    setZip(c.zip_code);
    setIncome(c.income_level);
    setProviders(c.doctors || []);
    setRx(c.prescriptions || []);
  }

  async function run() {
    setError('');
    setRunning(true);
    try {
      const res = await api.post('/verify', {
        zip_code: zip,
        income_level: income,
        providers: providers.map((p) => ({ name: p.name, npi: p.npi || null })),
        prescriptions: rx,
      });
      setResult(res);
      if (clientId) {
        api.post('/history', {
          client_id: clientId,
          action_type: 'verify',
          request_data: { zip_code: zip, income_level: income, providers: providers.length, prescriptions: rx.length },
          response_summary: { plans: res.plans?.length || 0 },
        }).catch(() => {});
      }
    } catch (err) {
      setError(err.message || 'Verification failed');
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <TopBar
        crumbs={['Tools', 'Network verify']}
        onMenuClick={openMenu}
        onNotificationsClick={openNotifications}
      />
      <div className="page wide">
        <div className="page-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>Provider &amp; formulary check</div>
            <h1 className="page-title"><em>Verify</em> the network,<br />before you enroll.</h1>
            <p className="page-sub">
              Enter a client's doctors and prescriptions to see which Medicare Advantage plans keep everyone
              in-network and on-formulary.
            </p>
          </div>
        </div>

        <form className="card card-pad" style={{ padding: 32, marginBottom: 28 }} onSubmit={(e) => { e.preventDefault(); run(); }}>
          {clients.length > 0 && (
            <div className="field" style={{ marginBottom: 20 }}>
              <label className="field-label">Prefill from client</label>
              <select
                className="select"
                value={clientId}
                onChange={(e) => applyClient(clients.find((x) => x.id === e.target.value))}
              >
                <option value="">— none —</option>
                {clients.map((c) => (
                  <option key={c.id} value={c.id}>{c.full_name} · ZIP {c.zip_code}</option>
                ))}
              </select>
            </div>
          )}

          <div className="grid-12" style={{ gap: 20 }}>
            <div className="field" style={{ gridColumn: 'span 3' }}>
              <label className="field-label">ZIP code</label>
              <input className="input" value={zip} onChange={(e) => setZip(e.target.value)} pattern="\d{5}" required />
            </div>
            <div className="field" style={{ gridColumn: 'span 3' }}>
              <label className="field-label">Income</label>
              <select className="select" value={income} onChange={(e) => setIncome(e.target.value)}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </div>
          </div>

          <div className="divider" />

          <div className="grid-2">
            <div>
              <div className="eyebrow" style={{ marginBottom: 12 }}>Providers</div>
              <div className="input-group">
                <input className="input" placeholder="Dr. name" value={pName} onChange={(e) => setPName(e.target.value)} />
                <input className="input" placeholder="NPI (optional)" value={pNpi} onChange={(e) => setPNpi(e.target.value)} style={{ maxWidth: 180 }} />
                <button
                  type="button"
                  className="btn"
                  onClick={() => {
                    if (!pName.trim()) return;
                    setProviders([...providers, { name: pName.trim(), npi: pNpi.trim() || null }]);
                    setPName('');
                    setPNpi('');
                  }}
                >
                  Add
                </button>
              </div>
              <div className="col" style={{ gap: 6, marginTop: 12 }}>
                {providers.map((p, i) => (
                  <div key={i} className="between" style={{ padding: '8px 12px', border: '1px solid var(--line)', borderRadius: 6 }}>
                    <div className="row" style={{ gap: 10 }}>
                      <Icon name="stethoscope" size={14} className="ink-4" />
                      <span style={{ fontSize: 13.5 }}>{p.name}</span>
                      {p.npi && <span className="muted mono" style={{ fontSize: 11.5 }}>NPI {p.npi}</span>}
                    </div>
                    <button type="button" className="btn ghost icon sm" onClick={() => setProviders(providers.filter((_, j) => j !== i))}>
                      <Icon name="x" size={12} />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="eyebrow" style={{ marginBottom: 12 }}>Prescriptions</div>
              <DrugAutocomplete values={rx} onChange={setRx} placeholder="Medication name" />
            </div>
          </div>

          {error && <div className="notice" style={{ marginTop: 20, color: 'var(--neg)', borderColor: 'var(--neg)' }}>{error}</div>}

          <div className="row" style={{ justifyContent: 'flex-end', marginTop: 20, gap: 10 }}>
            <button type="submit" className="btn accent" disabled={running || (providers.length === 0 && rx.length === 0)}>
              {running ? <><span className="loader" /> Checking…</> : <><Icon name="network" size={14} /> Verify coverage</>}
            </button>
          </div>
        </form>

        {result && (
          <>
            {result.recommendation && (
              <div className="card card-pad" style={{ marginBottom: 28 }}>
                <div className="eyebrow" style={{ marginBottom: 10 }}>Recommendation</div>
                <p style={{ fontFamily: 'var(--serif)', fontSize: 20, letterSpacing: '-0.01em', lineHeight: 1.4 }}>
                  {result.recommendation}
                </p>
              </div>
            )}

            <div className="section-head" style={{ marginTop: 0 }}>
              <h2>Plan-by-plan</h2>
              <div className="after">{result.plans?.length || 0} plans checked</div>
            </div>

            <div className="col" style={{ gap: 16 }}>
              {(result.plans || []).map((plan) => {
                const providersIn = plan.provider_results.filter((r) => r.in_network).length;
                const providersTotal = plan.provider_results.length;
                const formularyCovered = plan.formulary_results.filter((r) => r.on_formulary).length;
                const formularyTotal = plan.formulary_results.length;
                const allClean = providersIn === providersTotal && formularyCovered === formularyTotal;
                return (
                  <div key={plan.plan_id} className="card card-pad">
                    <div className="between" style={{ marginBottom: 16 }}>
                      <div>
                        <div style={{ fontFamily: 'var(--serif)', fontSize: 20, letterSpacing: '-0.01em' }}>{plan.plan_name}</div>
                        <div className="muted mono" style={{ fontSize: 11, marginTop: 2 }}>{plan.plan_id}</div>
                      </div>
                      <Chip tone={allClean ? 'pos' : 'warn'} dot>
                        {allClean ? 'Full coverage' : 'Has gaps'}
                      </Chip>
                    </div>
                    <div className="grid-2">
                      <div>
                        <div className="eyebrow" style={{ marginBottom: 10 }}>Providers · {providersIn}/{providersTotal} in-network</div>
                        {plan.provider_results.length === 0 && <div className="muted" style={{ fontSize: 13 }}>No providers entered.</div>}
                        {plan.provider_results.map((p, i, a) => (
                          <div key={i} className="between" style={{ padding: '8px 0', borderBottom: i < a.length - 1 ? '1px dashed var(--line)' : 0 }}>
                            <div className="row" style={{ gap: 10 }}>
                              <Icon name="stethoscope" size={14} className="ink-4" />
                              <div>
                                <div style={{ fontSize: 13 }}>{p.name}</div>
                                {p.specialty && <div className="muted" style={{ fontSize: 11 }}>{p.specialty}</div>}
                                {p.warning && <div style={{ color: 'var(--warn)', fontSize: 11, marginTop: 2 }}>{p.warning}</div>}
                              </div>
                            </div>
                            <Chip tone={p.in_network ? 'pos' : 'neg'} dot>
                              {p.in_network ? 'In-network' : 'Out'}
                            </Chip>
                          </div>
                        ))}
                      </div>

                      <div>
                        <div className="eyebrow" style={{ marginBottom: 10 }}>Formulary · {formularyCovered}/{formularyTotal} covered</div>
                        {plan.formulary_results.length === 0 && <div className="muted" style={{ fontSize: 13 }}>No prescriptions entered.</div>}
                        {plan.formulary_results.map((f, i, a) => (
                          <div key={i} className="between" style={{ padding: '8px 0', borderBottom: i < a.length - 1 ? '1px dashed var(--line)' : 0 }}>
                            <div className="row" style={{ gap: 10 }}>
                              <Icon name="pill" size={14} className="ink-4" />
                              <div>
                                <div style={{ fontSize: 13 }}>{f.drug_name}</div>
                                {f.tier && <div className="muted mono" style={{ fontSize: 11 }}>Tier {f.tier}</div>}
                                {f.prior_auth_required && <div style={{ color: 'var(--warn)', fontSize: 11, marginTop: 2 }}>Prior auth required</div>}
                              </div>
                            </div>
                            <Chip tone={f.on_formulary ? 'pos' : 'neg'} dot>
                              {f.on_formulary ? (f.copay != null ? `$${f.copay}` : 'Covered') : 'Not covered'}
                            </Chip>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {result.disclaimer && <div className="notice" style={{ marginTop: 24 }}>{result.disclaimer}</div>}
          </>
        )}
      </div>
    </>
  );
}
