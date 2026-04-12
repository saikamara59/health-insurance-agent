import { useState } from 'react'
import api from '../api/client'

export default function ClaimsAppealPage() {
  const [denialText, setDenialText] = useState('')
  const [context, setContext] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit() {
    if (!denialText.trim()) return
    setLoading(true); setError(''); setResult(null)
    try {
      const data = await api.post('/appeal', { denial_text: denialText, additional_context: context })
      setResult(data)
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  const analysis = result?.denial_analysis
  const argument = result?.coverage_argument

  return (
    <>
      {/* Header */}
      <div className="mb-10">
        <div className="flex items-center gap-2 text-primary mb-2">
          <span className="material-symbols-outlined text-sm">medical_services</span>
          <span className="text-xs font-bold tracking-widest uppercase">Claims Processing</span>
        </div>
        <h2 className="text-3xl font-headline font-extrabold text-on-surface tracking-tight">Claims Appeal Workstation</h2>
        <p className="text-on-surface-variant mt-1">Paste a denial letter to generate a formal appeal with AI-powered clinical justification.</p>
      </div>

      <div className="grid grid-cols-12 gap-8">
        {/* Left: Input & Parsing */}
        <div className="col-span-12 lg:col-span-5 space-y-8">
          {/* Upload / Paste */}
          <section className="bg-surface-container-lowest p-6 rounded-xl shadow-sm">
            <h3 className="font-headline font-bold text-lg mb-4 flex items-center gap-2">
              <span className="material-symbols-outlined text-primary">upload_file</span>
              Denial Letter Input
            </h3>
            <textarea
              className="w-full bg-surface-container-low border-none rounded-xl p-4 text-sm font-body leading-relaxed focus:ring-2 focus:ring-primary/20 resize-none"
              rows={8}
              placeholder="Paste the denial letter text here...&#10;&#10;Example:&#10;Dear Member, your claim for MRI of the lumbar spine (Claim #CLM-99283) has been denied.&#10;Denial Reason: CO-50 - Not deemed medically necessary.&#10;Policy Reference: LCD L35936&#10;You have 60 days to file an appeal."
              value={denialText}
              onChange={(e) => setDenialText(e.target.value)}
            ></textarea>
            <div className="mt-4">
              <label className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-2 block">Additional Context (Optional)</label>
              <input
                className="w-full bg-surface-container-low border-none rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-primary/20"
                placeholder="e.g. Patient has documented history of chronic back pain for 2 years"
                value={context}
                onChange={(e) => setContext(e.target.value)}
              />
            </div>
            <button
              onClick={handleSubmit}
              disabled={loading || !denialText.trim()}
              className="w-full mt-6 bg-gradient-to-r from-primary to-primary-container text-white py-3 rounded-xl font-bold shadow-md hover:shadow-lg transition-all disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <><span className="material-symbols-outlined text-lg animate-spin">progress_activity</span> Analyzing Denial...</>
              ) : (
                <><span className="material-symbols-outlined text-lg">auto_awesome</span> Generate Appeal</>
              )}
            </button>
          </section>

          {/* AI Parsing Results */}
          {analysis && (
            <section className="bg-surface-container-lowest p-8 rounded-xl shadow-sm">
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-headline font-bold text-lg flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary">analytics</span>
                  AI Parsing Results
                </h3>
                <span className="px-2 py-1 bg-secondary-container text-on-secondary-container text-[10px] font-bold rounded uppercase">Analyzed</span>
              </div>
              <div className="space-y-6">
                {/* Denial Code */}
                {analysis.denial_reason_code && (
                  <div>
                    <label className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-3 block">Denial Code Detected</label>
                    <div className="bg-surface-container-low p-4 rounded-xl">
                      <div className="flex items-start gap-3">
                        <div className="mt-1 px-2 py-0.5 bg-error-container text-on-error-container text-xs font-bold rounded">{analysis.denial_reason_code}</div>
                        <p className="text-sm leading-relaxed"><span className="font-bold">{analysis.denial_reason}</span></p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Treatment */}
                <div>
                  <label className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-3 block">Treatment Denied</label>
                  <div className="bg-surface-container-low p-4 rounded-xl">
                    <p className="text-sm font-bold">{analysis.treatment_denied}</p>
                  </div>
                </div>

                {/* Context Grid */}
                <div className="grid grid-cols-2 gap-4">
                  {analysis.policy_section_cited && (
                    <div className="bg-surface-container-low p-4 rounded-xl">
                      <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Policy Cited</p>
                      <p className="text-sm font-bold">{analysis.policy_section_cited}</p>
                    </div>
                  )}
                  {analysis.appeal_deadline && (
                    <div className="bg-surface-container-low p-4 rounded-xl">
                      <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Appeal Deadline</p>
                      <p className="text-sm font-bold">{analysis.appeal_deadline}</p>
                    </div>
                  )}
                </div>
              </div>
            </section>
          )}

          {/* Coverage Argument */}
          {argument && (
            <section className="bg-surface-container-lowest p-8 rounded-xl shadow-sm">
              <h3 className="font-headline font-bold text-lg mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-primary">fact_check</span>
                Coverage Argument
              </h3>
              <div className="space-y-4">
                <div className="bg-surface-container-low p-4 rounded-xl">
                  <p className="text-[10px] font-bold text-slate-400 uppercase mb-2">CMS Rule</p>
                  <p className="text-sm leading-relaxed">{argument.cms_rule}</p>
                </div>
                {argument.common_appeal_grounds?.length > 0 && (
                  <div>
                    <p className="text-[10px] font-bold text-slate-400 uppercase mb-2">Appeal Grounds</p>
                    <div className="space-y-2">
                      {argument.common_appeal_grounds.map((g, i) => (
                        <label key={i} className="flex items-center gap-3 p-3 bg-surface-container-low rounded-xl">
                          <input type="checkbox" defaultChecked className="rounded text-primary focus:ring-primary border-outline-variant" />
                          <span className="text-sm font-medium">{g}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </section>
          )}
        </div>

        {/* Right: Appeal Letter */}
        <div className="col-span-12 lg:col-span-7">
          <section className="bg-surface-container-lowest rounded-xl shadow-lg overflow-hidden flex flex-col h-full border border-outline-variant/10">
            {/* Toolbar */}
            <div className="px-8 py-4 bg-surface-container-low border-b border-outline-variant/20 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <button className="p-2 hover:bg-white rounded-lg transition-colors"><span className="material-symbols-outlined text-slate-600">format_bold</span></button>
                <button className="p-2 hover:bg-white rounded-lg transition-colors"><span className="material-symbols-outlined text-slate-600">format_italic</span></button>
                <button className="p-2 hover:bg-white rounded-lg transition-colors"><span className="material-symbols-outlined text-slate-600">list</span></button>
                <div className="h-6 w-px bg-outline-variant mx-2"></div>
                {result && (
                  <button onClick={handleSubmit} className="flex items-center gap-2 text-xs font-bold text-primary px-3 py-1 bg-white rounded-full border border-primary/20 hover:bg-primary/5 transition-colors">
                    <span className="material-symbols-outlined text-sm">magic_button</span> REGENERATE
                  </button>
                )}
              </div>
              <div className="flex items-center gap-3">
                <button className="flex items-center gap-2 text-xs font-bold text-slate-600 hover:text-primary transition-colors">
                  <span className="material-symbols-outlined text-sm">download</span> PDF
                </button>
                <button className="flex items-center gap-2 text-xs font-bold text-slate-600 hover:text-primary transition-colors">
                  <span className="material-symbols-outlined text-sm">print</span> PRINT
                </button>
              </div>
            </div>

            {/* Document Body */}
            <div className="flex-1 p-12 bg-white overflow-y-auto min-h-[500px]">
              {error && (
                <div className="p-4 bg-error-container rounded-xl mb-6">
                  <p className="text-sm text-on-error-container">{error}</p>
                </div>
              )}

              {!result && !loading && (
                <div className="flex flex-col items-center justify-center h-full text-center py-20">
                  <span className="material-symbols-outlined text-6xl text-outline-variant mb-6">description</span>
                  <h3 className="font-headline font-bold text-xl text-on-surface-variant mb-2">Appeal Letter Preview</h3>
                  <p className="text-sm text-on-surface-variant max-w-sm">Paste a denial letter on the left and click "Generate Appeal" to create a formal appeal letter with AI-powered clinical justification.</p>
                </div>
              )}

              {loading && (
                <div className="flex flex-col items-center justify-center h-full text-center py-20">
                  <span className="material-symbols-outlined text-5xl text-primary animate-spin mb-6">progress_activity</span>
                  <h3 className="font-headline font-bold text-lg text-primary">Generating Appeal Letter...</h3>
                  <p className="text-sm text-on-surface-variant mt-2">Analyzing denial codes, researching CMS coverage rules, and drafting formal appeal.</p>
                </div>
              )}

              {result && (
                <div className="max-w-2xl mx-auto space-y-8 leading-relaxed text-on-surface">
                  <div className="text-right text-sm text-slate-500">
                    <p>{new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</p>
                    <p>Session: {result.session_id?.slice(0, 8)}</p>
                  </div>

                  <div className="bg-surface-container-low p-4 rounded-lg border-l-4 border-primary">
                    <p className="text-[11px] font-bold text-primary mb-1">SUBJECT</p>
                    <p className="font-bold text-base">
                      Formal Appeal: {analysis?.treatment_denied || 'Denied Claim'} — {analysis?.denial_reason_code || 'Review Required'}
                    </p>
                  </div>

                  <div className="whitespace-pre-wrap text-sm leading-relaxed font-body">
                    {result.appeal_letter}
                  </div>

                  {result.disclaimer && (
                    <div className="mt-8 p-4 bg-surface-container-low rounded-xl border border-outline-variant/20">
                      <p className="text-[10px] text-on-surface-variant italic">{result.disclaimer}</p>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-8 py-6 bg-surface-container-highest flex justify-between items-center">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${result ? 'bg-green-500' : 'bg-slate-300'} ${result ? 'animate-pulse' : ''}`}></span>
                <span className="text-xs font-medium text-on-surface-variant">{result ? 'AI Assistant ready for revision' : 'Awaiting denial letter input'}</span>
              </div>
              {result && (
                <div className="flex gap-4">
                  <button className="px-6 py-2 bg-white border border-outline-variant text-on-surface font-bold rounded-lg hover:bg-surface-container transition-colors">
                    Save Draft
                  </button>
                  <button className="px-8 py-2 bg-primary text-white font-bold rounded-lg shadow-md hover:bg-primary-container transition-colors flex items-center gap-2">
                    Submit Appeal <span className="material-symbols-outlined text-sm">send</span>
                  </button>
                </div>
              )}
            </div>
          </section>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-12">
        <div className="bg-white/70 backdrop-blur-[12px] p-6 rounded-xl border border-white/40 shadow-sm">
          <p className="text-[10px] font-bold text-primary uppercase tracking-widest mb-1">Monthly Success Rate</p>
          <div className="flex items-end gap-2">
            <span className="text-4xl font-headline font-extrabold text-on-surface">82.4%</span>
            <span className="text-green-600 text-xs font-bold mb-1 flex items-center"><span className="material-symbols-outlined text-sm">arrow_drop_up</span>+4.2%</span>
          </div>
        </div>
        <div className="bg-white/70 backdrop-blur-[12px] p-6 rounded-xl border border-white/40 shadow-sm">
          <p className="text-[10px] font-bold text-primary uppercase tracking-widest mb-1">Avg. Recovery Value</p>
          <div className="flex items-end gap-2">
            <span className="text-4xl font-headline font-extrabold text-on-surface">$8.4k</span>
            <span className="text-slate-500 text-xs font-bold mb-1">Per Claim</span>
          </div>
        </div>
        <div className="bg-white/70 backdrop-blur-[12px] p-6 rounded-xl border border-white/40 shadow-sm">
          <p className="text-[10px] font-bold text-primary uppercase tracking-widest mb-1">Pending Responses</p>
          <div className="flex items-end gap-2">
            <span className="text-4xl font-headline font-extrabold text-on-surface">14</span>
            <span className="text-error text-xs font-bold mb-1 flex items-center">3 Overdue</span>
          </div>
        </div>
      </div>
    </>
  )
}
