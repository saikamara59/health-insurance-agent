import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../api/client'

const TABS = ['Plan Analysis', 'Profile Details', 'Prescriptions', 'Preferred Doctors']

const WORKFLOW_STEPS = [
  { number: 1, title: 'Extract & Translate', desc: 'PDF parsing and coverage translation from policy documents.', icon: 'description', endpoint: '/translate', color: 'bg-primary',
    buildPayload: (c) => ({ document_text: `Summary of Benefits for ${c.full_name}, age ${c.age}, zip ${c.zip_code}, income ${c.income_level}. Prescriptions: ${(c.prescriptions||[]).join(', ')||'none'}. Procedures: ${(c.procedures||[]).join(', ')||'none'}.`, question: 'What does this plan cover?' }) },
  { number: 2, title: 'Verify Networks', desc: 'Real-time validation of provider networks and formulary coverage.', icon: 'verified_user', endpoint: '/verify', color: 'bg-primary',
    buildPayload: (c) => ({ providers: (c.doctors||[]).map(d => ({ name: d.name, npi: d.npi })), prescriptions: c.prescriptions||[], zip_code: c.zip_code, income_level: c.income_level }) },
  { number: 3, title: 'Calculate Costs', desc: 'Estimate annual out-of-pocket based on healthcare usage patterns.', icon: 'calculate', endpoint: '/calculate', color: 'bg-primary',
    buildPayload: (c) => ({ zip_code: c.zip_code, income_level: c.income_level, usage: { doctor_visits_per_year: 12, prescriptions: (c.prescriptions||[]).map(rx => ({ name: rx, fills_per_year: 12 })), procedures: (c.procedures||[]).map(p => ({ name: p, count: 1 })) } }) },
  { number: 4, title: 'Compare Plans', desc: 'Search marketplace and rank plans by total cost and coverage.', icon: 'compare_arrows', endpoint: '/compare', color: 'bg-primary',
    buildPayload: (c) => ({ zip_code: c.zip_code, age: c.age, income_level: c.income_level, medications: c.prescriptions||[], procedures: c.procedures||[] }) },
  { number: 5, title: 'Generate Appeal', desc: 'Draft formal appeal letters for any denied claims.', icon: 'gavel', endpoint: '/appeal', color: 'bg-primary',
    buildPayload: (c) => ({ denial_text: `Claim denied for ${c.full_name}, Member zip ${c.zip_code}. Prescriptions: ${(c.prescriptions||[]).join(', ')}`, additional_context: `Patient age ${c.age}, income level ${c.income_level}` }) },
]

function getInitials(name) { return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2) }

export default function ClientProfilePage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [client, setClient] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState(0)
  const [stepStatuses, setStepStatuses] = useState({})
  const [stepResults, setStepResults] = useState({})
  const [stepLoading, setStepLoading] = useState({})
  const [editForm, setEditForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')
  const [rxInput, setRxInput] = useState('')
  const [docName, setDocName] = useState('')
  const [docNpi, setDocNpi] = useState('')

  useEffect(() => { loadClient() }, [id])

  async function loadClient() {
    setLoading(true)
    try {
      const data = await api.get(`/clients/${id}`)
      setClient(data)
      setEditForm({ full_name: data.full_name, zip_code: data.zip_code, age: data.age, income_level: data.income_level })
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  async function runStep(i) {
    setStepLoading(p => ({ ...p, [i]: true }))
    try {
      const result = await api.post(WORKFLOW_STEPS[i].endpoint, WORKFLOW_STEPS[i].buildPayload(client))
      setStepResults(p => ({ ...p, [i]: result }))
      setStepStatuses(p => ({ ...p, [i]: 'complete' }))
      // Log to action history
      try {
        await api.post('/history', {
          client_id: client.id,
          action_type: WORKFLOW_STEPS[i].title.toLowerCase().replace(/\s+/g, '_'),
          request_data: { endpoint: WORKFLOW_STEPS[i].endpoint },
          response_summary: { status: 'complete', has_recommendation: !!result?.recommendation },
        })
      } catch (_) { /* non-critical */ }
    } catch (err) {
      setStepResults(p => ({ ...p, [i]: { error: err.message } }))
      setStepStatuses(p => ({ ...p, [i]: 'error' }))
    } finally { setStepLoading(p => ({ ...p, [i]: false })) }
  }

  async function handleSave(e) {
    e.preventDefault(); setSaving(true); setSaveMsg('')
    try {
      const res = await api.put(`/clients/${id}`, { full_name: editForm.full_name, zip_code: editForm.zip_code, age: parseInt(editForm.age, 10), income_level: editForm.income_level })
      setClient(res); setSaveMsg('Saved')
    } catch (err) { setSaveMsg(`Error: ${err.message}`) }
    finally { setSaving(false) }
  }

  async function addRx() {
    if (!rxInput.trim()) return
    try { const res = await api.put(`/clients/${id}`, { prescriptions: [...(client.prescriptions||[]), rxInput.trim()] }); setClient(res); setRxInput('') } catch (err) { alert(err.message) }
  }
  async function removeRx(i) {
    try { const res = await api.put(`/clients/${id}`, { prescriptions: client.prescriptions.filter((_, j) => j !== i) }); setClient(res) } catch (err) { alert(err.message) }
  }
  async function addDoc() {
    if (!docName.trim()) return
    try { const res = await api.put(`/clients/${id}`, { doctors: [...(client.doctors||[]), { name: docName.trim(), npi: docNpi.trim() || null }] }); setClient(res); setDocName(''); setDocNpi('') } catch (err) { alert(err.message) }
  }
  async function removeDoc(i) {
    try { const res = await api.put(`/clients/${id}`, { doctors: client.doctors.filter((_, j) => j !== i) }); setClient(res) } catch (err) { alert(err.message) }
  }

  if (loading) return <div className="flex items-center justify-center min-h-[400px]"><span className="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span></div>
  if (error || !client) return <div className="flex flex-col items-center justify-center min-h-[400px]"><span className="material-symbols-outlined text-4xl text-error mb-4">error</span><p className="text-error text-sm">{error || 'Client not found'}</p><button className="mt-4 text-sm text-primary font-medium hover:underline" onClick={() => navigate('/clients')}>Back to Portfolio</button></div>

  const completedSteps = Object.values(stepStatuses).filter(s => s === 'complete').length

  return (
    <>
      {/* Client Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
        <div className="flex items-start gap-5">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary to-primary-container flex items-center justify-center shadow-lg shadow-primary/20">
            <span className="text-white text-2xl font-bold">{getInitials(client.full_name)}</span>
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-headline font-extrabold text-blue-950 tracking-tight">{client.full_name}</h1>
              <span className="px-3 py-1 rounded-full bg-secondary-fixed text-on-secondary-container text-[10px] font-bold uppercase tracking-widest">Active Client</span>
            </div>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-on-surface-variant text-sm mt-2">
              <span className="flex items-center gap-1.5"><span className="material-symbols-outlined text-base">cake</span> {client.age} years old</span>
              <span className="flex items-center gap-1.5"><span className="material-symbols-outlined text-base">payments</span> {client.income_level.charAt(0).toUpperCase() + client.income_level.slice(1)} income</span>
              <span className="flex items-center gap-1.5"><span className="material-symbols-outlined text-base">location_on</span> {client.zip_code}</span>
              {client.prescriptions?.length > 0 && <span className="flex items-center gap-1.5"><span className="material-symbols-outlined text-base">medication</span> {client.prescriptions.length} Rx</span>}
              {client.doctors?.length > 0 && <span className="flex items-center gap-1.5"><span className="material-symbols-outlined text-base">stethoscope</span> {client.doctors.length} providers</span>}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => setActiveTab(1)} className="px-5 py-2.5 rounded-lg font-semibold text-sm bg-surface-container-highest text-primary border border-outline-variant/10 hover:bg-surface-container-high transition-colors flex items-center gap-2">
            <span className="material-symbols-outlined text-lg">edit</span> Edit Profile
          </button>
          <button onClick={() => { setActiveTab(0); runStep(4) }} className="px-6 py-2.5 rounded-lg font-bold text-sm bg-gradient-to-r from-primary to-primary-container text-white shadow-lg shadow-primary/20 hover:shadow-primary/30 transition-all flex items-center gap-2">
            <span className="material-symbols-outlined text-lg">gavel</span> Generate Appeal
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-outline-variant/20 mb-8">
        {TABS.map((tab, i) => (
          <button key={tab} onClick={() => setActiveTab(i)}
            className={`px-6 py-4 text-sm font-medium transition-colors ${activeTab === i ? 'text-primary font-bold border-b-2 border-primary' : 'text-on-surface-variant hover:text-on-surface'}`}>
            {tab}
          </button>
        ))}
      </div>

      {/* Plan Analysis */}
      {activeTab === 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Workflow */}
          <div className="lg:col-span-4">
            <div className="bg-surface-container-low rounded-2xl p-6">
              <h3 className="font-headline font-bold text-lg mb-6">Analysis Workflow</h3>
              <div className="space-y-0">
                {WORKFLOW_STEPS.map((step, i) => {
                  const status = stepStatuses[i]
                  const isRunning = stepLoading[i]
                  const isLast = i === WORKFLOW_STEPS.length - 1
                  return (
                    <div key={i} className={`relative ${!isLast ? 'pb-8' : ''} flex gap-4`}>
                      {!isLast && <div className={`absolute left-[11px] top-6 bottom-0 w-0.5 ${status === 'complete' ? 'bg-primary/40' : 'bg-surface-container-highest'}`}></div>}
                      <div className={`relative z-10 w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0 ${
                        status === 'complete' ? 'bg-secondary text-white' :
                        status === 'error' ? 'bg-error text-white' :
                        isRunning ? 'bg-primary text-white ring-4 ring-primary/10' :
                        'bg-surface-container-highest text-on-surface-variant'
                      }`}>
                        {status === 'complete' ? <span className="material-symbols-outlined text-xs" style={{ fontVariationSettings: "'FILL' 1" }}>check</span> : step.number}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-1">
                          <h4 className="text-sm font-bold">{step.title}</h4>
                          {status === 'complete' && <span className="text-[10px] font-bold text-secondary uppercase">Complete</span>}
                          {status === 'error' && <span className="text-[10px] font-bold text-error uppercase">Error</span>}
                          {isRunning && <span className="px-2 py-0.5 rounded-md bg-primary/10 text-primary text-[10px] font-bold uppercase">Running</span>}
                        </div>
                        <p className="text-xs text-on-surface-variant leading-relaxed">{step.desc}</p>
                        <button onClick={() => runStep(i)} disabled={isRunning}
                          className="mt-3 text-[11px] font-bold text-primary flex items-center gap-1 hover:underline disabled:opacity-50">
                          {isRunning ? <>ANALYZING <span className="material-symbols-outlined text-sm animate-spin">progress_activity</span></> :
                           status === 'complete' ? <>RE-RUN <span className="material-symbols-outlined text-sm">refresh</span></> :
                           <>RUN ANALYSIS <span className="material-symbols-outlined text-sm">play_arrow</span></>}
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
            {/* Risk Score */}
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-outline-variant/10 mt-6">
              <div className="flex items-center gap-3 mb-4">
                <span className="material-symbols-outlined text-primary">analytics</span>
                <h4 className="text-sm font-bold">Analysis Progress</h4>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-3xl font-headline font-extrabold text-on-surface">{completedSteps}<span className="text-sm text-on-surface-variant font-normal">/{WORKFLOW_STEPS.length}</span></span>
                <span className={`px-2 py-1 text-[10px] font-bold rounded ${completedSteps === WORKFLOW_STEPS.length ? 'bg-secondary-fixed text-on-secondary-container' : completedSteps > 0 ? 'bg-primary-fixed text-primary' : 'bg-surface-container-highest text-on-surface-variant'}`}>
                  {completedSteps === WORKFLOW_STEPS.length ? 'ALL COMPLETE' : completedSteps > 0 ? 'IN PROGRESS' : 'NOT STARTED'}
                </span>
              </div>
              <div className="mt-3 w-full bg-surface-container-highest h-1.5 rounded-full overflow-hidden">
                <div className="bg-primary h-full transition-all" style={{ width: `${(completedSteps / WORKFLOW_STEPS.length) * 100}%` }}></div>
              </div>
            </div>
          </div>

          {/* Results */}
          <div className="lg:col-span-8 space-y-6">
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-surface-container-lowest p-6 rounded-2xl shadow-sm border border-outline-variant/5">
                <div className="flex justify-between items-start mb-4">
                  <div className="p-2 bg-primary/10 rounded-lg"><span className="material-symbols-outlined text-primary">account_balance_wallet</span></div>
                  <span className="text-[10px] font-bold text-primary px-2 py-1 bg-primary/5 rounded uppercase">Estimated</span>
                </div>
                <h5 className="text-sm font-bold text-on-surface-variant mb-1">Annual Out-of-Pocket</h5>
                <p className="text-2xl font-headline font-extrabold">{stepResults[2]?.plans?.[0]?.total_annual_cost ? `$${Number(stepResults[2].plans[0].total_annual_cost).toLocaleString()}` : '—'}</p>
                <p className="mt-2 text-xs text-on-surface-variant">{stepResults[2] ? 'Based on cost analysis' : 'Run cost calculation to estimate'}</p>
              </div>
              <div className="bg-surface-container-lowest p-6 rounded-2xl shadow-sm border border-outline-variant/5">
                <div className="flex justify-between items-start mb-4">
                  <div className="p-2 bg-secondary/10 rounded-lg"><span className="material-symbols-outlined text-secondary">verified_user</span></div>
                  <span className="text-[10px] font-bold text-secondary px-2 py-1 bg-secondary/5 rounded uppercase">Network</span>
                </div>
                <h5 className="text-sm font-bold text-on-surface-variant mb-1">Provider Coverage</h5>
                <p className="text-2xl font-headline font-extrabold">{stepResults[1]?.plans?.[0]?.provider_results ? `${stepResults[1].plans[0].provider_results.filter(p => p.in_network).length}/${stepResults[1].plans[0].provider_results.length}` : '—'}</p>
                <p className="mt-2 text-xs text-on-surface-variant">{stepResults[1] ? 'In-network providers' : 'Run network verification'}</p>
              </div>
            </div>

            {/* Results Panel */}
            {Object.keys(stepResults).length > 0 ? (
              <div className="bg-white rounded-3xl overflow-hidden shadow-md border border-outline-variant/5">
                <div className="p-8 border-b border-surface-container">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-headline font-extrabold text-xl mb-1">Analysis Results</h3>
                      <p className="text-sm text-on-surface-variant">{completedSteps} of {WORKFLOW_STEPS.length} analyses completed.</p>
                    </div>
                    <span className="material-symbols-outlined text-on-surface-variant opacity-40 text-4xl">database</span>
                  </div>
                </div>
                <div className="p-8 space-y-6 max-h-[600px] overflow-y-auto">
                  {Object.entries(stepResults).map(([idx, result]) => (
                    <div key={idx} className="border-b border-surface-container/50 pb-6 last:border-0 last:pb-0">
                      <div className="flex items-center gap-2 mb-3">
                        <span className={`w-2 h-2 rounded-full ${result.error ? 'bg-error' : 'bg-secondary'}`}></span>
                        <h4 className="text-sm font-bold text-blue-950">{WORKFLOW_STEPS[idx].title}</h4>
                      </div>
                      {result.error ? (
                        <p className="text-sm text-error">{result.error}</p>
                      ) : result.recommendation ? (
                        <p className="text-sm text-on-surface-variant leading-relaxed">{typeof result.recommendation === 'string' ? result.recommendation.slice(0, 500) : JSON.stringify(result.recommendation).slice(0, 500)}...</p>
                      ) : result.answer ? (
                        <p className="text-sm text-on-surface-variant leading-relaxed">{result.answer.slice(0, 500)}</p>
                      ) : result.appeal_letter ? (
                        <pre className="text-xs text-on-surface-variant whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto bg-surface-container-low p-4 rounded-lg">{result.appeal_letter.slice(0, 800)}</pre>
                      ) : (
                        <pre className="text-xs text-on-surface-variant whitespace-pre-wrap max-h-32 overflow-y-auto">{JSON.stringify(result, null, 2).slice(0, 500)}</pre>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="bg-surface-container-low/50 rounded-2xl p-12 border-2 border-dashed border-outline-variant/30 flex flex-col items-center text-center">
                <span className="material-symbols-outlined text-4xl text-outline-variant mb-4">science</span>
                <h4 className="font-headline font-bold text-lg mb-2 text-on-surface-variant">No Analysis Results Yet</h4>
                <p className="text-sm text-on-surface-variant max-w-sm mb-6">Run the analysis workflow steps on the left to generate insights for {client.full_name}.</p>
                <button onClick={() => runStep(0)} className="bg-primary/10 text-primary px-6 py-2 rounded-xl font-bold text-xs uppercase tracking-widest hover:bg-primary/20 transition-all">
                  Start Analysis
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Profile Details */}
      {activeTab === 1 && editForm && (
        <div className="max-w-2xl">
          <div className="bg-white rounded-2xl p-8 shadow-sm border border-outline-variant/10">
            <h2 className="font-headline text-xl font-bold text-blue-950 mb-8">Profile Details</h2>
            {saveMsg && <div className={`mb-6 p-4 rounded-xl text-sm ${saveMsg.startsWith('Error') ? 'bg-error-container text-on-error-container' : 'bg-secondary-fixed/30 text-on-secondary-container'}`}>{saveMsg}</div>}
            <form className="space-y-6" onSubmit={handleSave}>
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">Full Name</label>
                <input className="w-full bg-surface-container-low border-0 border-b-2 border-transparent focus:border-primary px-4 py-3 rounded-t-lg focus:outline-none focus:ring-0 transition-all text-lg font-medium" value={editForm.full_name} onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })} required />
              </div>
              <div className="grid grid-cols-3 gap-6">
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">Zip Code</label>
                  <input className="w-full bg-surface-container-low border-0 border-b-2 border-transparent focus:border-primary px-4 py-3 rounded-t-lg focus:outline-none focus:ring-0 transition-all text-lg font-medium" value={editForm.zip_code} onChange={(e) => setEditForm({ ...editForm, zip_code: e.target.value })} required maxLength={5} />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">Age</label>
                  <input type="number" className="w-full bg-surface-container-low border-0 border-b-2 border-transparent focus:border-primary px-4 py-3 rounded-t-lg focus:outline-none focus:ring-0 transition-all text-lg font-medium" value={editForm.age} onChange={(e) => setEditForm({ ...editForm, age: e.target.value })} required min={18} max={120} />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">Income</label>
                  <select className="w-full bg-surface-container-low border-0 border-b-2 border-transparent focus:border-primary px-4 py-3 rounded-t-lg focus:outline-none focus:ring-0 transition-all text-lg font-medium" value={editForm.income_level} onChange={(e) => setEditForm({ ...editForm, income_level: e.target.value })}>
                    <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option>
                  </select>
                </div>
              </div>
              <button type="submit" disabled={saving} className="bg-primary hover:bg-primary-container text-white px-8 py-3 rounded-lg font-bold shadow-lg shadow-primary/10 transition-all disabled:opacity-50 flex items-center gap-2">
                <span className="material-symbols-outlined text-lg">save</span> {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Prescriptions */}
      {activeTab === 2 && (
        <div className="max-w-2xl">
          <div className="bg-white rounded-2xl p-8 shadow-sm border border-outline-variant/10">
            <h2 className="font-headline text-xl font-bold text-blue-950 mb-6">Prescriptions</h2>
            <div className="flex gap-2 mb-6">
              <input type="text" placeholder="e.g. Metformin, Lisinopril..." value={rxInput}
                className="flex-1 px-4 py-3 bg-surface-container-low rounded-lg border-0 border-b-2 border-transparent text-sm focus:ring-0 focus:border-primary"
                onChange={(e) => setRxInput(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addRx() } }} />
              <button onClick={addRx} className="px-6 py-3 bg-primary text-white rounded-lg text-sm font-bold hover:bg-primary-container transition-colors flex items-center gap-2">
                <span className="material-symbols-outlined text-lg">add</span> Add
              </button>
            </div>
            {(!client.prescriptions || client.prescriptions.length === 0) ? (
              <div className="p-8 text-center border-2 border-dashed border-outline-variant/30 rounded-xl">
                <span className="material-symbols-outlined text-3xl text-outline-variant mb-2">medication</span>
                <p className="text-sm text-slate-400">No prescriptions added yet.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {client.prescriptions.map((rx, i) => (
                  <div key={i} className="flex items-center justify-between px-5 py-4 bg-surface-container-low rounded-xl group hover:bg-surface-container transition-colors">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg bg-secondary-fixed/30 flex items-center justify-center">
                        <span className="material-symbols-outlined text-on-secondary-container">medication</span>
                      </div>
                      <div>
                        <span className="text-sm font-bold text-blue-950">{rx}</span>
                        <p className="text-[10px] text-slate-400 uppercase tracking-wider">Active Prescription</p>
                      </div>
                    </div>
                    <button onClick={() => removeRx(i)} className="p-2 rounded-lg text-slate-300 hover:text-error hover:bg-error-container/20 transition-all opacity-0 group-hover:opacity-100">
                      <span className="material-symbols-outlined">delete</span>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Doctors */}
      {activeTab === 3 && (
        <div className="max-w-2xl">
          <div className="bg-white rounded-2xl p-8 shadow-sm border border-outline-variant/10">
            <h2 className="font-headline text-xl font-bold text-blue-950 mb-6">Preferred Doctors</h2>
            <div className="flex gap-2 mb-6">
              <input type="text" placeholder="Doctor name" value={docName}
                className="flex-1 px-4 py-3 bg-surface-container-low rounded-lg border-0 border-b-2 border-transparent text-sm focus:ring-0 focus:border-primary"
                onChange={(e) => setDocName(e.target.value)} />
              <input type="text" placeholder="NPI (optional)" value={docNpi}
                className="w-40 px-4 py-3 bg-surface-container-low rounded-lg border-0 border-b-2 border-transparent text-sm focus:ring-0 focus:border-primary"
                onChange={(e) => setDocNpi(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addDoc() } }} />
              <button onClick={addDoc} className="px-6 py-3 bg-primary text-white rounded-lg text-sm font-bold hover:bg-primary-container transition-colors flex items-center gap-2">
                <span className="material-symbols-outlined text-lg">add</span> Add
              </button>
            </div>
            {(!client.doctors || client.doctors.length === 0) ? (
              <div className="p-8 text-center border-2 border-dashed border-outline-variant/30 rounded-xl">
                <span className="material-symbols-outlined text-3xl text-outline-variant mb-2">stethoscope</span>
                <p className="text-sm text-slate-400">No preferred doctors added yet.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {client.doctors.map((doc, i) => (
                  <div key={i} className="flex items-center justify-between px-5 py-4 bg-surface-container-low rounded-xl group hover:bg-surface-container transition-colors">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                        <span className="material-symbols-outlined text-primary">person</span>
                      </div>
                      <div>
                        <span className="text-sm font-bold text-blue-950">{doc.name}</span>
                        {doc.npi && <p className="text-[10px] text-slate-400">NPI: {doc.npi}</p>}
                      </div>
                    </div>
                    <button onClick={() => removeDoc(i)} className="p-2 rounded-lg text-slate-300 hover:text-error hover:bg-error-container/20 transition-all opacity-0 group-hover:opacity-100">
                      <span className="material-symbols-outlined">delete</span>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}
