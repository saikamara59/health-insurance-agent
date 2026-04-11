import { useState } from 'react'

const KNOWLEDGE_CARDS = [
  { icon: 'clinical_notes', color: 'bg-primary-fixed text-primary', title: 'Clinical Integration', desc: 'Master the HealthFlow API and direct HL7/FHIR data synchronization protocols.' },
  { icon: 'security', color: 'bg-secondary-fixed text-secondary', title: 'Compliance & Security', desc: 'Detailed HIPAA documentation, SOC2 reports, and institutional security guidelines.' },
  { icon: 'analytics', color: 'bg-tertiary-fixed text-tertiary', title: 'Analytics Engine', desc: 'Understanding predictive modeling and patient population cohort analysis tools.' },
  { icon: 'manage_accounts', color: 'bg-primary-fixed text-primary', title: 'User Management', desc: 'Admin controls for staff permissions, role-based access, and audit logging.' },
]

const UPDATES = [
  { date: 'APR 10, 2026', title: 'Enhanced Telemetry V2.4 Deployment', desc: 'Improving real-time vitals monitoring latency for remote care portfolios.' },
  { date: 'APR 04, 2026', title: 'Security Infrastructure Maintenance', desc: 'Scheduled optimization for the institutional identity management gateway.' },
]

export default function SupportPage() {
  const [category, setCategory] = useState('Technical Integration Support')
  const [urgency, setUrgency] = useState('standard')
  const [description, setDescription] = useState('')
  const [submitted, setSubmitted] = useState(false)

  function handleSubmit(e) {
    e.preventDefault()
    setSubmitted(true)
    setTimeout(() => { setSubmitted(false); setDescription('') }, 3000)
  }

  return (
    <>
      {/* Hero */}
      <section className="mb-16">
        <div className="relative overflow-hidden rounded-xl bg-primary-container p-12 text-on-primary">
          <div className="relative z-10 max-w-2xl">
            <p className="uppercase tracking-widest text-xs font-bold mb-4 opacity-80 font-label">Institutional Access</p>
            <h1 className="text-5xl font-extrabold tracking-tight mb-6 leading-tight font-display">HealthFlow Support Center</h1>
            <p className="text-xl opacity-90 leading-relaxed mb-8">
              Access professional resources, technical documentation, and direct clinical assistance for the Vitalis ecosystem.
            </p>
            <div className="relative max-w-md">
              <input
                className="w-full pl-12 pr-4 py-4 rounded-lg bg-surface text-on-surface border-none shadow-xl focus:ring-2 focus:ring-secondary transition-all"
                placeholder="Search knowledge base..."
                type="text"
              />
              <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">search</span>
            </div>
          </div>
        </div>
      </section>

      {/* Knowledge Library + Ticket Form */}
      <section className="grid grid-cols-1 md:grid-cols-12 gap-8 mb-16">
        <div className="md:col-span-8">
          <div className="flex items-center justify-between mb-8">
            <h2 className="text-3xl font-bold text-blue-900 tracking-tight font-headline">Knowledge Library</h2>
            <button className="text-secondary font-semibold flex items-center gap-2 hover:underline">
              View All Documentation <span className="material-symbols-outlined text-sm">arrow_forward</span>
            </button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {KNOWLEDGE_CARDS.map((card) => (
              <div key={card.title} className="p-8 bg-surface-container-low rounded-xl hover:shadow-lg transition-all group cursor-pointer">
                <div className={`w-12 h-12 rounded-lg ${card.color} flex items-center justify-center mb-6 group-hover:scale-110 transition-transform`}>
                  <span className="material-symbols-outlined">{card.icon}</span>
                </div>
                <h3 className="text-xl font-bold mb-3 text-blue-900">{card.title}</h3>
                <p className="text-on-surface-variant text-sm leading-relaxed">{card.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Ticket Form */}
        <aside className="md:col-span-4">
          <div className="bg-white p-8 rounded-xl shadow-sm border border-outline-variant/10">
            <h2 className="text-2xl font-bold text-blue-900 mb-6 tracking-tight font-headline">Submit Ticket</h2>
            <form className="space-y-6" onSubmit={handleSubmit}>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-2 font-label">Issue Category</label>
                <select
                  className="w-full bg-surface-container-lowest border-none border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-sm py-3 transition-all"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  <option>Technical Integration Support</option>
                  <option>Billing & Claims Portal</option>
                  <option>Clinical Data Discrepancy</option>
                  <option>Security & Access Recovery</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-2 font-label">Urgency Level</label>
                <div className="flex gap-4">
                  <label
                    className={`flex-1 text-center py-2 px-4 rounded-lg cursor-pointer transition-all ${
                      urgency === 'standard' ? 'bg-primary text-white' : 'bg-surface-container-low hover:bg-surface-container'
                    }`}
                  >
                    <input className="hidden" name="urgency" type="radio" checked={urgency === 'standard'} onChange={() => setUrgency('standard')} />
                    <span className="text-sm font-medium">Standard</span>
                  </label>
                  <label
                    className={`flex-1 text-center py-2 px-4 rounded-lg cursor-pointer transition-all ${
                      urgency === 'urgent' ? 'bg-error text-white' : 'bg-surface-container-low hover:bg-error-container/20'
                    }`}
                  >
                    <input className="hidden" name="urgency" type="radio" checked={urgency === 'urgent'} onChange={() => setUrgency('urgent')} />
                    <span className="text-sm font-medium">Urgent</span>
                  </label>
                </div>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-2 font-label">Detailed Description</label>
                <textarea
                  className="w-full bg-surface-container-lowest border-none border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-sm py-3 transition-all resize-none"
                  placeholder="Provide clinical context or error codes..."
                  rows={4}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                ></textarea>
              </div>
              <button
                className="w-full bg-primary text-on-primary py-4 rounded-lg font-bold shadow-lg shadow-primary/20 hover:shadow-xl hover:translate-y-[-2px] transition-all flex items-center justify-center gap-2"
                type="submit"
              >
                <span className="material-symbols-outlined text-xl">send</span>
                {submitted ? 'Ticket Submitted!' : 'Submit Support Request'}
              </button>
            </form>
            <p className="mt-6 text-xs text-on-surface-variant text-center italic">Institutional average response time: 2.4 hours</p>
          </div>
        </aside>
      </section>

      {/* Recent Updates */}
      <section className="mb-16">
        <h2 className="text-2xl font-bold text-blue-900 mb-8 tracking-tight font-headline">Recent System Updates</h2>
        <div className="space-y-4">
          {UPDATES.map((update) => (
            <div key={update.title} className="flex items-center gap-6 p-6 bg-white rounded-lg hover:bg-surface-container transition-colors cursor-pointer">
              <span className="text-sm font-bold text-secondary font-label min-w-[100px]">{update.date}</span>
              <div className="flex-1">
                <h4 className="font-bold text-blue-950">{update.title}</h4>
                <p className="text-sm text-on-surface-variant">{update.desc}</p>
              </div>
              <span className="material-symbols-outlined text-slate-300">chevron_right</span>
            </div>
          ))}
        </div>
      </section>

      {/* Contact Cards */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12">
        <div className="p-8 bg-blue-900 text-white rounded-xl relative overflow-hidden">
          <div className="relative z-10">
            <h3 className="text-xl font-bold mb-2">Direct Phone Support</h3>
            <p className="text-blue-100 mb-6 opacity-80">Reserved for VIP Clinical Institutional access.</p>
            <p className="text-2xl font-extrabold tracking-tighter">+1 (800) HLT-FLOW</p>
          </div>
          <div className="absolute -bottom-4 -right-4 opacity-10">
            <span className="material-symbols-outlined text-[96px]">support_agent</span>
          </div>
        </div>
        <div className="p-8 bg-secondary text-white rounded-xl relative overflow-hidden">
          <div className="relative z-10">
            <h3 className="text-xl font-bold mb-2">Live Clinician Chat</h3>
            <p className="text-blue-100 mb-6 opacity-80">Real-time collaboration with medical specialists.</p>
            <button className="bg-white text-secondary px-6 py-2 rounded-lg font-bold text-sm hover:bg-blue-50 transition-colors">Start Chat Now</button>
          </div>
          <div className="absolute -bottom-4 -right-4 opacity-10">
            <span className="material-symbols-outlined text-[96px]">chat_bubble</span>
          </div>
        </div>
        <div className="p-8 bg-tertiary text-white rounded-xl relative overflow-hidden">
          <div className="relative z-10">
            <h3 className="text-xl font-bold mb-2">Institutional FAQ</h3>
            <p className="text-blue-100 mb-6 opacity-80">Quick answers for standard procedural queries.</p>
            <button className="bg-white text-tertiary px-6 py-2 rounded-lg font-bold text-sm hover:bg-blue-50 transition-colors">Browse Topics</button>
          </div>
          <div className="absolute -bottom-4 -right-4 opacity-10">
            <span className="material-symbols-outlined text-[96px]">help_center</span>
          </div>
        </div>
      </section>
    </>
  )
}
