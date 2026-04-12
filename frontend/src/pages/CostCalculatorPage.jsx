import { useState } from 'react'
import api from '../api/client'

export default function CostCalculatorPage() {
  const [form, setForm] = useState({ zip_code: '', income_level: 'medium', doctor_visits: 12, prescriptions: [], procedures: [] })
  const [rxName, setRxName] = useState('')
  const [rxFills, setRxFills] = useState(12)
  const [procName, setProcName] = useState('')
  const [procCount, setProcCount] = useState(1)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState(null)

  function addRx() { if (rxName.trim()) { setForm({ ...form, prescriptions: [...form.prescriptions, { name: rxName.trim(), fills_per_year: rxFills }] }); setRxName(''); setRxFills(12) } }
  function addProc() { if (procName.trim()) { setForm({ ...form, procedures: [...form.procedures, { name: procName.trim(), count: procCount }] }); setProcName(''); setProcCount(1) } }

  async function handleCalculate() {
    if (!form.zip_code) return
    setLoading(true); setError(''); setResult(null)
    try {
      const data = await api.post('/calculate', {
        zip_code: form.zip_code,
        income_level: form.income_level,
        usage: { doctor_visits_per_year: form.doctor_visits, prescriptions: form.prescriptions, procedures: form.procedures },
      })
      setResult(data)
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  const plans = result?.plans || []
  const cheapest = plans[0]
  const mostExpensive = plans[plans.length - 1]
  const savings = cheapest && mostExpensive ? (mostExpensive.total_annual_cost - cheapest.total_annual_cost).toFixed(0) : 0

  return (
    <>
      <div className="mb-10">
        <span className="uppercase tracking-widest text-[11px] font-semibold text-secondary mb-2 block">Premium Analysis Tool</span>
        <h1 className="font-display text-4xl text-primary font-bold mb-4">Plan Cost Projections</h1>
        <p className="text-outline max-w-2xl leading-relaxed">Adjust your clinical utilization metrics to see a detailed annual cost breakdown across plans.</p>
      </div>

      <div className="grid grid-cols-12 gap-8">
        {/* Input Sidebar */}
        <section className="col-span-12 lg:col-span-4 xl:col-span-3 space-y-6">
          <div className="bg-surface-container-low p-6 rounded-lg">
            <h2 className="font-headline font-bold text-primary text-lg mb-6 flex items-center gap-2">
              <span className="material-symbols-outlined text-primary">tune</span> Utilization Inputs
            </h2>

            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="uppercase tracking-widest text-[10px] font-bold text-slate-600 mb-2 block">Zip Code</label>
                  <input className="w-full bg-surface-container-highest border-0 border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-sm font-bold py-2 px-0"
                    placeholder="10001" value={form.zip_code} onChange={(e) => setForm({ ...form, zip_code: e.target.value })} maxLength={5} />
                </div>
                <div>
                  <label className="uppercase tracking-widest text-[10px] font-bold text-slate-600 mb-2 block">Income</label>
                  <select className="w-full bg-surface-container-highest border-0 border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-sm font-bold py-2 px-0"
                    value={form.income_level} onChange={(e) => setForm({ ...form, income_level: e.target.value })}>
                    <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option>
                  </select>
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="uppercase tracking-widest text-[10px] font-bold text-slate-600">Doctor Visits / Year</label>
                  <span className="font-headline font-bold text-primary">{form.doctor_visits}</span>
                </div>
                <input type="range" min="0" max="52" value={form.doctor_visits}
                  onChange={(e) => setForm({ ...form, doctor_visits: parseInt(e.target.value) })}
                  className="w-full h-1.5 bg-surface-container-high rounded-lg appearance-none cursor-pointer accent-primary" />
              </div>

              {/* Prescriptions */}
              <div>
                <label className="uppercase tracking-widest text-[10px] font-bold text-slate-600 mb-2 block">Prescriptions</label>
                <div className="flex gap-2 mb-2">
                  <input className="flex-1 bg-surface-container-highest border-0 border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-xs py-2 px-0" placeholder="Drug name" value={rxName} onChange={(e) => setRxName(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addRx() } }} />
                  <input type="number" className="w-16 bg-surface-container-highest border-0 border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-xs py-2 px-0 text-center" min={1} max={365} value={rxFills} onChange={(e) => setRxFills(parseInt(e.target.value) || 1)} />
                  <button onClick={addRx} className="px-3 py-1 bg-primary text-white rounded text-[10px] font-bold">+</button>
                </div>
                {form.prescriptions.map((rx, i) => (
                  <div key={i} className="flex justify-between items-center text-xs py-1.5 border-b border-slate-50">
                    <span className="font-medium">{rx.name}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-slate-400">{rx.fills_per_year}x/yr</span>
                      <button onClick={() => setForm({ ...form, prescriptions: form.prescriptions.filter((_, j) => j !== i) })} className="text-slate-300 hover:text-error"><span className="material-symbols-outlined text-xs">close</span></button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Procedures */}
              <div>
                <label className="uppercase tracking-widest text-[10px] font-bold text-slate-600 mb-2 block">Procedures</label>
                <div className="flex gap-2 mb-2">
                  <input className="flex-1 bg-surface-container-highest border-0 border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-xs py-2 px-0" placeholder="Procedure" value={procName} onChange={(e) => setProcName(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addProc() } }} />
                  <input type="number" className="w-16 bg-surface-container-highest border-0 border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-xs py-2 px-0 text-center" min={1} max={365} value={procCount} onChange={(e) => setProcCount(parseInt(e.target.value) || 1)} />
                  <button onClick={addProc} className="px-3 py-1 bg-primary text-white rounded text-[10px] font-bold">+</button>
                </div>
                {form.procedures.map((p, i) => (
                  <div key={i} className="flex justify-between items-center text-xs py-1.5 border-b border-slate-50">
                    <span className="font-medium">{p.name}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-slate-400">{p.count}x</span>
                      <button onClick={() => setForm({ ...form, procedures: form.procedures.filter((_, j) => j !== i) })} className="text-slate-300 hover:text-error"><span className="material-symbols-outlined text-xs">close</span></button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <button onClick={handleCalculate} disabled={loading || !form.zip_code}
              className="w-full mt-8 bg-primary text-white py-3 rounded font-headline font-bold shadow-md hover:bg-primary-container transition-all disabled:opacity-50 flex items-center justify-center gap-2">
              {loading ? <><span className="material-symbols-outlined animate-spin">progress_activity</span> Calculating...</> : 'Update Analysis'}
            </button>
          </div>

          {/* Savings Card */}
          {result && cheapest && (
            <div className="bg-primary text-white p-6 rounded-lg relative overflow-hidden">
              <div className="relative z-10">
                <span className="uppercase tracking-widest text-[10px] font-bold opacity-70">Projected Efficiency</span>
                <div className="mt-2 mb-1 flex items-baseline gap-1">
                  <span className="text-3xl font-headline font-extrabold">${Number(savings).toLocaleString()}</span>
                  <span className="text-xs opacity-80 uppercase tracking-widest font-bold">Annual Delta</span>
                </div>
                <p className="text-xs leading-relaxed opacity-90">
                  Switching to <span className="font-bold">{cheapest.plan_name}</span> saves the most in total out-of-pocket costs.
                </p>
              </div>
              <div className="absolute -right-4 -bottom-4 opacity-10">
                <span className="material-symbols-outlined text-8xl" style={{ fontVariationSettings: "'FILL' 1" }}>savings</span>
              </div>
            </div>
          )}
        </section>

        {/* Results */}
        <section className="col-span-12 lg:col-span-8 xl:col-span-9 space-y-6">
          {error && <div className="p-4 bg-error-container rounded"><p className="text-sm text-on-error-container">{error}</p></div>}

          {!result && !loading && (
            <div className="bg-surface-container-lowest border border-slate-100 rounded-lg p-12 text-center">
              <span className="material-symbols-outlined text-5xl text-slate-200 mb-4">calculate</span>
              <h3 className="font-headline font-bold text-lg text-slate-400 mb-2">Configure & Calculate</h3>
              <p className="text-sm text-slate-400 max-w-md mx-auto">Set your utilization inputs on the left and click "Update Analysis" to see cost projections across plans.</p>
            </div>
          )}

          {/* Plan Cards */}
          {plans.length > 0 && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {plans.slice(0, 3).map((plan, idx) => {
                  const premPct = plan.annual_premium / plan.total_annual_cost * 100
                  const carePct = 100 - premPct
                  return (
                    <div key={plan.plan_id} className={`bg-surface-container-lowest p-5 rounded-lg shadow-sm ${idx === 0 ? 'border-2 border-primary relative' : 'border border-slate-100'}`}>
                      {idx === 0 && <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary text-white text-[9px] px-3 py-1 rounded-full uppercase tracking-widest font-bold">Recommended</div>}
                      <div className="flex justify-between items-start mb-4">
                        <div>
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-tighter ${idx === 0 ? 'bg-secondary-container text-on-secondary-container' : 'bg-surface-container-high text-slate-600'}`}>
                            {plan.plan_type}
                          </span>
                          <h4 className="font-headline font-bold text-primary mt-2">{plan.plan_name}</h4>
                        </div>
                        <span className="text-xl font-headline font-extrabold text-primary">${plan.total_annual_cost.toLocaleString()}</span>
                      </div>
                      <div className="space-y-2 mb-4">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-slate-500 uppercase tracking-widest font-medium">Premium</span>
                          <span className="font-bold">${plan.annual_premium.toLocaleString()}</span>
                        </div>
                        <div className="w-full h-2 bg-surface-container-high rounded-full overflow-hidden flex">
                          <div className="h-full bg-primary" style={{ width: `${premPct}%` }}></div>
                          <div className="h-full bg-secondary" style={{ width: `${carePct}%` }}></div>
                        </div>
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-slate-500 uppercase tracking-widest font-medium">Care Costs</span>
                          <span className="font-bold">${plan.annual_care_cost.toLocaleString()}</span>
                        </div>
                      </div>
                      <button onClick={() => setExpanded(expanded === plan.plan_id ? null : plan.plan_id)}
                        className="w-full py-2 border-t border-slate-100 text-[10px] font-bold text-primary uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-slate-50 transition-colors">
                        {expanded === plan.plan_id ? 'Hide' : 'View'} Line Items
                        <span className={`material-symbols-outlined text-sm transition-transform ${expanded === plan.plan_id ? 'rotate-180' : ''}`}>expand_more</span>
                      </button>
                      {expanded === plan.plan_id && (
                        <div className="pt-4 border-t border-slate-50 space-y-2 text-xs">
                          <div className="flex justify-between"><span className="text-slate-500">Doctor Visits</span><span className="font-bold">${plan.breakdown.doctor_visit_costs.toLocaleString()}</span></div>
                          <div className="flex justify-between"><span className="text-slate-500">Prescriptions</span><span className="font-bold">${plan.breakdown.prescription_costs.toLocaleString()}</span></div>
                          <div className="flex justify-between"><span className="text-slate-500">Procedures</span><span className="font-bold">${plan.breakdown.procedure_costs.toLocaleString()}</span></div>
                          {plan.breakdown.oop_cap_applied && <div className="flex justify-between text-secondary font-bold"><span>OOP Cap Applied</span><span>Saved ${(plan.breakdown.total_before_oop_cap - plan.breakdown.final_care_cost).toLocaleString()}</span></div>}
                          {plan.prescription_details?.map((rx, i) => (
                            <div key={i} className="flex justify-between text-slate-400"><span>{rx.name} ({Math.round(rx.annual_cost / rx.cost_per_fill)}x)</span><span>${rx.annual_cost.toLocaleString()}/yr</span></div>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* Ranking Table */}
              <div className="bg-surface-container-lowest rounded-lg border border-slate-100 overflow-hidden shadow-sm">
                <div className="p-6 border-b border-slate-100 flex justify-between items-center">
                  <h3 className="font-headline font-bold text-primary">Full Comparison Ranking</h3>
                </div>
                <table className="w-full text-left">
                  <thead className="bg-surface-container-low">
                    <tr>
                      <th className="px-6 py-4 uppercase tracking-widest text-[10px] font-bold text-slate-500">Plan</th>
                      <th className="px-6 py-4 uppercase tracking-widest text-[10px] font-bold text-slate-500">Annual Premium</th>
                      <th className="px-6 py-4 uppercase tracking-widest text-[10px] font-bold text-slate-500">Care Costs</th>
                      <th className="px-6 py-4 uppercase tracking-widest text-[10px] font-bold text-slate-500 text-right">Total OOP</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {plans.map((plan, idx) => (
                      <tr key={plan.plan_id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-6 py-5">
                          <div className="flex items-center gap-3">
                            <span className={`w-6 h-6 rounded ${idx === 0 ? 'bg-primary text-white' : 'bg-slate-200 text-slate-600'} text-[10px] flex items-center justify-center font-bold`}>{idx + 1}</span>
                            <span className="font-headline font-bold text-sm">{plan.plan_name}</span>
                          </div>
                        </td>
                        <td className="px-6 py-5 text-sm font-medium">${plan.annual_premium.toLocaleString()}</td>
                        <td className="px-6 py-5">
                          <div className="flex items-center gap-2">
                            <div className="flex-1 h-1.5 bg-surface-container-high rounded-full overflow-hidden">
                              <div className="h-full bg-secondary" style={{ width: `${(plan.annual_care_cost / (plans[plans.length - 1]?.total_annual_cost || 1)) * 100}%` }}></div>
                            </div>
                            <span className="text-xs font-bold text-secondary">${plan.annual_care_cost.toLocaleString()}</span>
                          </div>
                        </td>
                        <td className="px-6 py-5 text-right font-headline font-bold text-primary">${plan.total_annual_cost.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* AI Recommendation */}
              {result.recommendation && (
                <div className="relative overflow-hidden bg-primary-container text-white p-8 rounded-lg shadow-lg">
                  <div className="absolute top-0 right-0 p-4 opacity-10">
                    <span className="material-symbols-outlined text-[100px]" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
                  </div>
                  <div className="relative z-10 flex gap-6 items-start">
                    <div className="w-10 h-10 bg-on-primary-container rounded-full flex items-center justify-center text-primary-container shrink-0">
                      <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
                    </div>
                    <div>
                      <span className="text-[10px] uppercase tracking-widest text-on-primary-container font-extrabold mb-2 block">AI Cost Analysis</span>
                      <div className="text-slate-200 leading-relaxed whitespace-pre-wrap text-sm">{result.recommendation}</div>
                    </div>
                  </div>
                </div>
              )}

              {result.disclaimer && (
                <div className="p-4 bg-surface-container-low rounded border border-outline-variant/20">
                  <p className="text-[10px] text-on-surface-variant italic">{result.disclaimer}</p>
                </div>
              )}

              <div className="text-center">
                <button onClick={() => setResult(null)} className="text-primary font-bold text-sm hover:underline flex items-center gap-2 mx-auto">
                  <span className="material-symbols-outlined text-sm">refresh</span> New Calculation
                </button>
              </div>
            </>
          )}
        </section>
      </div>
    </>
  )
}
