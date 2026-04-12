import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'

export default function PlanComparisonPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState({ zip_code: '', age: '', income_level: 'medium', medications: [], procedures: [] })
  const [medInput, setMedInput] = useState('')
  const [procInput, setProcInput] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function addMed() { if (medInput.trim()) { setForm({ ...form, medications: [...form.medications, medInput.trim()] }); setMedInput('') } }
  function addProc() { if (procInput.trim()) { setForm({ ...form, procedures: [...form.procedures, procInput.trim()] }); setProcInput('') } }

  async function handleCompare() {
    if (!form.zip_code || !form.age) return
    setLoading(true); setError(''); setResult(null)
    try {
      const data = await api.post('/compare', {
        zip_code: form.zip_code,
        age: parseInt(form.age, 10),
        income_level: form.income_level,
        medications: form.medications,
        procedures: form.procedures,
      })
      setResult(data)
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  const plans = result?.plans || []
  const bestPlan = plans[0]

  return (
    <>
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-10">
        <div className="flex justify-between items-end mb-6">
          <div>
            <h1 className="font-display text-4xl text-primary font-bold mb-2">Plan Comparison Results</h1>
            <p className="text-on-surface-variant font-headline">Side-by-side Medicare Advantage plan analysis</p>
          </div>
        </div>

        {/* Input Section */}
        {!result && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-surface-container-lowest p-5 rounded border border-slate-100 shadow-sm">
              <span className="text-[10px] uppercase tracking-widest text-outline font-bold mb-2 block">Zip Code</span>
              <input className="w-full bg-surface-container-low border-0 border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-lg font-bold py-2 px-0"
                placeholder="e.g. 10001" value={form.zip_code} onChange={(e) => setForm({ ...form, zip_code: e.target.value })} maxLength={5} />
            </div>
            <div className="bg-surface-container-lowest p-5 rounded border border-slate-100 shadow-sm">
              <span className="text-[10px] uppercase tracking-widest text-outline font-bold mb-2 block">Age</span>
              <input type="number" className="w-full bg-surface-container-low border-0 border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-lg font-bold py-2 px-0"
                placeholder="e.g. 65" value={form.age} onChange={(e) => setForm({ ...form, age: e.target.value })} min={18} max={120} />
            </div>
            <div className="bg-surface-container-lowest p-5 rounded border border-slate-100 shadow-sm">
              <span className="text-[10px] uppercase tracking-widest text-outline font-bold mb-2 block">Income Level</span>
              <select className="w-full bg-surface-container-low border-0 border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-lg font-bold py-2 px-0"
                value={form.income_level} onChange={(e) => setForm({ ...form, income_level: e.target.value })}>
                <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option>
              </select>
            </div>
            <div className="bg-surface-container-lowest p-5 rounded border border-slate-100 shadow-sm md:col-span-1 flex flex-col justify-end">
              <button onClick={handleCompare} disabled={loading || !form.zip_code || !form.age}
                className="w-full bg-primary text-on-primary py-3 rounded font-bold text-sm shadow-md hover:bg-primary-container transition-all disabled:opacity-50 flex items-center justify-center gap-2">
                {loading ? <><span className="material-symbols-outlined text-sm animate-spin">progress_activity</span> Comparing...</>
                  : <><span className="material-symbols-outlined text-sm">compare_arrows</span> Compare Plans</>}
              </button>
            </div>
          </div>
        )}

        {/* Medications & Procedures Input */}
        {!result && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
            <div className="bg-surface-container-lowest p-5 rounded border border-slate-100 shadow-sm">
              <span className="text-[10px] uppercase tracking-widest text-outline font-bold mb-3 block">Medications</span>
              <div className="flex gap-2 mb-3">
                <input className="flex-1 bg-surface-container-low border-0 border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-sm py-2 px-0"
                  placeholder="e.g. Metformin" value={medInput} onChange={(e) => setMedInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addMed() } }} />
                <button onClick={addMed} className="px-4 py-2 bg-primary text-white rounded text-xs font-bold">Add</button>
              </div>
              <div className="flex flex-wrap gap-2">
                {form.medications.map((m, i) => (
                  <span key={i} className="bg-secondary-fixed text-on-secondary-fixed-variant px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
                    {m} <button onClick={() => setForm({ ...form, medications: form.medications.filter((_, j) => j !== i) })}><span className="material-symbols-outlined text-xs">close</span></button>
                  </span>
                ))}
              </div>
            </div>
            <div className="bg-surface-container-lowest p-5 rounded border border-slate-100 shadow-sm">
              <span className="text-[10px] uppercase tracking-widest text-outline font-bold mb-3 block">Procedures</span>
              <div className="flex gap-2 mb-3">
                <input className="flex-1 bg-surface-container-low border-0 border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-sm py-2 px-0"
                  placeholder="e.g. MRI" value={procInput} onChange={(e) => setProcInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addProc() } }} />
                <button onClick={addProc} className="px-4 py-2 bg-primary text-white rounded text-xs font-bold">Add</button>
              </div>
              <div className="flex flex-wrap gap-2">
                {form.procedures.map((p, i) => (
                  <span key={i} className="bg-tertiary-fixed text-on-tertiary-fixed px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
                    {p} <button onClick={() => setForm({ ...form, procedures: form.procedures.filter((_, j) => j !== i) })}><span className="material-symbols-outlined text-xs">close</span></button>
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {error && <div className="p-4 bg-error-container rounded mb-8"><p className="text-sm text-on-error-container">{error}</p></div>}

        {/* Input Summary (after results) */}
        {result && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-surface-container-lowest p-5 rounded border border-slate-100 shadow-sm">
              <span className="text-[10px] uppercase tracking-widest text-outline font-bold mb-2 block">Demographics</span>
              <p className="text-xl font-headline font-bold text-primary">Age {form.age}</p>
              <p className="text-sm text-on-surface-variant">Zip: {form.zip_code}</p>
            </div>
            <div className="bg-surface-container-lowest p-5 rounded border border-slate-100 shadow-sm">
              <span className="text-[10px] uppercase tracking-widest text-outline font-bold mb-2 block">Income</span>
              <p className="text-xl font-headline font-bold text-primary capitalize">{form.income_level}</p>
              <p className="text-sm text-on-surface-variant">{plans.length} plans compared</p>
            </div>
            <div className="bg-surface-container-lowest p-5 rounded border border-slate-100 shadow-sm md:col-span-2">
              <span className="text-[10px] uppercase tracking-widest text-outline font-bold mb-3 block">Medical Profile</span>
              <div className="flex flex-wrap gap-2">
                {form.medications.map((m, i) => (
                  <span key={i} className="bg-secondary-fixed text-on-secondary-fixed-variant px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider">{m}</span>
                ))}
                {form.procedures.map((p, i) => (
                  <span key={`p-${i}`} className="bg-tertiary-fixed text-on-tertiary-fixed px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider">{p}</span>
                ))}
                {form.medications.length === 0 && form.procedures.length === 0 && <span className="text-sm text-slate-400">None specified</span>}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* AI Recommendation */}
      {result?.recommendation && (
        <div className="max-w-7xl mx-auto mb-12">
          <div className="relative overflow-hidden bg-primary-container text-white p-8 rounded-lg shadow-lg border border-primary/20">
            <div className="absolute top-0 right-0 p-4 opacity-10">
              <span className="material-symbols-outlined text-[120px]" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
            </div>
            <div className="relative z-10 flex gap-8 items-start">
              <div className="shrink-0">
                <div className="w-12 h-12 bg-on-primary-container rounded-full flex items-center justify-center text-primary-container">
                  <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
                </div>
              </div>
              <div>
                <span className="text-[10px] uppercase tracking-widest text-on-primary-container font-extrabold mb-2 block">AI Clinical Guidance</span>
                <h2 className="font-display text-2xl mb-4">Recommendation</h2>
                <div className="text-slate-200 max-w-3xl leading-relaxed whitespace-pre-wrap">
                  {result.recommendation}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Plan Cards */}
      {plans.length > 0 && (
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {plans.map((plan, idx) => (
              <div key={plan.plan_id} className={`bg-surface-container-lowest rounded-lg shadow-sm hover:shadow-md transition-shadow ${idx === 0 ? 'border-2 border-primary ring-4 ring-primary/5 relative' : 'border border-slate-200'}`}>
                {idx === 0 && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-primary text-on-primary px-4 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest whitespace-nowrap">
                    Best Clinical Value
                  </div>
                )}
                <div className="p-6 border-b border-slate-100">
                  <p className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">{plan.plan_type}</p>
                  <h3 className="font-headline font-bold text-lg leading-tight mt-1">{plan.plan_name}</h3>
                  <p className="text-xs text-slate-400 mt-1">{plan.plan_id}</p>
                </div>
                <div className="divide-y divide-slate-50 text-center">
                  <div className="h-16 flex flex-col justify-center px-6">
                    <span className="text-[9px] text-outline font-bold uppercase mb-1">Monthly Premium</span>
                    <span className={`font-headline font-extrabold text-xl ${idx === 0 ? 'text-primary' : 'text-slate-700'}`}>${plan.monthly_premium.toFixed(2)}</span>
                  </div>
                  <div className="h-14 flex flex-col justify-center px-6">
                    <span className="text-[9px] text-outline font-bold uppercase mb-1">Deductible</span>
                    <span className="font-medium">${plan.annual_deductible.toFixed(2)}</span>
                  </div>
                  <div className="h-14 flex flex-col justify-center px-6">
                    <span className="text-[9px] text-outline font-bold uppercase mb-1">OOP Max</span>
                    <span className="font-medium">${plan.out_of_pocket_max.toFixed(2)}</span>
                  </div>
                  <div className="h-14 flex flex-col justify-center px-6">
                    <span className="text-[9px] text-outline font-bold uppercase mb-1">Star Rating</span>
                    <div className="flex justify-center text-yellow-500">
                      {Array.from({ length: 5 }, (_, i) => (
                        <span key={i} className="material-symbols-outlined text-sm" style={{ fontVariationSettings: `'FILL' ${i < Math.floor(plan.star_rating) ? 1 : 0}` }}>star</span>
                      ))}
                      <span className="text-xs text-slate-500 ml-1">{plan.star_rating}</span>
                    </div>
                  </div>
                  {plan.estimated_medication_costs && Object.keys(plan.estimated_medication_costs).length > 0 && (
                    <div className="px-6 py-3">
                      <span className="text-[9px] text-outline font-bold uppercase mb-2 block">Drug Costs</span>
                      {Object.entries(plan.estimated_medication_costs).map(([drug, cost]) => (
                        <div key={drug} className="flex justify-between text-xs mb-1">
                          <span className="text-slate-600">{drug}</span>
                          <span className="font-bold">${cost.toFixed(2)}/mo</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {plan.estimated_procedure_costs && Object.keys(plan.estimated_procedure_costs).length > 0 && (
                    <div className="px-6 py-3">
                      <span className="text-[9px] text-outline font-bold uppercase mb-2 block">Procedures</span>
                      {Object.entries(plan.estimated_procedure_costs).map(([proc, cost]) => (
                        <div key={proc} className="flex justify-between text-xs mb-1">
                          <span className="text-slate-600">{proc}</span>
                          <span className="font-bold">${cost.toFixed(2)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Disclaimer */}
      {result?.disclaimer && (
        <div className="max-w-7xl mx-auto mt-8 p-4 bg-surface-container-low rounded border border-outline-variant/20">
          <p className="text-[10px] text-on-surface-variant italic">{result.disclaimer}</p>
        </div>
      )}

      {/* Reset button */}
      {result && (
        <div className="max-w-7xl mx-auto mt-8 text-center">
          <button onClick={() => setResult(null)} className="text-primary font-bold text-sm hover:underline flex items-center gap-2 mx-auto">
            <span className="material-symbols-outlined text-sm">refresh</span> Run New Comparison
          </button>
        </div>
      )}
    </>
  )
}
