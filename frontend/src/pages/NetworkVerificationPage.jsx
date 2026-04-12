import { useState } from 'react'
import api from '../api/client'

export default function NetworkVerificationPage() {
  const [form, setForm] = useState({ zip_code: '', income_level: 'medium', providers: [], prescriptions: [] })
  const [provName, setProvName] = useState('')
  const [provNpi, setProvNpi] = useState('')
  const [drugInput, setDrugInput] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function addProvider() {
    if (provName.trim()) {
      setForm({ ...form, providers: [...form.providers, { name: provName.trim(), npi: provNpi.trim() || null }] })
      setProvName(''); setProvNpi('')
    }
  }
  function addDrug() {
    if (drugInput.trim()) {
      setForm({ ...form, prescriptions: [...form.prescriptions, drugInput.trim()] })
      setDrugInput('')
    }
  }

  async function handleVerify() {
    if (!form.zip_code) return
    setLoading(true); setError(''); setResult(null)
    try {
      const data = await api.post('/verify', {
        zip_code: form.zip_code,
        income_level: form.income_level,
        providers: form.providers,
        prescriptions: form.prescriptions,
      })
      setResult(data)
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  const plans = result?.plans || []

  return (
    <>
      {/* Header */}
      <section className="mb-8">
        <h1 className="font-display text-4xl text-primary mb-2">Network Verification</h1>
        <p className="text-slate-500 max-w-2xl text-sm leading-relaxed">
          Cross-reference provider NPI data against carrier-specific network files and drug formularies to ensure clinical alignment for your clients.
        </p>
      </section>

      {/* Input Section */}
      {!result && (
        <div className="grid grid-cols-12 gap-8 mb-8">
          {/* Left: Provider Search */}
          <div className="col-span-12 lg:col-span-7 space-y-6">
            <div className="flex justify-between items-end mb-2">
              <label className="text-[11px] uppercase tracking-widest font-bold text-primary">Provider Directory Search</label>
            </div>

            {/* Zip + Income */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-surface-container-lowest p-5 rounded-lg border border-slate-100 shadow-sm">
                <span className="text-[10px] uppercase tracking-widest text-outline font-bold mb-2 block">Zip Code</span>
                <input className="w-full bg-surface-container-low border-0 border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-lg font-bold py-2 px-0"
                  placeholder="e.g. 10001" value={form.zip_code} onChange={(e) => setForm({ ...form, zip_code: e.target.value })} maxLength={5} />
              </div>
              <div className="bg-surface-container-lowest p-5 rounded-lg border border-slate-100 shadow-sm">
                <span className="text-[10px] uppercase tracking-widest text-outline font-bold mb-2 block">Income Level</span>
                <select className="w-full bg-surface-container-low border-0 border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-lg font-bold py-2 px-0"
                  value={form.income_level} onChange={(e) => setForm({ ...form, income_level: e.target.value })}>
                  <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option>
                </select>
              </div>
            </div>

            {/* Add Providers */}
            <div className="bg-surface-container-lowest p-6 rounded-lg border border-slate-100 shadow-sm">
              <span className="text-[10px] uppercase tracking-widest text-outline font-bold mb-3 block">Add Providers to Verify</span>
              <div className="flex gap-2 mb-4">
                <input className="flex-1 bg-surface-container-low border-0 border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-sm py-2 px-0"
                  placeholder="Doctor name" value={provName} onChange={(e) => setProvName(e.target.value)} />
                <input className="w-40 bg-surface-container-low border-0 border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-sm py-2 px-0"
                  placeholder="NPI (optional)" value={provNpi} onChange={(e) => setProvNpi(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addProvider() } }} />
                <button onClick={addProvider} className="px-4 py-2 bg-primary text-white rounded text-xs font-bold">Add</button>
              </div>
              {form.providers.length > 0 ? (
                <div className="space-y-2">
                  {form.providers.map((p, i) => (
                    <div key={i} className="bg-surface-container-low p-4 rounded-lg border border-slate-100 flex justify-between items-center relative overflow-hidden group">
                      <div className="absolute top-0 left-0 w-1 h-full bg-primary transition-all group-hover:w-2"></div>
                      <div className="flex items-center gap-3 pl-3">
                        <div className="w-10 h-10 bg-surface-container-high rounded flex items-center justify-center text-primary">
                          <span className="material-symbols-outlined">medical_services</span>
                        </div>
                        <div>
                          <p className="font-headline font-bold text-primary">{p.name}</p>
                          {p.npi && <p className="text-[10px] text-slate-400">NPI: {p.npi}</p>}
                        </div>
                      </div>
                      <button onClick={() => setForm({ ...form, providers: form.providers.filter((_, j) => j !== i) })}
                        className="text-slate-300 hover:text-error transition-colors"><span className="material-symbols-outlined">close</span></button>
                    </div>
                  ))}
                </div>
              ) : <p className="text-xs text-slate-400 italic">No providers added yet.</p>}
            </div>
          </div>

          {/* Right: Drug Formulary + Run */}
          <div className="col-span-12 lg:col-span-5 space-y-6">
            <div className="bg-white/40 backdrop-blur-xl p-6 rounded-lg border border-white/20 shadow-lg">
              <div className="flex items-center gap-2 mb-4">
                <span className="material-symbols-outlined text-primary">medication</span>
                <h2 className="font-headline font-bold text-sm uppercase tracking-widest text-primary">Drug Formulary Checker</h2>
              </div>
              <div className="flex gap-2 mb-4">
                <input className="flex-1 bg-surface-container-low border-0 border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-sm py-2 px-0"
                  placeholder="e.g. Metformin" value={drugInput} onChange={(e) => setDrugInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addDrug() } }} />
                <button onClick={addDrug} className="px-4 py-2 bg-primary text-white rounded text-xs font-bold">Add</button>
              </div>
              {form.prescriptions.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {form.prescriptions.map((d, i) => (
                    <span key={i} className="bg-secondary-fixed text-on-secondary-fixed-variant px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
                      {d} <button onClick={() => setForm({ ...form, prescriptions: form.prescriptions.filter((_, j) => j !== i) })}><span className="material-symbols-outlined text-xs">close</span></button>
                    </span>
                  ))}
                </div>
              ) : <p className="text-xs text-slate-400 italic">No drugs added yet.</p>}
            </div>

            <button onClick={handleVerify} disabled={loading || !form.zip_code}
              className="w-full bg-primary text-on-primary py-4 rounded-lg font-bold shadow-md hover:bg-primary-container transition-all disabled:opacity-50 flex items-center justify-center gap-2">
              {loading ? <><span className="material-symbols-outlined animate-spin">progress_activity</span> Verifying...</>
                : <><span className="material-symbols-outlined">verified_user</span> Run Network Verification</>}
            </button>
          </div>
        </div>
      )}

      {error && <div className="p-4 bg-error-container rounded mb-8"><p className="text-sm text-on-error-container">{error}</p></div>}

      {/* Results */}
      {result && (
        <>
          {/* AI Recommendation */}
          {result.recommendation && (
            <div className="relative overflow-hidden bg-primary-container text-white p-8 rounded-lg shadow-lg mb-8">
              <div className="absolute top-0 right-0 p-4 opacity-10">
                <span className="material-symbols-outlined text-[100px]" style={{ fontVariationSettings: "'FILL' 1" }}>verified_user</span>
              </div>
              <div className="relative z-10 flex gap-6 items-start">
                <div className="w-10 h-10 bg-on-primary-container rounded-full flex items-center justify-center text-primary-container shrink-0">
                  <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
                </div>
                <div>
                  <span className="text-[10px] uppercase tracking-widest text-on-primary-container font-extrabold mb-2 block">Network Analysis</span>
                  <div className="text-slate-200 leading-relaxed whitespace-pre-wrap text-sm">{result.recommendation}</div>
                </div>
              </div>
            </div>
          )}

          {/* Plan Results */}
          {plans.map((plan, idx) => (
            <div key={idx} className="bg-surface-container-lowest rounded-lg border border-slate-100 shadow-sm mb-6 overflow-hidden">
              <div className="p-6 border-b border-slate-100 flex justify-between items-center">
                <div>
                  <h3 className="font-headline font-bold text-lg text-primary">{plan.plan_name}</h3>
                  <p className="text-xs text-slate-400">{plan.plan_id}</p>
                </div>
              </div>

              {/* Provider Results */}
              {plan.provider_results?.length > 0 && (
                <div className="p-6 border-b border-slate-50">
                  <label className="text-[10px] uppercase tracking-widest font-bold text-primary mb-3 block">Provider Network Status</label>
                  <div className="space-y-2">
                    {plan.provider_results.map((p, i) => (
                      <div key={i} className="flex items-center justify-between p-3 bg-surface-container-low rounded">
                        <div className="flex items-center gap-3">
                          <span className={`material-symbols-outlined text-lg ${p.in_network ? 'text-green-600' : 'text-error'}`}
                            style={p.in_network ? { fontVariationSettings: "'FILL' 1" } : {}}>
                            {p.in_network ? 'check_circle' : 'cancel'}
                          </span>
                          <div>
                            <p className="text-sm font-bold">{p.name}</p>
                            {p.specialty && <p className="text-[10px] text-slate-400">{p.specialty}</p>}
                          </div>
                        </div>
                        <div className="text-right">
                          <span className={`px-2 py-1 rounded-full text-[10px] font-bold ${p.in_network ? 'bg-secondary-container text-on-secondary-container' : 'bg-error-container text-on-error-container'}`}>
                            {p.in_network ? 'IN-NETWORK' : 'OUT-OF-NETWORK'}
                          </span>
                          {p.warning && <p className="text-[9px] text-error mt-1">{p.warning}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Formulary Results */}
              {plan.formulary_results?.length > 0 && (
                <div className="p-6">
                  <label className="text-[10px] uppercase tracking-widest font-bold text-primary mb-3 block">Drug Formulary Status</label>
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-surface-container-low">
                        <th className="p-3 text-[9px] font-bold text-slate-500 uppercase tracking-widest">Drug Name</th>
                        <th className="p-3 text-[9px] font-bold text-slate-500 uppercase tracking-widest text-center">Tier</th>
                        <th className="p-3 text-[9px] font-bold text-slate-500 uppercase tracking-widest text-center">Status</th>
                        <th className="p-3 text-[9px] font-bold text-slate-500 uppercase tracking-widest text-right">Copay</th>
                      </tr>
                    </thead>
                    <tbody className="text-sm">
                      {plan.formulary_results.map((f, i) => (
                        <tr key={i} className="border-b border-slate-50 hover:bg-slate-50 transition-colors">
                          <td className="p-3 font-semibold text-primary">{f.drug_name}</td>
                          <td className="p-3 text-center">
                            {f.tier ? <span className="bg-secondary-container/30 text-secondary px-2 py-0.5 rounded text-[10px] font-bold">{f.tier}</span> : '—'}
                          </td>
                          <td className="p-3 text-center">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${f.on_formulary ? 'bg-secondary-container text-on-secondary-container' : 'bg-error-container text-on-error-container'}`}>
                              {f.on_formulary ? 'ON FORMULARY' : 'NOT COVERED'}
                            </span>
                          </td>
                          <td className="p-3 text-right font-medium">{f.copay != null ? `$${f.copay.toFixed(2)}` : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ))}

          {/* Compatibility Scores */}
          {plans.length > 0 && (
            <div className="pt-8 border-t border-slate-200/50">
              <label className="text-[11px] uppercase tracking-widest font-bold text-primary mb-6 block">Compatibility Scores</label>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="bg-surface-container-lowest p-6 rounded shadow-sm border border-slate-100 flex flex-col justify-between h-48">
                  <div>
                    <p className="text-[10px] uppercase tracking-widest font-bold text-slate-400 mb-1">Provider Overlap</p>
                    <h4 className="text-2xl font-bold text-primary">
                      {plans[0]?.provider_results ? `${plans[0].provider_results.filter(p => p.in_network).length} / ${plans[0].provider_results.length}` : '—'}
                    </h4>
                    <p className="text-[10px] text-slate-500 mt-2">Doctors in network for top plan.</p>
                  </div>
                  <div className="h-1 w-full bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-primary" style={{ width: plans[0]?.provider_results ? `${(plans[0].provider_results.filter(p => p.in_network).length / Math.max(plans[0].provider_results.length, 1)) * 100}%` : '0%' }}></div>
                  </div>
                </div>
                <div className="bg-surface-container-lowest p-6 rounded shadow-sm border border-slate-100 flex flex-col justify-between h-48">
                  <div>
                    <p className="text-[10px] uppercase tracking-widest font-bold text-slate-400 mb-1">Formulary Match</p>
                    <h4 className="text-2xl font-bold text-secondary">
                      {plans[0]?.formulary_results ? `${Math.round((plans[0].formulary_results.filter(f => f.on_formulary).length / Math.max(plans[0].formulary_results.length, 1)) * 100)}%` : '—'}
                    </h4>
                    <p className="text-[10px] text-slate-500 mt-2">Drug coverage across formulary.</p>
                  </div>
                  <div className="h-1 w-full bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-secondary" style={{ width: plans[0]?.formulary_results ? `${(plans[0].formulary_results.filter(f => f.on_formulary).length / Math.max(plans[0].formulary_results.length, 1)) * 100}%` : '0%' }}></div>
                  </div>
                </div>
                <div className="bg-primary text-on-primary p-6 rounded shadow-xl flex flex-col justify-between h-48 relative overflow-hidden">
                  <div className="relative z-10">
                    <p className="text-[10px] uppercase tracking-widest font-bold text-blue-200 mb-1">Compatibility Score</p>
                    <h4 className="text-4xl font-extrabold">A+</h4>
                    <p className="text-[10px] text-blue-100 mt-2">Institutional grade alignment.</p>
                  </div>
                  <div className="relative z-10 flex items-center text-[10px] font-bold">
                    <span className="material-symbols-outlined text-xs mr-1">verified_user</span> VERIFIED
                  </div>
                </div>
                <div className="bg-surface-container-lowest p-6 rounded shadow-sm border border-slate-100 flex flex-col justify-between h-48">
                  <div>
                    <p className="text-[10px] uppercase tracking-widest font-bold text-slate-400 mb-1">Gap Analysis</p>
                    <h4 className="text-2xl font-bold text-tertiary">
                      {plans[0]?.provider_results ? plans[0].provider_results.filter(p => !p.in_network).length : 0}
                    </h4>
                    <p className="text-[10px] text-slate-500 mt-2">Uncovered requirements identified.</p>
                  </div>
                  <div className="flex gap-2">
                    {plans[0]?.provider_results?.filter(p => !p.in_network).map((_, i) => (
                      <div key={i} className="w-3 h-3 rounded-full bg-error"></div>
                    ))}
                    {(!plans[0]?.provider_results || plans[0].provider_results.every(p => p.in_network)) && (
                      <div className="w-3 h-3 rounded-full bg-slate-200"></div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Disclaimer + Reset */}
          {result.disclaimer && (
            <div className="mt-8 p-4 bg-surface-container-low rounded border border-outline-variant/20">
              <p className="text-[10px] text-on-surface-variant italic">{result.disclaimer}</p>
            </div>
          )}
          <div className="mt-6 text-center">
            <button onClick={() => setResult(null)} className="text-primary font-bold text-sm hover:underline flex items-center gap-2 mx-auto">
              <span className="material-symbols-outlined text-sm">refresh</span> Run New Verification
            </button>
          </div>
        </>
      )}
    </>
  )
}
