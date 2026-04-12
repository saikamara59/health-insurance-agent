import { useState } from 'react'
import api from '../api/client'

const SUGGESTED = [
  { icon: 'emergency', title: 'ER Triage', q: 'What is the ER copay if admitted vs released?' },
  { icon: 'medication', title: 'Prescription Tiers', q: 'What are the drug coverage tiers and copays?' },
  { icon: 'family_restroom', title: 'Family Cap', q: 'When does the family out-of-pocket maximum trigger?' },
  { icon: 'stethoscope', title: 'Specialist Referral', q: 'Does this plan require specialist referrals?' },
]

export default function CoverageTranslatorPage() {
  const [docText, setDocText] = useState('')
  const [question, setQuestion] = useState('')
  const [followUp, setFollowUp] = useState('')
  const [responses, setResponses] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function ask(q) {
    if (!docText.trim() || !q.trim()) return
    setLoading(true); setError('')
    try {
      const data = await api.post('/translate', { document_text: docText, question: q })
      setResponses(prev => [...prev, { question: q, answer: data.answer, sections: data.relevant_sections, disclaimer: data.disclaimer }])
      setQuestion('')
      setFollowUp('')
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  return (
    <>
      <header className="mb-12">
        <h1 className="font-display text-4xl text-primary font-bold mb-2">Coverage Translator</h1>
        <p className="text-on-surface-variant max-w-2xl">Decode complex Summary of Benefits documents into clear, clinical insights using AI translation.</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left: Document Input */}
        <section className="lg:col-span-5 space-y-6">
          <div className="bg-surface-container-lowest p-6 rounded shadow-sm border border-slate-100">
            <div className="flex items-center justify-between mb-4">
              <label className="uppercase tracking-widest text-[11px] font-bold text-slate-500">SoB Document Text</label>
              <span className="text-[10px] text-blue-900 font-bold uppercase tracking-widest flex items-center gap-1">
                <span className="material-symbols-outlined text-[14px]">auto_awesome</span> AI Ready
              </span>
            </div>
            <textarea
              className="w-full h-[500px] p-4 bg-surface-container-high rounded border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-sm font-body leading-relaxed resize-none"
              placeholder={"Paste the Summary of Benefits (SoB) content here...\n\nExample:\nMember Responsibility:\n$2,500 Individual / $5,000 Family (In-Network)\n\nProfessional Services:\nOffice Visits: $25 copay per visit\nSpecialist Visits: $50 copay per visit"}
              value={docText}
              onChange={(e) => setDocText(e.target.value)}
            ></textarea>
          </div>
        </section>

        {/* Right: Q&A */}
        <section className="lg:col-span-7 space-y-8">
          {/* Question Input */}
          <div className="bg-white/80 backdrop-blur-[12px] p-8 rounded-xl shadow-sm border border-slate-100">
            <label className="block uppercase tracking-widest text-[11px] font-bold text-slate-500 mb-4">Inquiry Portal</label>
            <div className="relative mb-6">
              <input
                className="w-full py-4 px-6 bg-surface-container-low rounded border-b-2 border-outline-variant focus:border-primary focus:ring-0 text-lg font-headline font-medium pr-48"
                placeholder="e.g., How much will a knee MRI cost in-network?"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); ask(question) } }}
              />
              <button
                onClick={() => ask(question)}
                disabled={loading || !docText.trim() || !question.trim()}
                className="absolute right-3 top-3 bg-primary text-on-primary px-6 py-2 rounded font-headline font-bold text-sm shadow-md hover:bg-primary-container transition-all disabled:opacity-50 flex items-center gap-2"
              >
                {loading ? 'Analyzing...' : 'Ask About Coverage'}
                <span className="material-symbols-outlined">send</span>
              </button>
            </div>

            {error && <div className="p-4 bg-error-container rounded mb-4"><p className="text-sm text-on-error-container">{error}</p></div>}

            {/* Responses */}
            <div className="space-y-6">
              {responses.length === 0 && !loading && (
                <div className="text-center py-12">
                  <span className="material-symbols-outlined text-5xl text-slate-200 mb-4">translate</span>
                  <p className="text-sm text-slate-400">Paste a document and ask a question to get started.</p>
                </div>
              )}

              {responses.map((r, i) => (
                <div key={i} className="bg-surface-container-lowest border-l-4 border-primary p-6 rounded shadow-sm">
                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 rounded bg-primary-container flex items-center justify-center flex-shrink-0">
                      <span className="material-symbols-outlined text-blue-200">robot_2</span>
                    </div>
                    <div className="flex-1">
                      <p className="text-xs text-slate-400 mb-2 uppercase tracking-widest font-bold">{r.question}</p>
                      <h3 className="font-headline font-bold text-primary mb-2">Translation Analysis</h3>
                      <div className="text-on-surface leading-relaxed whitespace-pre-wrap text-sm mb-4">{r.answer}</div>

                      {r.sections?.length > 0 && (
                        <div className="bg-secondary/5 p-4 rounded border border-secondary/10">
                          <p className="text-xs uppercase tracking-widest font-bold text-secondary mb-2 flex items-center gap-2">
                            <span className="material-symbols-outlined text-[14px]">format_quote</span> Relevant Sections
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {r.sections.map((s, j) => (
                              <span key={j} className="text-xs bg-secondary/10 text-secondary px-2 py-1 rounded font-medium">{s}</span>
                            ))}
                          </div>
                        </div>
                      )}

                      {r.disclaimer && <p className="text-[10px] text-slate-400 italic mt-3">{r.disclaimer}</p>}
                    </div>
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex items-center gap-3 p-6">
                  <span className="material-symbols-outlined text-primary animate-spin">progress_activity</span>
                  <p className="text-sm text-slate-500">Analyzing document and generating response...</p>
                </div>
              )}
            </div>

            {/* Follow-up Input */}
            {responses.length > 0 && (
              <div className="flex items-center gap-3 mt-8">
                <input
                  className="flex-1 py-3 px-4 bg-surface-container-highest/50 rounded-full border-none focus:ring-2 focus:ring-primary/20 text-sm"
                  placeholder="Ask a follow-up question..."
                  value={followUp}
                  onChange={(e) => setFollowUp(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); ask(followUp) } }}
                />
                <button onClick={() => ask(followUp)} disabled={loading || !followUp.trim()}
                  className="w-10 h-10 flex items-center justify-center rounded-full bg-primary text-white hover:bg-primary-container transition-colors disabled:opacity-50">
                  <span className="material-symbols-outlined">send</span>
                </button>
              </div>
            )}
          </div>

          {/* Suggested Queries */}
          <div className="grid grid-cols-2 gap-4">
            {SUGGESTED.map((s) => (
              <div key={s.title}
                onClick={() => { setQuestion(s.q); if (docText.trim()) ask(s.q) }}
                className="p-4 bg-surface-container-low rounded border border-slate-100 hover:border-primary/30 transition-all cursor-pointer group">
                <span className="material-symbols-outlined text-primary mb-2">{s.icon}</span>
                <h4 className="font-headline font-bold text-xs uppercase tracking-widest mb-1 group-hover:text-primary">{s.title}</h4>
                <p className="text-[11px] text-on-surface-variant">{s.q}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </>
  )
}
