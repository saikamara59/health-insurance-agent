import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import api from '../api/client';
import TopBar from '../components/TopBar';
import Icon from '../components/ui/Icon';
import Stars from '../components/ui/Stars';
import useLayout from '../components/ui/useLayout';

function currency(v) {
  if (v == null || Number.isNaN(v)) return '—';
  return `$${Math.round(v).toLocaleString()}`;
}

function annualEstimate(plan) {
  const premium = (plan.monthly_premium || 0) * 12;
  const rxTotal = Object.values(plan.estimated_medication_costs || {}).reduce((s, v) => s + v, 0);
  const procTotal = Object.values(plan.estimated_procedure_costs || {}).reduce((s, v) => s + v, 0);
  return premium + rxTotal + procTotal + (plan.annual_deductible || 0) * 0.3;
}

export default function PlanComparisonPage() {
  const location = useLocation();
  const { openMenu, openNotifications } = useLayout();

  const preset = location.state?.client;
  const [step, setStep] = useState('input');
  const [clientId, setClientId] = useState(preset?.id || '');
  const [clientOptions, setClientOptions] = useState([]);
  const [zip, setZip] = useState(preset?.zip_code || '10001');
  const [age, setAge] = useState(preset?.age || 67);
  const [income, setIncome] = useState(preset?.income_level || 'medium');
  const [rx, setRx] = useState(preset?.prescriptions || []);
  const [rxInput, setRxInput] = useState('');
  const [procInput, setProcInput] = useState('');
  const [procs, setProcs] = useState(preset?.procedures || []);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/clients').then((d) => setClientOptions(Array.isArray(d) ? d : [])).catch(() => {});
  }, []);

  function applyClient(c) {
    if (!c) return;
    setClientId(c.id);
    setZip(c.zip_code);
    setAge(c.age);
    setIncome(c.income_level);
    setRx(c.prescriptions || []);
    setProcs(c.procedures || []);
  }

  async function run() {
    setError('');
    setRunning(true);
    try {
      const data = await api.post('/compare', {
        zip_code: zip,
        age: parseInt(age, 10),
        income_level: income,
        medications: rx,
        procedures: procs,
      });
      setResult(data);
      setStep('results');
      if (clientId) {
        api.post('/history', {
          client_id: clientId,
          action_type: 'compare',
          request_data: { zip_code: zip, age, income_level: income },
          response_summary: { plans: data.plans?.length || 0, session_id: data.session_id },
        }).catch(() => {});
      }
    } catch (err) {
      setError(err.message || 'Comparison failed');
    } finally {
      setRunning(false);
    }
  }

  const plans = result?.plans || [];
  const annuals = plans.map(annualEstimate);
  const cheapestIdx = annuals.length ? annuals.indexOf(Math.min(...annuals)) : -1;
  const selectedClient = clientOptions.find((c) => c.id === clientId);

  const rows = plans.length > 0
    ? [
        { k: 'Est. annual cost', vals: annuals, fmt: currency },
        { k: 'Monthly premium', vals: plans.map((p) => p.monthly_premium), fmt: (v) => `$${v}` },
        { k: 'Deductible', vals: plans.map((p) => p.annual_deductible), fmt: currency },
        { k: 'Out-of-pocket max', vals: plans.map((p) => p.out_of_pocket_max), fmt: currency },
      ]
    : [];

  return (
    <>
      <TopBar
        crumbs={['Tools', 'Plan comparison']}
        onMenuClick={openMenu}
        onNotificationsClick={openNotifications}
        action={
          step === 'results' && (
            <button className="btn" onClick={() => setStep('input')}>
              <Icon name="settings" size={14} /> Edit inputs
            </button>
          )
        }
      />
      <div className="page wide">
        <div className="page-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>
              {selectedClient ? `For · ${selectedClient.full_name} · ${zip}` : `ZIP ${zip}`}
            </div>
            <h1 className="page-title">
              {step === 'results' && cheapestIdx >= 0
                ? <>Plans compared,<br /><em>one clear choice.</em></>
                : <><em>Compare</em> Medicare Advantage plans.</>}
            </h1>
            <p className="page-sub">
              Real-time CMS plan filings for the ZIP you enter, ranked by total cost given the client's medications
              and expected procedures. Star rating is CMS 2026.
            </p>
          </div>
        </div>

        {step === 'input' && (
          <form
            className="card card-pad"
            style={{ padding: 32, marginBottom: 32 }}
            onSubmit={(e) => { e.preventDefault(); run(); }}
          >
            {clientOptions.length > 0 && (
              <div className="field" style={{ marginBottom: 20 }}>
                <label className="field-label">Prefill from client (optional)</label>
                <select
                  className="select"
                  value={clientId}
                  onChange={(e) => {
                    const c = clientOptions.find((x) => x.id === e.target.value);
                    if (c) applyClient(c);
                    else setClientId('');
                  }}
                >
                  <option value="">— none —</option>
                  {clientOptions.map((c) => (
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
                <label className="field-label">Age</label>
                <input className="input" type="number" value={age} onChange={(e) => setAge(e.target.value)} required />
              </div>
              <div className="field" style={{ gridColumn: 'span 3' }}>
                <label className="field-label">Income level</label>
                <select className="select" value={income} onChange={(e) => setIncome(e.target.value)}>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>
              <div className="field" style={{ gridColumn: 'span 6' }}>
                <label className="field-label">Medications</label>
                <div className="input-group">
                  <input
                    className="input"
                    placeholder="e.g. Metformin 500mg"
                    value={rxInput}
                    onChange={(e) => setRxInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        if (rxInput.trim()) { setRx([...rx, rxInput.trim()]); setRxInput(''); }
                      }
                    }}
                  />
                  <button type="button" className="btn" onClick={() => {
                    if (rxInput.trim()) { setRx([...rx, rxInput.trim()]); setRxInput(''); }
                  }}>Add</button>
                </div>
                <div className="row" style={{ gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                  {rx.map((r, i) => (
                    <span key={i} className="chip">
                      {r}
                      <button type="button" onClick={() => setRx(rx.filter((_, j) => j !== i))} style={{ marginLeft: 4, color: 'var(--ink-4)' }}>
                        <Icon name="x" size={10} />
                      </button>
                    </span>
                  ))}
                </div>
              </div>
              <div className="field" style={{ gridColumn: 'span 6' }}>
                <label className="field-label">Expected procedures</label>
                <div className="input-group">
                  <input
                    className="input"
                    placeholder="e.g. Annual physical"
                    value={procInput}
                    onChange={(e) => setProcInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        if (procInput.trim()) { setProcs([...procs, procInput.trim()]); setProcInput(''); }
                      }
                    }}
                  />
                  <button type="button" className="btn" onClick={() => {
                    if (procInput.trim()) { setProcs([...procs, procInput.trim()]); setProcInput(''); }
                  }}>Add</button>
                </div>
                <div className="row" style={{ gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                  {procs.map((p, i) => (
                    <span key={i} className="chip">
                      {p}
                      <button type="button" onClick={() => setProcs(procs.filter((_, j) => j !== i))} style={{ marginLeft: 4, color: 'var(--ink-4)' }}>
                        <Icon name="x" size={10} />
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {error && (
              <div className="notice" style={{ marginTop: 20, color: 'var(--neg)', borderColor: 'var(--neg)' }}>
                {error}
              </div>
            )}

            <div className="row" style={{ justifyContent: 'flex-end', marginTop: 20, gap: 10 }}>
              <button type="submit" className="btn accent" disabled={running}>
                {running ? <><span className="loader" /> Running…</> : <><Icon name="compare" size={14} /> Compare plans</>}
              </button>
            </div>
          </form>
        )}

        {step === 'results' && result && (
          <>
            {result.recommendation && (
              <div className="card" style={{ marginBottom: 28, overflow: 'hidden' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px' }}>
                  <div style={{ padding: 28 }}>
                    <div className="eyebrow" style={{ marginBottom: 10 }}>Recommendation</div>
                    <p
                      style={{
                        fontFamily: 'var(--serif)',
                        fontSize: 22,
                        letterSpacing: '-0.01em',
                        lineHeight: 1.35,
                        maxWidth: 620,
                      }}
                    >
                      {result.recommendation}
                    </p>
                  </div>
                  {cheapestIdx >= 0 && (
                    <div style={{ background: 'var(--bg-2)', borderLeft: '1px solid var(--line)', padding: 28 }}>
                      <div className="eyebrow" style={{ marginBottom: 14 }}>Cheapest estimate</div>
                      <div style={{ fontFamily: 'var(--serif)', fontSize: 44, letterSpacing: '-0.02em', lineHeight: 1 }}>
                        {currency(annuals[cheapestIdx])}
                      </div>
                      <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>{plans[cheapestIdx].plan_name}</div>
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="grid-3">
              {plans.map((p, i) => {
                const isBest = i === cheapestIdx;
                return (
                  <div key={p.plan_id || i} data-testid="plan-row" className={`plan-card ${isBest ? 'best' : ''}`}>
                    {isBest && <span className="best-tag">Best value</span>}
                    <div>
                      <div className="eyebrow">{p.plan_type}</div>
                      <h3 style={{ fontFamily: 'var(--serif)', fontSize: 22, lineHeight: 1.2, marginTop: 6 }}>{p.plan_name}</h3>
                      <div className="row" style={{ gap: 10, marginTop: 10 }}>
                        <Stars value={p.star_rating} />
                        <span className="muted mono" style={{ fontSize: 11 }}>
                          {p.star_rating?.toFixed(1)} · {p.drug_coverage ? 'Rx included' : 'No Rx'}
                        </span>
                      </div>
                    </div>

                    <div className="plan-metrics">
                      <div className="plan-metric"><div className="k">Premium</div><div className="v num">${p.monthly_premium}<small>/mo</small></div></div>
                      <div className="plan-metric"><div className="k">Deductible</div><div className="v num">{currency(p.annual_deductible)}</div></div>
                      <div className="plan-metric"><div className="k">OOP max</div><div className="v num">{currency(p.out_of_pocket_max)}</div></div>
                      <div className="plan-metric"><div className="k">Est. annual</div><div className="v num">{currency(annuals[i])}</div></div>
                    </div>

                    <div className="row" style={{ gap: 8, marginTop: 'auto' }}>
                      <button className={`btn ${isBest ? 'accent' : ''}`} style={{ flex: 1 }}>
                        {isBest ? 'Recommend' : 'Select'}
                      </button>
                      <button className="btn ghost icon" aria-label="More">
                        <Icon name="dot3" size={14} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            {rows.length > 0 && (
              <>
                <div className="section-head" style={{ marginTop: 40 }}>
                  <h2>Side by side</h2>
                  <div className="after">Lower bars are better</div>
                </div>
                <div className="card card-pad">
                  {rows.map((row, ri) => {
                    const max = Math.max(...row.vals.map((v) => v || 0));
                    return (
                      <div key={ri} style={{ padding: '16px 0', borderBottom: ri < rows.length - 1 ? '1px dashed var(--line)' : 0 }}>
                        <div className="between" style={{ marginBottom: 10 }}>
                          <div style={{ fontSize: 13 }}>{row.k}</div>
                          <div className="muted mono" style={{ fontSize: 11 }}>{plans.length} plans</div>
                        </div>
                        {row.vals.map((v, i) => (
                          <div key={i} className="cbar-row">
                            <div className="row" style={{ gap: 8, minWidth: 0 }}>
                              <span className={`risk-dot ${i === cheapestIdx ? '' : 'med'}`} style={i === cheapestIdx ? { background: 'var(--accent)' } : {}} />
                              <span style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {plans[i].plan_name}
                              </span>
                            </div>
                            <div className="cbar-track">
                              <div
                                className={`cbar-fill ${i === cheapestIdx ? '' : 'muted'}`}
                                style={{ width: max === 0 ? '2%' : `${Math.max(2, ((v || 0) / max) * 100)}%` }}
                              />
                            </div>
                            <div className="num mono" style={{ fontSize: 13, textAlign: 'right' }}>{row.fmt(v)}</div>
                          </div>
                        ))}
                      </div>
                    );
                  })}
                </div>
              </>
            )}

            {result.disclaimer && <div className="notice" style={{ marginTop: 24 }}>{result.disclaimer}</div>}
          </>
        )}
      </div>
    </>
  );
}
