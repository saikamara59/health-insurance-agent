import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../api/client'

const TABS = ['Plan Analysis', 'Profile Details', 'Prescriptions', 'Preferred Doctors']

const WORKFLOW_STEPS = [
  {
    number: 1,
    title: 'Extract Data',
    description: 'Parse and translate Summary of Benefits documents into structured data.',
    icon: 'description',
    endpoint: '/translate',
    buildPayload: (client) => ({
      document_text: `Summary of Benefits for ${client.full_name}, age ${client.age}, zip ${client.zip_code}, income ${client.income_level}. Prescriptions: ${client.prescriptions.join(', ') || 'none'}. Procedures: ${client.procedures.join(', ') || 'none'}.`,
    }),
  },
  {
    number: 2,
    title: 'Verify Networks',
    description: 'Scrape provider directories to verify doctor and pharmacy network status.',
    icon: 'verified',
    endpoint: '/verify',
    buildPayload: (client) => ({
      doctors: client.doctors || [],
      prescriptions: client.prescriptions || [],
      zip_code: client.zip_code,
    }),
  },
  {
    number: 3,
    title: 'Calculate Risks',
    description: 'Categorize health risk levels and project utilization patterns.',
    icon: 'calculate',
    endpoint: '/calculate',
    buildPayload: (client) => ({
      age: client.age,
      zip_code: client.zip_code,
      income_level: client.income_level,
      prescriptions: client.prescriptions || [],
      procedures: client.procedures || [],
    }),
  },
  {
    number: 4,
    title: 'Compare Plans',
    description: 'Search marketplace for available plans and rank by total cost.',
    icon: 'compare_arrows',
    endpoint: '/compare',
    buildPayload: (client) => ({
      zip_code: client.zip_code,
      age: client.age,
      income_level: client.income_level,
      prescriptions: client.prescriptions || [],
      procedures: client.procedures || [],
      doctors: client.doctors || [],
    }),
  },
  {
    number: 5,
    title: 'Cost Estimate',
    description: 'Generate final cost breakdown with out-of-pocket projections.',
    icon: 'payments',
    endpoint: '/estimate',
    buildPayload: (client) => ({
      zip_code: client.zip_code,
      age: client.age,
      income_level: client.income_level,
      prescriptions: client.prescriptions || [],
      procedures: client.procedures || [],
      doctors: client.doctors || [],
    }),
  },
]

function getInitials(name) {
  return name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)
}

export default function ClientProfilePage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [client, setClient] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState(0)

  // Workflow state
  const [stepStatuses, setStepStatuses] = useState({})
  const [stepResults, setStepResults] = useState({})
  const [stepLoading, setStepLoading] = useState({})

  // Profile edit state
  const [editForm, setEditForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState('')

  // Prescriptions state
  const [newPrescription, setNewPrescription] = useState('')

  // Doctors state
  const [newDoctor, setNewDoctor] = useState({ name: '', npi: '' })

  useEffect(() => {
    loadClient()
  }, [id])

  async function loadClient() {
    setLoading(true)
    try {
      const data = await api.get(`/clients/${id}`)
      setClient(data)
      setEditForm({
        full_name: data.full_name,
        zip_code: data.zip_code,
        age: data.age,
        income_level: data.income_level,
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function runStep(stepIndex) {
    const step = WORKFLOW_STEPS[stepIndex]
    setStepLoading((prev) => ({ ...prev, [stepIndex]: true }))

    try {
      const payload = step.buildPayload(client)
      const result = await api.post(step.endpoint, payload)
      setStepResults((prev) => ({ ...prev, [stepIndex]: result }))
      setStepStatuses((prev) => ({ ...prev, [stepIndex]: 'complete' }))
    } catch (err) {
      setStepResults((prev) => ({ ...prev, [stepIndex]: { error: err.message } }))
      setStepStatuses((prev) => ({ ...prev, [stepIndex]: 'error' }))
    } finally {
      setStepLoading((prev) => ({ ...prev, [stepIndex]: false }))
    }
  }

  async function handleSaveProfile(e) {
    e.preventDefault()
    setSaving(true)
    setSaveMessage('')
    try {
      const updated = await api.put(`/clients/${id}`, {
        full_name: editForm.full_name,
        zip_code: editForm.zip_code,
        age: parseInt(editForm.age, 10),
        income_level: editForm.income_level,
      })
      setClient(updated)
      setSaveMessage('Profile saved successfully.')
    } catch (err) {
      setSaveMessage(`Error: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  async function addPrescription() {
    if (!newPrescription.trim()) return
    const updated = [...(client.prescriptions || []), newPrescription.trim()]
    try {
      const result = await api.put(`/clients/${id}`, { prescriptions: updated })
      setClient(result)
      setNewPrescription('')
    } catch (err) {
      alert(err.message)
    }
  }

  async function removePrescription(index) {
    const updated = client.prescriptions.filter((_, i) => i !== index)
    try {
      const result = await api.put(`/clients/${id}`, { prescriptions: updated })
      setClient(result)
    } catch (err) {
      alert(err.message)
    }
  }

  async function addDoctor() {
    if (!newDoctor.name.trim()) return
    const updated = [...(client.doctors || []), { name: newDoctor.name.trim(), npi: newDoctor.npi.trim() }]
    try {
      const result = await api.put(`/clients/${id}`, { doctors: updated })
      setClient(result)
      setNewDoctor({ name: '', npi: '' })
    } catch (err) {
      alert(err.message)
    }
  }

  async function removeDoctor(index) {
    const updated = client.doctors.filter((_, i) => i !== index)
    try {
      const result = await api.put(`/clients/${id}`, { doctors: updated })
      setClient(result)
    } catch (err) {
      alert(err.message)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <span className="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
      </div>
    )
  }

  if (error || !client) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px]">
        <span className="material-symbols-outlined text-4xl text-error mb-4">error</span>
        <p className="text-error text-sm">{error || 'Client not found'}</p>
        <button
          className="mt-4 text-sm text-primary font-medium hover:underline"
          onClick={() => navigate('/')}
        >
          Back to Portfolio
        </button>
      </div>
    )
  }

  return (
    <div>
      {/* Client Header */}
      <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-8 mb-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-6">
            <div className="w-16 h-16 bg-primary rounded-2xl flex items-center justify-center">
              <span className="text-on-primary text-xl font-bold">{getInitials(client.full_name)}</span>
            </div>
            <div>
              <h1 className="font-headline text-2xl font-bold text-on-surface">{client.full_name}</h1>
              <div className="flex items-center gap-4 mt-2 text-sm text-on-surface-variant">
                <span className="flex items-center gap-1">
                  <span className="material-symbols-outlined text-base">cake</span>
                  Age {client.age}
                </span>
                <span className="flex items-center gap-1">
                  <span className="material-symbols-outlined text-base">attach_money</span>
                  {client.income_level.charAt(0).toUpperCase() + client.income_level.slice(1)} Income
                </span>
                <span className="flex items-center gap-1">
                  <span className="material-symbols-outlined text-base">location_on</span>
                  {client.zip_code}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-secondary-container text-on-secondary-container text-sm font-medium">
              <span className="material-symbols-outlined text-sm">check_circle</span>
              Active Client
            </span>
            <button
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl border border-outline-variant text-on-surface-variant font-medium text-sm hover:bg-surface-container-high transition-colors"
              onClick={() => setActiveTab(1)}
            >
              <span className="material-symbols-outlined text-lg">edit</span>
              Edit Profile
            </button>
            <button
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-on-primary font-semibold text-sm hover:bg-primary-container transition-colors"
              onClick={() => {
                // Navigate or open appeal generation
              }}
            >
              <span className="material-symbols-outlined text-lg">gavel</span>
              Generate Appeal Draft
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-surface-container-low rounded-xl p-1">
        {TABS.map((tab, i) => (
          <button
            key={tab}
            className={`flex-1 py-3 px-4 rounded-xl text-sm font-medium transition-colors ${
              activeTab === i
                ? 'bg-surface-container-lowest text-primary shadow-sm'
                : 'text-on-surface-variant hover:text-on-surface'
            }`}
            onClick={() => setActiveTab(i)}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 0 && (
        <div>
          {/* Analysis Workflow */}
          <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-8 mb-6">
            <h2 className="font-headline text-xl font-bold text-on-surface mb-6">Analysis Workflow</h2>

            <div className="space-y-4">
              {WORKFLOW_STEPS.map((step, index) => {
                const status = stepStatuses[index]
                const isRunning = stepLoading[index]
                const result = stepResults[index]

                return (
                  <div key={index} className="border border-outline-variant rounded-xl p-6">
                    <div className="flex items-start gap-4">
                      {/* Step number circle */}
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                        status === 'complete'
                          ? 'bg-secondary text-on-secondary'
                          : status === 'error'
                            ? 'bg-error text-on-error'
                            : 'bg-surface-container-high text-on-surface-variant'
                      }`}>
                        {status === 'complete' ? (
                          <span className="material-symbols-outlined text-lg">check</span>
                        ) : (
                          <span className="text-sm font-bold">{step.number}</span>
                        )}
                      </div>

                      {/* Step content */}
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-1">
                          <h3 className="text-base font-semibold text-on-surface">{step.title}</h3>
                          {status === 'complete' && (
                            <span className="px-2.5 py-0.5 text-xs font-medium rounded-full bg-secondary-container text-on-secondary-container">
                              Complete
                            </span>
                          )}
                          {status === 'error' && (
                            <span className="px-2.5 py-0.5 text-xs font-medium rounded-full bg-error-container text-on-error-container">
                              Error
                            </span>
                          )}
                          {isRunning && (
                            <span className="px-2.5 py-0.5 text-xs font-medium rounded-full bg-primary-fixed text-on-primary-fixed">
                              In Progress
                            </span>
                          )}
                          {!status && !isRunning && (
                            <span className="px-2.5 py-0.5 text-xs font-medium rounded-full bg-surface-container-high text-on-surface-variant">
                              Pending
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-on-surface-variant mb-3">{step.description}</p>

                        <button
                          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-on-primary text-sm font-medium hover:bg-primary-container transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                          onClick={() => runStep(index)}
                          disabled={isRunning}
                        >
                          {isRunning ? (
                            <>
                              <span className="material-symbols-outlined text-sm animate-spin">progress_activity</span>
                              Running...
                            </>
                          ) : (
                            <>
                              <span className="material-symbols-outlined text-sm">{step.icon}</span>
                              {status === 'complete' ? 'Re-run' : 'Run'}
                            </>
                          )}
                        </button>

                        {/* Result display */}
                        {result && (
                          <div className={`mt-4 p-4 rounded-xl text-sm ${
                            result.error
                              ? 'bg-error-container text-on-error-container'
                              : 'bg-surface-container-low text-on-surface'
                          }`}>
                            <pre className="whitespace-pre-wrap font-body text-xs overflow-auto max-h-64">
                              {JSON.stringify(result, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-6">
              <div className="flex items-center gap-3 mb-3">
                <span className="material-symbols-outlined text-primary text-2xl">payments</span>
                <h3 className="text-sm font-semibold text-on-surface-variant uppercase tracking-wider">Annual Out-of-Pocket</h3>
              </div>
              <p className="text-3xl font-bold text-on-surface font-headline">
                {stepResults[4]?.estimated_annual_cost
                  ? `$${Number(stepResults[4].estimated_annual_cost).toLocaleString()}`
                  : '--'}
              </p>
              <p className="text-xs text-on-surface-variant mt-1">Run cost estimate to calculate</p>
            </div>
            <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-6">
              <div className="flex items-center gap-3 mb-3">
                <span className="material-symbols-outlined text-secondary text-2xl">savings</span>
                <h3 className="text-sm font-semibold text-on-surface-variant uppercase tracking-wider">Projected Savings</h3>
              </div>
              <p className="text-3xl font-bold text-on-surface font-headline">
                {stepResults[3]?.potential_savings
                  ? `$${Number(stepResults[3].potential_savings).toLocaleString()}`
                  : '--'}
              </p>
              <p className="text-xs text-on-surface-variant mt-1">Run plan comparison to calculate</p>
            </div>
          </div>
        </div>
      )}

      {activeTab === 1 && editForm && (
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-8">
          <h2 className="font-headline text-xl font-bold text-on-surface mb-6">Profile Details</h2>

          {saveMessage && (
            <div className={`mb-6 p-4 rounded-xl ${
              saveMessage.startsWith('Error')
                ? 'bg-error-container text-on-error-container'
                : 'bg-secondary-container text-on-secondary-container'
            }`}>
              <p className="text-sm">{saveMessage}</p>
            </div>
          )}

          <form className="space-y-5 max-w-lg" onSubmit={handleSaveProfile}>
            <div>
              <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
                Full Name
              </label>
              <input
                type="text"
                className="w-full px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface focus:ring-2 focus:ring-primary/20"
                value={editForm.full_name}
                onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
                  Zip Code
                </label>
                <input
                  type="text"
                  className="w-full px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface focus:ring-2 focus:ring-primary/20"
                  value={editForm.zip_code}
                  onChange={(e) => setEditForm({ ...editForm, zip_code: e.target.value })}
                  required
                  maxLength={5}
                  pattern="\d{5}"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
                  Age
                </label>
                <input
                  type="number"
                  className="w-full px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface focus:ring-2 focus:ring-primary/20"
                  value={editForm.age}
                  onChange={(e) => setEditForm({ ...editForm, age: e.target.value })}
                  required
                  min={18}
                  max={120}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
                Income Level
              </label>
              <select
                className="w-full px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface focus:ring-2 focus:ring-primary/20"
                value={editForm.income_level}
                onChange={(e) => setEditForm({ ...editForm, income_level: e.target.value })}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </div>

            <button
              type="submit"
              className="flex items-center gap-2 bg-primary hover:bg-primary-container text-on-primary font-semibold px-6 py-3 rounded-xl transition-colors disabled:opacity-50"
              disabled={saving}
            >
              <span className="material-symbols-outlined text-lg">save</span>
              {saving ? 'Saving...' : 'Save Profile'}
            </button>
          </form>
        </div>
      )}

      {activeTab === 2 && (
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-8">
          <h2 className="font-headline text-xl font-bold text-on-surface mb-6">Prescriptions</h2>

          {/* Add prescription */}
          <div className="flex gap-3 mb-6">
            <input
              type="text"
              className="flex-1 px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface placeholder:text-outline focus:ring-2 focus:ring-primary/20"
              placeholder="Enter prescription name"
              value={newPrescription}
              onChange={(e) => setNewPrescription(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addPrescription())}
            />
            <button
              className="flex items-center gap-2 px-5 py-3 bg-primary text-on-primary font-semibold rounded-xl hover:bg-primary-container transition-colors text-sm"
              onClick={addPrescription}
            >
              <span className="material-symbols-outlined text-lg">add</span>
              Add
            </button>
          </div>

          {/* Prescription list */}
          {(!client.prescriptions || client.prescriptions.length === 0) ? (
            <p className="text-sm text-on-surface-variant">No prescriptions added yet.</p>
          ) : (
            <ul className="space-y-2">
              {client.prescriptions.map((rx, i) => (
                <li key={i} className="flex items-center justify-between px-4 py-3 bg-surface-container-low rounded-xl">
                  <div className="flex items-center gap-3">
                    <span className="material-symbols-outlined text-primary text-lg">medication</span>
                    <span className="text-sm font-medium text-on-surface">{rx}</span>
                  </div>
                  <button
                    className="p-1.5 rounded-lg hover:bg-error-container transition-colors"
                    onClick={() => removePrescription(i)}
                  >
                    <span className="material-symbols-outlined text-lg text-error">close</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {activeTab === 3 && (
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-8">
          <h2 className="font-headline text-xl font-bold text-on-surface mb-6">Preferred Doctors</h2>

          {/* Add doctor */}
          <div className="flex gap-3 mb-6">
            <input
              type="text"
              className="flex-1 px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface placeholder:text-outline focus:ring-2 focus:ring-primary/20"
              placeholder="Doctor name"
              value={newDoctor.name}
              onChange={(e) => setNewDoctor({ ...newDoctor, name: e.target.value })}
            />
            <input
              type="text"
              className="w-40 px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface placeholder:text-outline focus:ring-2 focus:ring-primary/20"
              placeholder="NPI (optional)"
              value={newDoctor.npi}
              onChange={(e) => setNewDoctor({ ...newDoctor, npi: e.target.value })}
            />
            <button
              className="flex items-center gap-2 px-5 py-3 bg-primary text-on-primary font-semibold rounded-xl hover:bg-primary-container transition-colors text-sm"
              onClick={addDoctor}
            >
              <span className="material-symbols-outlined text-lg">add</span>
              Add
            </button>
          </div>

          {/* Doctor list */}
          {(!client.doctors || client.doctors.length === 0) ? (
            <p className="text-sm text-on-surface-variant">No preferred doctors added yet.</p>
          ) : (
            <ul className="space-y-2">
              {client.doctors.map((doc, i) => (
                <li key={i} className="flex items-center justify-between px-4 py-3 bg-surface-container-low rounded-xl">
                  <div className="flex items-center gap-3">
                    <span className="material-symbols-outlined text-primary text-lg">stethoscope</span>
                    <div>
                      <span className="text-sm font-medium text-on-surface">{doc.name}</span>
                      {doc.npi && (
                        <span className="ml-3 text-xs text-on-surface-variant">NPI: {doc.npi}</span>
                      )}
                    </div>
                  </div>
                  <button
                    className="p-1.5 rounded-lg hover:bg-error-container transition-colors"
                    onClick={() => removeDoctor(i)}
                  >
                    <span className="material-symbols-outlined text-lg text-error">close</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
