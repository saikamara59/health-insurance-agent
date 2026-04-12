import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'

const STEPS = ['PERSONAL', 'FINANCIAL', 'HEALTHCARE', 'REVIEW']

export default function AddClientPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // Form state
  const [form, setForm] = useState({
    full_name: '',
    zip_code: '',
    age: '',
    income_level: 'medium',
    email: '',
    phone: '',
    prescriptions: [],
    doctors: [],
    procedures: [],
  })

  // Temp inputs
  const [rxInput, setRxInput] = useState('')
  const [docName, setDocName] = useState('')
  const [docNpi, setDocNpi] = useState('')
  const [procInput, setProcInput] = useState('')

  function addRx() {
    if (rxInput.trim()) {
      setForm({ ...form, prescriptions: [...form.prescriptions, rxInput.trim()] })
      setRxInput('')
    }
  }

  function addDoc() {
    if (docName.trim()) {
      setForm({ ...form, doctors: [...form.doctors, { name: docName.trim(), npi: docNpi.trim() || null }] })
      setDocName(''); setDocNpi('')
    }
  }

  function addProc() {
    if (procInput.trim()) {
      setForm({ ...form, procedures: [...form.procedures, procInput.trim()] })
      setProcInput('')
    }
  }

  async function handleSubmit() {
    setError('')
    setLoading(true)
    try {
      const res = await api.post('/clients', {
        full_name: form.full_name,
        zip_code: form.zip_code,
        age: parseInt(form.age, 10),
        income_level: form.income_level,
        prescriptions: form.prescriptions,
        doctors: form.doctors,
        procedures: form.procedures,
      })
      navigate(`/clients/success?id=${res.id}`)
    } catch (err) {
      setError(err.message || 'Failed to create client')
      setLoading(false)
    }
  }

  function canAdvance() {
    if (step === 0) return form.full_name && form.zip_code && form.age
    if (step === 1) return form.income_level
    return true
  }

  const inputCls = "w-full bg-surface-container-low border-0 border-b-2 border-transparent py-4 px-0 text-lg font-medium transition-all focus:ring-0 focus:border-primary"

  return (
    <>
      {/* Header */}
      <div className="mb-12">
        <div className="flex items-center gap-4 text-primary mb-2">
          <span className="material-symbols-outlined">person_add</span>
          <span className="font-label text-xs uppercase tracking-widest font-bold">New Intake Journey</span>
        </div>
        <h1 className="text-4xl font-black font-headline tracking-tighter text-primary">Add New Client</h1>
        <p className="text-slate-500 mt-2 max-w-xl leading-relaxed">
          Ensure all clinical and financial fields are accurately populated to maintain institutional compliance standards.
        </p>
      </div>

      {/* Stepper */}
      <div className="flex items-center justify-between mb-16 relative max-w-2xl">
        <div className="absolute top-5 left-0 w-full h-px bg-slate-200 -z-10"></div>
        {STEPS.map((label, i) => (
          <div key={label} className="flex flex-col items-center gap-2 cursor-pointer" onClick={() => i < step && setStep(i)}>
            <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold z-10 transition-all ${
              i < step ? 'bg-secondary text-white shadow-md' :
              i === step ? 'bg-primary text-on-primary shadow-md' :
              'bg-white border-2 border-slate-200 text-slate-400'
            }`}>
              {i < step ? <span className="material-symbols-outlined text-lg">check</span> : i + 1}
            </div>
            <span className={`text-xs font-bold font-label ${i === step ? 'text-primary' : 'text-slate-400'}`}>{label}</span>
          </div>
        ))}
      </div>

      {error && (
        <div className="mb-8 p-4 bg-error-container rounded-xl">
          <p className="text-sm text-on-error-container">{error}</p>
        </div>
      )}

      {/* Form Content */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
        <div className="md:col-span-8 bg-surface-container-lowest p-10 rounded-xl shadow-[0_32px_64px_-12px_rgba(0,62,122,0.08)]">

          {/* Step 1: Personal */}
          {step === 0 && (
            <>
              <h2 className="text-2xl font-bold font-headline mb-8 text-primary">1. Personal Information</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-10">
                <div className="col-span-2">
                  <label className="block text-xs font-bold font-label text-slate-500 mb-2 uppercase tracking-wide">Full Name</label>
                  <input className={inputCls} placeholder="e.g. Jane Doe" type="text"
                    value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
                </div>
                <div>
                  <label className="block text-xs font-bold font-label text-slate-500 mb-2 uppercase tracking-wide">Zip Code</label>
                  <input className={inputCls} placeholder="e.g. 10001" type="text" maxLength={5}
                    value={form.zip_code} onChange={(e) => setForm({ ...form, zip_code: e.target.value })} />
                </div>
                <div>
                  <label className="block text-xs font-bold font-label text-slate-500 mb-2 uppercase tracking-wide">Age</label>
                  <input className={inputCls} placeholder="e.g. 42" type="number" min={18} max={120}
                    value={form.age} onChange={(e) => setForm({ ...form, age: e.target.value })} />
                </div>
                <div>
                  <label className="block text-xs font-bold font-label text-slate-500 mb-2 uppercase tracking-wide">Phone (Optional)</label>
                  <input className={inputCls} placeholder="+1 (555) 000-0000" type="tel"
                    value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                </div>
                <div>
                  <label className="block text-xs font-bold font-label text-slate-500 mb-2 uppercase tracking-wide">Email (Optional)</label>
                  <input className={inputCls} placeholder="client@example.com" type="email"
                    value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
                </div>
              </div>
            </>
          )}

          {/* Step 2: Financial */}
          {step === 1 && (
            <>
              <h2 className="text-2xl font-bold font-headline mb-8 text-primary">2. Financial Profile</h2>
              <div className="space-y-10">
                <div>
                  <label className="block text-xs font-bold font-label text-slate-500 mb-2 uppercase tracking-wide">Income Level</label>
                  <div className="grid grid-cols-3 gap-4 mt-4">
                    {['low', 'medium', 'high'].map((level) => (
                      <button key={level} type="button"
                        onClick={() => setForm({ ...form, income_level: level })}
                        className={`p-6 rounded-xl text-center transition-all ${
                          form.income_level === level
                            ? 'bg-primary text-white shadow-lg shadow-primary/20'
                            : 'bg-surface-container-low text-on-surface-variant hover:bg-surface-container border border-outline-variant/20'
                        }`}>
                        <span className="material-symbols-outlined text-3xl mb-2">
                          {level === 'low' ? 'savings' : level === 'medium' ? 'account_balance_wallet' : 'diamond'}
                        </span>
                        <p className="font-bold capitalize text-lg">{level}</p>
                        <p className="text-xs mt-1 opacity-70">
                          {level === 'low' ? 'Under $30k' : level === 'medium' ? '$30k — $75k' : 'Over $75k'}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Step 3: Healthcare */}
          {step === 2 && (
            <>
              <h2 className="text-2xl font-bold font-headline mb-8 text-primary">3. Healthcare Profile</h2>
              <div className="space-y-10">
                {/* Prescriptions */}
                <div>
                  <label className="block text-xs font-bold font-label text-primary mb-3 uppercase tracking-widest flex items-center gap-2">
                    <span className="material-symbols-outlined text-sm">medication</span> Prescriptions
                  </label>
                  <div className="flex gap-2 mb-3">
                    <input type="text" placeholder="e.g. Metformin, Lisinopril..." value={rxInput}
                      className="flex-1 px-4 py-3 bg-surface-container-low rounded-lg border-0 border-b-2 border-transparent text-sm focus:ring-0 focus:border-primary"
                      onChange={(e) => setRxInput(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addRx() } }} />
                    <button type="button" onClick={addRx}
                      className="px-5 py-3 bg-primary text-white rounded-lg text-sm font-bold hover:bg-primary-container transition-colors">
                      Add
                    </button>
                  </div>
                  {form.prescriptions.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {form.prescriptions.map((rx, i) => (
                        <span key={i} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-secondary-fixed/30 text-on-secondary-container rounded-full text-xs font-bold">
                          <span className="material-symbols-outlined text-xs">medication</span> {rx}
                          <button type="button" onClick={() => setForm({ ...form, prescriptions: form.prescriptions.filter((_, j) => j !== i) })}
                            className="ml-1 hover:text-error"><span className="material-symbols-outlined text-xs">close</span></button>
                        </span>
                      ))}
                    </div>
                  ) : <p className="text-xs text-slate-400 italic">No prescriptions added yet.</p>}
                </div>

                {/* Doctors */}
                <div>
                  <label className="block text-xs font-bold font-label text-primary mb-3 uppercase tracking-widest flex items-center gap-2">
                    <span className="material-symbols-outlined text-sm">stethoscope</span> Preferred Doctors
                  </label>
                  <div className="flex gap-2 mb-3">
                    <input type="text" placeholder="Doctor name" value={docName}
                      className="flex-1 px-4 py-3 bg-surface-container-low rounded-lg border-0 border-b-2 border-transparent text-sm focus:ring-0 focus:border-primary"
                      onChange={(e) => setDocName(e.target.value)} />
                    <input type="text" placeholder="NPI (optional)" value={docNpi}
                      className="w-40 px-4 py-3 bg-surface-container-low rounded-lg border-0 border-b-2 border-transparent text-sm focus:ring-0 focus:border-primary"
                      onChange={(e) => setDocNpi(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addDoc() } }} />
                    <button type="button" onClick={addDoc}
                      className="px-5 py-3 bg-primary text-white rounded-lg text-sm font-bold hover:bg-primary-container transition-colors">
                      Add
                    </button>
                  </div>
                  {form.doctors.length > 0 ? (
                    <div className="space-y-2">
                      {form.doctors.map((doc, i) => (
                        <div key={i} className="flex items-center justify-between px-4 py-3 bg-surface-container-low rounded-lg">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                              <span className="material-symbols-outlined text-primary text-sm">person</span>
                            </div>
                            <div>
                              <p className="text-sm font-medium text-on-surface">{doc.name}</p>
                              {doc.npi && <p className="text-[10px] text-slate-400">NPI: {doc.npi}</p>}
                            </div>
                          </div>
                          <button type="button" onClick={() => setForm({ ...form, doctors: form.doctors.filter((_, j) => j !== i) })}
                            className="p-1 text-slate-400 hover:text-error"><span className="material-symbols-outlined text-sm">close</span></button>
                        </div>
                      ))}
                    </div>
                  ) : <p className="text-xs text-slate-400 italic">No doctors added yet.</p>}
                </div>

                {/* Procedures */}
                <div>
                  <label className="block text-xs font-bold font-label text-primary mb-3 uppercase tracking-widest flex items-center gap-2">
                    <span className="material-symbols-outlined text-sm">medical_services</span> Expected Procedures
                  </label>
                  <div className="flex gap-2 mb-3">
                    <input type="text" placeholder="e.g. MRI, Blood work..." value={procInput}
                      className="flex-1 px-4 py-3 bg-surface-container-low rounded-lg border-0 border-b-2 border-transparent text-sm focus:ring-0 focus:border-primary"
                      onChange={(e) => setProcInput(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addProc() } }} />
                    <button type="button" onClick={addProc}
                      className="px-5 py-3 bg-primary text-white rounded-lg text-sm font-bold hover:bg-primary-container transition-colors">
                      Add
                    </button>
                  </div>
                  {form.procedures.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {form.procedures.map((proc, i) => (
                        <span key={i} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-tertiary-fixed/30 text-on-tertiary-fixed-variant rounded-full text-xs font-bold">
                          <span className="material-symbols-outlined text-xs">medical_services</span> {proc}
                          <button type="button" onClick={() => setForm({ ...form, procedures: form.procedures.filter((_, j) => j !== i) })}
                            className="ml-1 hover:text-error"><span className="material-symbols-outlined text-xs">close</span></button>
                        </span>
                      ))}
                    </div>
                  ) : <p className="text-xs text-slate-400 italic">No procedures added yet.</p>}
                </div>
              </div>
            </>
          )}

          {/* Step 4: Review */}
          {step === 3 && (
            <>
              <h2 className="text-2xl font-bold font-headline mb-8 text-primary">4. Review & Submit</h2>
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-6">
                  <div className="p-4 bg-surface-container-low rounded-lg">
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Full Name</p>
                    <p className="font-bold text-on-surface">{form.full_name || '—'}</p>
                  </div>
                  <div className="p-4 bg-surface-container-low rounded-lg">
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Age</p>
                    <p className="font-bold text-on-surface">{form.age || '—'}</p>
                  </div>
                  <div className="p-4 bg-surface-container-low rounded-lg">
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Zip Code</p>
                    <p className="font-bold text-on-surface">{form.zip_code || '—'}</p>
                  </div>
                  <div className="p-4 bg-surface-container-low rounded-lg">
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Income Level</p>
                    <p className="font-bold text-on-surface capitalize">{form.income_level}</p>
                  </div>
                </div>

                {form.prescriptions.length > 0 && (
                  <div className="p-4 bg-surface-container-low rounded-lg">
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Prescriptions ({form.prescriptions.length})</p>
                    <div className="flex flex-wrap gap-2">
                      {form.prescriptions.map((rx, i) => (
                        <span key={i} className="px-3 py-1 bg-secondary-fixed/30 text-on-secondary-container rounded-full text-xs font-bold">{rx}</span>
                      ))}
                    </div>
                  </div>
                )}

                {form.doctors.length > 0 && (
                  <div className="p-4 bg-surface-container-low rounded-lg">
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Doctors ({form.doctors.length})</p>
                    {form.doctors.map((doc, i) => (
                      <p key={i} className="text-sm font-medium">{doc.name}{doc.npi ? ` (NPI: ${doc.npi})` : ''}</p>
                    ))}
                  </div>
                )}

                {form.procedures.length > 0 && (
                  <div className="p-4 bg-surface-container-low rounded-lg">
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Procedures ({form.procedures.length})</p>
                    <div className="flex flex-wrap gap-2">
                      {form.procedures.map((proc, i) => (
                        <span key={i} className="px-3 py-1 bg-tertiary-fixed/30 text-on-tertiary-fixed-variant rounded-full text-xs font-bold">{proc}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Sidebar */}
        <div className="md:col-span-4 space-y-6">
          <div className="bg-primary text-on-primary p-8 rounded-xl overflow-hidden relative group">
            <div className="absolute -right-12 -top-12 w-32 h-32 bg-white/10 rounded-full blur-3xl transition-all group-hover:scale-150"></div>
            <span className="material-symbols-outlined text-4xl mb-4">security</span>
            <h3 className="font-headline font-bold text-lg mb-2">HIPAA Encrypted</h3>
            <p className="text-sm text-blue-100/80 leading-relaxed">All clinical data entered here is protected by 256-bit encryption and complies with institutional privacy regulations.</p>
          </div>
          <div className="p-8 border border-slate-200 rounded-xl">
            <h4 className="font-headline font-bold text-sm mb-4">Intake Progress</h4>
            <ul className="space-y-4">
              {STEPS.map((s, i) => (
                <li key={s} className="flex items-start gap-3">
                  <span className={`material-symbols-outlined text-sm mt-1 ${i <= step ? 'text-green-500' : 'text-slate-300'}`}
                    style={i < step ? { fontVariationSettings: "'FILL' 1" } : {}}>
                    {i < step ? 'check_circle' : 'circle'}
                  </span>
                  <span className={`text-sm ${i === step ? 'text-primary font-bold' : 'text-slate-600'}`}>{s.charAt(0) + s.slice(1).toLowerCase()} Details</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between pt-12 mt-12 border-t border-slate-100">
        <button onClick={() => step === 0 ? navigate('/clients') : setStep(step - 1)}
          className="flex items-center gap-2 text-slate-400 font-bold hover:text-slate-600 transition-colors">
          <span className="material-symbols-outlined">arrow_back</span>
          {step === 0 ? 'CANCEL' : 'BACK'}
        </button>
        <div className="flex items-center gap-6">
          {step < 3 ? (
            <button onClick={() => setStep(step + 1)} disabled={!canAdvance()}
              className="bg-primary hover:bg-primary-container text-on-primary px-10 py-4 rounded-lg font-bold shadow-xl shadow-primary/20 transition-all flex items-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed">
              NEXT: {STEPS[step + 1]}
              <span className="material-symbols-outlined">arrow_forward</span>
            </button>
          ) : (
            <button onClick={handleSubmit} disabled={loading}
              className="bg-secondary hover:bg-secondary-container text-on-secondary px-10 py-4 rounded-lg font-bold shadow-xl shadow-secondary/20 transition-all flex items-center gap-3 disabled:opacity-50">
              {loading ? 'CREATING...' : 'SUBMIT CLIENT'}
              <span className="material-symbols-outlined">check_circle</span>
            </button>
          )}
        </div>
      </div>
    </>
  )
}
