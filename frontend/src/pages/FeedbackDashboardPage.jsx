import { useState, useEffect } from 'react'
import api from '../api/client'

const AGENT_LABELS = { compare: 'Plan Comparison', calculate: 'Cost Calculator', translate: 'Coverage Translation', appeal: 'Claims Appeal', verify: 'Network Verification' }
const AGENT_ICONS = { compare: 'compare_arrows', calculate: 'calculate', translate: 'translate', appeal: 'gavel', verify: 'verified_user' }

export default function FeedbackDashboardPage() {
  const [analytics, setAnalytics] = useState(null)
  const [weeklyReport, setWeeklyReport] = useState(null)
  const [feedbackList, setFeedbackList] = useState([])
  const [loading, setLoading] = useState(true)

  // Submit form state
  const [outputId, setOutputId] = useState('')
  const [agentType, setAgentType] = useState('compare')
  const [accuracy, setAccuracy] = useState(0)
  const [clarity, setClarity] = useState(0)
  const [helpfulness, setHelpfulness] = useState(0)
  const [comment, setComment] = useState('')
  const [submitLoading, setSubmitLoading] = useState(false)
  const [submitMsg, setSubmitMsg] = useState('')

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [a, w, f] = await Promise.all([
        api.get('/feedback/analytics?days=30').catch(() => null),
        api.get('/feedback/weekly-report').catch(() => null),
        api.get('/feedback?limit=20').catch(() => []),
      ])
      setAnalytics(a)
      setWeeklyReport(w)
      setFeedbackList(Array.isArray(f) ? f : [])
    } catch {} finally { setLoading(false) }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!outputId || accuracy === 0 || clarity === 0 || helpfulness === 0) return
    setSubmitLoading(true); setSubmitMsg('')
    try {
      await api.post('/feedback', { output_id: outputId, agent_type: agentType, accuracy, clarity, helpfulness, comment })
      setSubmitMsg('Feedback submitted!')
      setOutputId(''); setAccuracy(0); setClarity(0); setHelpfulness(0); setComment('')
      loadData()
    } catch (err) { setSubmitMsg(`Error: ${err.message}`) }
    finally { setSubmitLoading(false) }
  }

  async function triggerRewardScore() {
    try {
      const report = await api.post('/feedback/reward-score?days=30')
      setWeeklyReport(report)
    } catch {}
  }

  const agents = analytics?.agents || []
  const overallAvg = analytics?.overall_avg?.toFixed(1) || '—'
  const totalFeedback = analytics?.total_feedback || 0

  function StarRating({ value, onChange }) {
    return (
      <div className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map(i => (
          <button key={i} type="button" onClick={() => onChange(i)}
            className="transition-all hover:scale-110">
            <span className={`material-symbols-outlined text-lg ${i <= value ? 'text-secondary' : 'text-outline-variant'}`}
              style={i <= value ? { fontVariationSettings: "'FILL' 1" } : {}}>star</span>
          </button>
        ))}
      </div>
    )
  }

  return (
    <>
      {/* Hero */}
      <section className="mb-10">
        <h2 className="font-display text-4xl md:text-5xl text-primary font-bold tracking-tight mb-4">Model Feedback & RLHF Dashboard</h2>
        <p className="text-lg text-outline max-w-3xl leading-relaxed">
          Audit AI outputs, provide feedback ratings, and monitor accuracy trends across all agents. The reward model uses your feedback to improve future recommendations.
        </p>
      </section>

      <div className="grid grid-cols-12 gap-8">
        {/* Main Column */}
        <div className="col-span-12 lg:col-span-8 space-y-8">

          {/* Rating Submission */}
          <div className="bg-surface-container-lowest p-8 rounded-lg shadow-sm border border-slate-100">
            <header className="flex justify-between items-center mb-6">
              <h3 className="uppercase tracking-widest text-[11px] font-bold text-primary">Submit Feedback</h3>
              {submitMsg && <span className={`text-xs font-bold ${submitMsg.startsWith('Error') ? 'text-error' : 'text-secondary'}`}>{submitMsg}</span>}
            </header>
            <form onSubmit={handleSubmit}>
              <div className="grid grid-cols-2 gap-6 mb-6">
                <div>
                  <label className="uppercase tracking-widest text-[10px] font-bold text-outline block mb-2">Output / Session ID</label>
                  <input className="w-full bg-surface-container-high border-none border-b-2 border-outline-variant rounded-t p-3 text-sm focus:border-primary focus:ring-0"
                    placeholder="e.g. abc-123 or session ID" value={outputId} onChange={(e) => setOutputId(e.target.value)} required />
                </div>
                <div>
                  <label className="uppercase tracking-widest text-[10px] font-bold text-outline block mb-2">Agent Type</label>
                  <select className="w-full bg-surface-container-high border-none border-b-2 border-outline-variant rounded-t p-3 text-sm focus:border-primary focus:ring-0"
                    value={agentType} onChange={(e) => setAgentType(e.target.value)}>
                    {Object.entries(AGENT_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-6 mb-6">
                <div>
                  <label className="uppercase tracking-widest text-[10px] font-bold text-outline block mb-2">Accuracy</label>
                  <StarRating value={accuracy} onChange={setAccuracy} />
                </div>
                <div>
                  <label className="uppercase tracking-widest text-[10px] font-bold text-outline block mb-2">Clarity</label>
                  <StarRating value={clarity} onChange={setClarity} />
                </div>
                <div>
                  <label className="uppercase tracking-widest text-[10px] font-bold text-outline block mb-2">Helpfulness</label>
                  <StarRating value={helpfulness} onChange={setHelpfulness} />
                </div>
              </div>

              <div className="mb-6">
                <label className="uppercase tracking-widest text-[10px] font-bold text-outline block mb-2">Clinical Notes (Optional)</label>
                <textarea className="w-full bg-surface-container-high border-none border-b-2 border-outline-variant rounded-t p-3 text-sm focus:border-primary focus:ring-0 min-h-[80px]"
                  placeholder="Describe errors or improvements..." value={comment} onChange={(e) => setComment(e.target.value)} maxLength={2000}></textarea>
              </div>

              <div className="flex justify-end">
                <button type="submit" disabled={submitLoading || accuracy === 0}
                  className="bg-primary text-on-primary px-8 py-3 rounded shadow-md font-bold text-sm tracking-tight hover:bg-primary-container transition-all disabled:opacity-50">
                  {submitLoading ? 'SUBMITTING...' : 'SUBMIT FEEDBACK'}
                </button>
              </div>
            </form>
          </div>

          {/* Analytics Bento Grid */}
          <div className="grid grid-cols-2 gap-6">
            {/* Per-Agent Scores */}
            <div className="bg-surface-container-lowest p-6 rounded-lg shadow-sm border border-slate-100">
              <h3 className="uppercase tracking-widest text-[10px] font-bold text-outline mb-6">Agent Performance</h3>
              {loading ? (
                <div className="py-8 text-center"><span className="material-symbols-outlined animate-spin text-outline">progress_activity</span></div>
              ) : agents.length === 0 ? (
                <p className="text-xs text-slate-400 text-center py-8">No feedback data yet.</p>
              ) : (
                <div className="space-y-4">
                  {agents.map(a => (
                    <div key={a.agent_type} className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded bg-primary/10 flex items-center justify-center text-primary">
                        <span className="material-symbols-outlined text-sm">{AGENT_ICONS[a.agent_type] || 'smart_toy'}</span>
                      </div>
                      <div className="flex-1">
                        <div className="flex justify-between items-center mb-1">
                          <span className="text-xs font-bold">{AGENT_LABELS[a.agent_type] || a.agent_type}</span>
                          <span className={`text-xs font-bold ${a.combined_avg >= 4 ? 'text-secondary' : a.combined_avg >= 3 ? 'text-primary' : 'text-error'}`}>{a.combined_avg.toFixed(1)}</span>
                        </div>
                        <div className="h-1.5 bg-surface-container-high rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${a.combined_avg >= 4 ? 'bg-secondary' : a.combined_avg >= 3 ? 'bg-primary' : 'bg-error'}`} style={{ width: `${(a.combined_avg / 5) * 100}%` }}></div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Overall Stats */}
            <div className="bg-surface-container-lowest p-6 rounded-lg shadow-sm border border-slate-100">
              <h3 className="uppercase tracking-widest text-[10px] font-bold text-outline mb-6">Feedback Overview</h3>
              <div className="flex items-center justify-center py-4">
                <div className="w-32 h-32 rounded-full border-[16px] border-primary-container flex items-center justify-center relative">
                  <div className="absolute inset-[-16px] rounded-full border-[16px] border-secondary-container border-r-transparent border-b-transparent rotate-45"></div>
                  <div className="text-center">
                    <p className="text-xl font-bold">{totalFeedback}</p>
                    <p className="text-[8px] uppercase tracking-tighter text-outline">Total</p>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 mt-4">
                <div className="text-center">
                  <p className="text-lg font-bold text-primary">{overallAvg}</p>
                  <p className="text-[9px] uppercase tracking-widest text-outline">Avg Score</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-bold text-primary">{agents.length}</p>
                  <p className="text-[9px] uppercase tracking-widest text-outline">Agents Rated</p>
                </div>
              </div>
            </div>
          </div>

          {/* Weekly Report */}
          <div className="bg-surface-container-lowest p-8 rounded-lg shadow-sm border border-slate-100">
            <div className="flex justify-between items-end mb-8">
              <div>
                <h3 className="uppercase tracking-widest text-[10px] font-bold text-outline mb-2">Clinical Insights</h3>
                <h4 className="text-2xl font-bold text-primary">Weekly Intelligence Brief</h4>
              </div>
              <button onClick={triggerRewardScore} className="text-primary text-xs font-bold uppercase tracking-widest flex items-center gap-2 hover:underline">
                Refresh Report <span className="material-symbols-outlined text-sm">refresh</span>
              </button>
            </div>
            {!weeklyReport ? (
              <p className="text-sm text-slate-400 text-center py-8">Run reward scoring to generate the weekly report.</p>
            ) : (
              <div className="space-y-6">
                {weeklyReport.best_agent && (
                  <div className="flex gap-6 items-start group">
                    <div className="w-12 h-12 rounded bg-secondary/10 flex-shrink-0 flex items-center justify-center text-secondary">
                      <span className="material-symbols-outlined">trending_up</span>
                    </div>
                    <div>
                      <p className="text-sm font-bold text-on-surface group-hover:text-primary transition-colors">
                        Best performing agent: <span className="text-secondary">{AGENT_LABELS[weeklyReport.best_agent] || weeklyReport.best_agent}</span>
                      </p>
                      <p className="text-xs text-outline">Highest average feedback scores across accuracy, clarity, and helpfulness.</p>
                    </div>
                  </div>
                )}
                {weeklyReport.worst_agent && (
                  <div className="flex gap-6 items-start group">
                    <div className="w-12 h-12 rounded bg-error/10 flex-shrink-0 flex items-center justify-center text-error">
                      <span className="material-symbols-outlined">trending_down</span>
                    </div>
                    <div>
                      <p className="text-sm font-bold text-on-surface group-hover:text-primary transition-colors">
                        Needs improvement: <span className="text-error">{AGENT_LABELS[weeklyReport.worst_agent] || weeklyReport.worst_agent}</span>
                      </p>
                      <p className="text-xs text-outline">Lowest scoring agent — consider reviewing recent outputs and updating prompts.</p>
                    </div>
                  </div>
                )}
                <div className="flex gap-6 items-start group">
                  <div className="w-12 h-12 rounded bg-primary/10 flex-shrink-0 flex items-center justify-center text-primary">
                    <span className="material-symbols-outlined">analytics</span>
                  </div>
                  <div>
                    <p className="text-sm font-bold text-on-surface">
                      {weeklyReport.low_score_count} low-scoring outputs flagged, {weeklyReport.top_output_ids?.length || 0} high-quality examples identified for few-shot learning.
                    </p>
                    <p className="text-xs text-outline">Overall average score: {weeklyReport.overall_avg?.toFixed(1) || '—'}/5.0 across {weeklyReport.period_days} days.</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Sidebar */}
        <div className="col-span-12 lg:col-span-4 space-y-8">
          {/* Model Status */}
          <div className="bg-white/80 backdrop-blur-[12px] p-6 rounded-lg shadow-sm border border-primary/5">
            <h3 className="uppercase tracking-widest text-[10px] font-bold text-outline mb-6">System Status</h3>
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-bold text-primary">Claude Sonnet 4.6</p>
                  <p className="text-[10px] uppercase tracking-widest text-outline">Production Model</p>
                </div>
                <span className="w-3 h-3 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]"></span>
              </div>
              <div className="h-1 bg-surface-container-high rounded-full overflow-hidden">
                <div className="h-full bg-primary" style={{ width: `${Math.min((analytics?.overall_avg || 0) / 5 * 100, 100)}%` }}></div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-lg font-bold text-primary">{overallAvg}/5</p>
                  <p className="text-[9px] uppercase tracking-widest text-outline">Quality Score</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-primary">{totalFeedback}</p>
                  <p className="text-[9px] uppercase tracking-widest text-outline">Total Reviews</p>
                </div>
              </div>
            </div>
          </div>

          {/* Recent Feedback */}
          <div className="bg-surface-container-lowest p-6 rounded-lg shadow-sm border border-slate-100">
            <h3 className="uppercase tracking-widest text-[10px] font-bold text-outline mb-6">Recent Feedback</h3>
            {feedbackList.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-6">No feedback submitted yet.</p>
            ) : (
              <div className="space-y-4">
                {feedbackList.slice(0, 5).map(f => (
                  <div key={f.id} className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded bg-primary/10 flex items-center justify-center text-primary shrink-0">
                      <span className="material-symbols-outlined text-sm">{AGENT_ICONS[f.agent_type] || 'rate_review'}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-bold text-primary uppercase truncate">{AGENT_LABELS[f.agent_type] || f.agent_type}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[10px] text-outline">Acc:{f.accuracy}</span>
                        <span className="text-[10px] text-outline">Clar:{f.clarity}</span>
                        <span className="text-[10px] text-outline">Help:{f.helpfulness}</span>
                      </div>
                      {f.comment && <p className="text-[10px] text-slate-500 mt-1 truncate">{f.comment}</p>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* HITL Velocity */}
          <div className="bg-primary p-6 rounded-lg shadow-lg relative overflow-hidden">
            <div className="absolute -right-4 -bottom-4 text-white/10">
              <span className="material-symbols-outlined text-[96px]" style={{ fontVariationSettings: "'wght' 700" }}>bolt</span>
            </div>
            <h3 className="uppercase tracking-widest text-[10px] font-bold text-primary-fixed mb-6 relative z-10">HITL Velocity</h3>
            <div className="relative z-10">
              <p className="text-4xl font-extrabold text-on-primary">{totalFeedback}</p>
              <p className="text-xs text-primary-fixed-dim mt-2 font-medium uppercase tracking-widest">Total Reviews Submitted</p>
              <div className="mt-6 flex items-center gap-2 text-secondary-container">
                <span className="material-symbols-outlined text-sm">trending_up</span>
                <span className="text-[10px] font-bold uppercase tracking-widest">Active Learning Loop</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
