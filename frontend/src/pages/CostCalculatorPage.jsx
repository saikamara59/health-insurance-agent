import { useState, useEffect } from 'react';
import api from '../api/client';
import TopBar from '../components/TopBar';
import Icon from '../components/ui/Icon';
import useLayout from '../components/ui/useLayout';

function currency(v) {
  if (v == null || Number.isNaN(v)) return '—';
  return `$${Math.round(v).toLocaleString()}`;
}

export default function CostCalculatorPage() {
  const { openMenu, openNotifications } = useLayout();
  const [clients, setClients] = useState([]);
  const [clientId, setClientId] = useState('');
  const [zip, setZip] = useState('10001');
  const [income, setIncome] = useState('medium');
  const [visits, setVisits] = useState(12);
  const [rx, setRx] = useState([]);
  const [rxName, setRxName] = useState('');
  const [rxFills, setRxFills] = useState(12);
  const [procs, setProcs] = useState([]);
  const [procName, setProcName] = useState('');
  const [procCount, setProcCount] = useState(1);
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
    setRx((c.prescriptions || []).map((name) => ({ name, fills_per_year: 12 })));
    setProcs((c.procedures || []).map((name) => ({ name, count: 1 })));
  }

  async function run() {
    setError('');
    setRunning(true);
    try {
      const res = await api.post('/calculate', {
        zip_code: zip,
        income_level: income,
        usage: {
          doctor_visits_per_year: parseInt(visits, 10),
          prescriptions: rx,
          procedures: procs,
        },
      });
      setResult(res);
      if (clientId) {
        api.post('/history', {
          client_id: clientId,
          action_type: 'calculate',
          request_data: { zip_code: zip, visits, prescriptions: rx.length },
          response_summary: { plans: res.plans?.length || 0 },
        }).catch(() => {});
      }
    } catch (err) {
      setError(err.message || 'Calculation failed');
    } finally {
      setRunning(false);
    }
  }

  const plans = result?.plans || [];
  const cheapest = plans.length ? plans.reduce((a, b) => (a.total_annual_cost < b.total_annual_cost ? a : b)) : null;

  return (
    <>
      <TopBar crumbs={['Tools', 'Cost calculator']} onMenuClick={openMenu} onNotificationsClick={openNotifications} />
      <div className="page wide" style={{ fontFamily: '"Times New Roman"' }}>
        <div className="page-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>Project annual spend</div>
            <h1 className="page-title"><em>Calculate</em> full-year cost.</h1>
            <p className="page-sub">
              Project a client's total out-of-pocket spend across premiums, deductibles, prescription tiers, and
              expected procedures — for every plan in their ZIP.
            </p>
          </div>
        </div>

        <form className="card card-pad" style={{ padding: 32, marginBottom: 28 }} onSubmit={(e) => { e.preventDefault(); run(); }}>
          {clients.length > 0 && (
            <div className="field" style={{ marginBottom: 20 }}>
              <label className="field-label">Prefill from client</label>
              <select className="select" value={clientId} onChange={(e) => applyClient(clients.find((x) => x.id === e.target.value))}>
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
              <label className="field-label">Income level</label>
              <select className="select" value={income} onChange={(e) => setIncome(e.target.value)}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </div>
            <div className="field" style={{ gridColumn: 'span 3' }}>
              <label className="field-label">Doctor visits / year</label>
              <input className="input" type="number" min="0" max="100" value={visits} onChange={(e) => setVisits(e.target.value)} />
            </div>
          </div>

          <div className="divider" />

          <div className="grid-2">
            <div>
              <div className="eyebrow" style={{ marginBottom: 12 }}>Prescriptions · annual fills</div>
              <div className="input-group">
                <input className="input" placeholder="Medication" value={rxName} onChange={(e) => setRxName(e.target.value)} />
                <input
                  className="input"
                  type="number"
                  min="1"
                  max="365"
                  style={{ maxWidth: 100 }}
                  value={rxFills}
                  onChange={(e) => setRxFills(e.target.value)}
                />
                <button type="button" className="btn" onClick={() => {
                  if (!rxName.trim()) return;
                  setRx([...rx, { name: rxName.trim(), fills_per_year: parseInt(rxFills, 10) || 12 }]);
                  setRxName(''); setRxFills(12);
                }}>Add</button>
              </div>
              <div className="col" style={{ gap: 6, marginTop: 12 }}>
                {rx.map((r, i) => (
                  <div key={i} className="between" style={{ padding: '8px 12px', border: '1px solid var(--line)', borderRadius: 6 }}>
                    <div className="row" style={{ gap: 10 }}>
                      <Icon name="pill" size={14} className="ink-4" />
                      <span style={{ fontSize: 13.5 }}>{r.name}</span>
                    </div>
                    <span className="muted mono" style={{ fontSize: 11.5 }}>{r.fills_per_year}×/yr</span>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="eyebrow" style={{ marginBottom: 12 }}>Procedures · annual count</div>
              <div className="input-group">
                <input className="input" placeholder="Procedure" value={procName} onChange={(e) => setProcName(e.target.value)} />
                <input
                  className="input"
                  type="number"
                  min="1"
                  max="52"
                  style={{ maxWidth: 100 }}
                  value={procCount}
                  onChange={(e) => setProcCount(e.target.value)}
                />
                <button type="button" className="btn" onClick={() => {
                  if (!procName.trim()) return;
                  setProcs([...procs, { name: procName.trim(), count: parseInt(procCount, 10) || 1 }]);
                  setProcName(''); setProcCount(1);
                }}>Add</button>
              </div>
              <div className="col" style={{ gap: 6, marginTop: 12 }}>
                {procs.map((p, i) => (
                  <div key={i} className="between" style={{ padding: '8px 12px', border: '1px solid var(--line)', borderRadius: 6 }}>
                    <div className="row" style={{ gap: 10 }}>
                      <Icon name="note" size={14} className="ink-4" />
                      <span style={{ fontSize: 13.5 }}>{p.name}</span>
                    </div>
                    <span className="muted mono" style={{ fontSize: 11.5 }}>{p.count}×/yr</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {error && <div className="notice" style={{ marginTop: 20, color: 'var(--neg)', borderColor: 'var(--neg)' }}>{error}</div>}

          <div className="row" style={{ justifyContent: 'flex-end', marginTop: 20 }}>
            <button type="submit" className="btn accent" disabled={running}>
              {running ? <><span className="loader" /> Calculating…</> : <><Icon name="calculator" size={14} /> Estimate cost</>}
            </button>
          </div>
        </form>

        {result && (
          <>
            {cheapest && (
              <div className="card" style={{ marginBottom: 28, overflow: 'hidden' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px' }}>
                  <div style={{ padding: 28 }}>
                    <div className="eyebrow" style={{ marginBottom: 10 }}>Best value</div>
                    <h2 style={{ fontFamily: 'var(--serif)', fontSize: 26, letterSpacing: '-0.01em', lineHeight: 1.25 }}>
                      <em style={{ color: 'var(--accent)' }}>{cheapest.plan_name}</em> — {currency(cheapest.total_annual_cost)} projected for the year.
                    </h2>
                  </div>
                  <div style={{ background: 'var(--bg-2)', borderLeft: '1px solid var(--line)', padding: 28 }}>
                    <div className="eyebrow" style={{ marginBottom: 14 }}>Annual estimate</div>
                    <div style={{ fontFamily: 'var(--serif)', fontSize: 44, letterSpacing: '-0.02em', lineHeight: 1 }}>
                      {currency(cheapest.total_annual_cost)}
                    </div>
                    <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>
                      {currency(cheapest.annual_premium)} premium · {currency(cheapest.annual_care_cost)} care
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div className="section-head" style={{ marginTop: 0 }}><h2>All plans</h2></div>
            <div className="col" style={{ gap: 16 }}>
              {plans.map((p) => (
                <div key={p.plan_id} className={`plan-card ${p === cheapest ? 'best' : ''}`}>
                  {p === cheapest && <span className="best-tag">Cheapest</span>}
                  <div className="between" style={{ alignItems: 'flex-start' }}>
                    <div>
                      <div style={{ fontFamily: 'var(--serif)', fontSize: 20, letterSpacing: '-0.01em' }}>{p.plan_name}</div>
                      <div className="muted mono" style={{ fontSize: 11, marginTop: 2 }}>{p.plan_id}</div>
                    </div>
                    <div style={{ fontFamily: 'var(--serif)', fontSize: 28, letterSpacing: '-0.01em' }}>
                      {currency(p.total_annual_cost)}
                      <div className="muted" style={{ fontSize: 11, fontFamily: 'var(--mono)', marginTop: 4, textAlign: 'right' }}>annual</div>
                    </div>
                  </div>
                  <div className="plan-metrics" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
                    <div className="plan-metric"><div className="k">Premium</div><div className="v num">{currency(p.annual_premium)}</div></div>
                    <div className="plan-metric"><div className="k">Visits</div><div className="v num">{currency(p.breakdown?.doctor_visit_costs)}</div></div>
                    <div className="plan-metric"><div className="k">Rx</div><div className="v num">{currency(p.breakdown?.prescription_costs)}</div></div>
                    <div className="plan-metric"><div className="k">Procedures</div><div className="v num">{currency(p.breakdown?.procedure_costs)}</div></div>
                  </div>
                  {p.breakdown?.oop_cap_applied && (
                    <div className="notice" style={{ marginTop: 0 }}>
                      Out-of-pocket cap applied. Costs above the cap aren't counted here.
                    </div>
                  )}
                </div>
              ))}
            </div>

            {result.disclaimer && <div className="notice" style={{ marginTop: 24 }}>{result.disclaimer}</div>}
          </>
        )}
      </div>
    </>
  );
}
