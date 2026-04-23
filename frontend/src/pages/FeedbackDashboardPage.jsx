import { useState, useEffect } from 'react';
import api from '../api/client';
import TopBar from '../components/TopBar';
import Chip from '../components/ui/Chip';
import Donut from '../components/ui/Donut';
import useLayout from '../components/ui/useLayout';

function toneFor(score) {
  if (score >= 4.2) return 'pos';
  if (score >= 3.5) return 'warn';
  return 'neg';
}

export default function FeedbackDashboardPage() {
  const { openMenu, openNotifications } = useLayout();
  const [analytics, setAnalytics] = useState(null);
  const [recent, setRecent] = useState([]);
  const [weekly, setWeekly] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get('/feedback/analytics?days=30').catch(() => null),
      api.get('/feedback?limit=20').catch(() => []),
      api.get('/feedback/weekly-report').catch(() => null),
    ]).then(([a, r, w]) => {
      setAnalytics(a);
      setRecent(Array.isArray(r) ? r : []);
      setWeekly(w);
      setLoading(false);
    });
  }, []);

  const agents = analytics?.agents || [];
  const overall = analytics?.overall_avg || 0;
  const overallPct = Math.round((overall / 5) * 100);

  return (
    <>
      <TopBar crumbs={['Review', 'Feedback']} onMenuClick={openMenu} onNotificationsClick={openNotifications} />
      <div className="page wide">
        <div className="page-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>Last {analytics?.period_days || 30} days</div>
            <h1 className="page-title"><em>Feedback</em></h1>
            <p className="page-sub">
              How the agents are performing — accuracy, clarity, and helpfulness scored by brokers after each
              output. Drives the weekly RLHF reward loop.
            </p>
          </div>
        </div>

        {loading ? (
          <div className="empty"><div className="loader" /></div>
        ) : (
          <>
            <div className="grid-12">
              <div style={{ gridColumn: 'span 4' }}>
                <div className="card card-pad">
                  <div className="eyebrow" style={{ marginBottom: 14 }}>Overall score</div>
                  <div className="row" style={{ gap: 20 }}>
                    <Donut value={overallPct} size={72} stroke={7} />
                    <div>
                      <div style={{ fontFamily: 'var(--serif)', fontSize: 28, letterSpacing: '-0.01em' }}>
                        {overall.toFixed(2)}
                        <span style={{ fontSize: 14, color: 'var(--ink-3)' }}> / 5</span>
                      </div>
                      <div className="muted" style={{ fontSize: 12.5 }}>{analytics?.total_feedback || 0} responses</div>
                    </div>
                  </div>
                </div>
              </div>

              <div style={{ gridColumn: 'span 8' }}>
                <div className="card card-pad">
                  <div className="eyebrow" style={{ marginBottom: 14 }}>By agent</div>
                  {agents.length === 0 ? (
                    <div className="muted" style={{ fontSize: 13 }}>No feedback collected yet.</div>
                  ) : (
                    agents.map((a) => (
                      <div key={a.agent_type} className="between" style={{ padding: '12px 0', borderBottom: '1px dashed var(--line)' }}>
                        <div className="row" style={{ gap: 12 }}>
                          <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                            {a.agent_type}
                          </span>
                          <Chip tone={toneFor(a.combined_avg)}>{a.combined_avg.toFixed(2)}</Chip>
                        </div>
                        <div className="row" style={{ gap: 16, fontSize: 12 }}>
                          <span className="muted">Acc {a.avg_accuracy.toFixed(1)}</span>
                          <span className="muted">Clar {a.avg_clarity.toFixed(1)}</span>
                          <span className="muted">Help {a.avg_helpfulness.toFixed(1)}</span>
                          <span className="mono" style={{ color: 'var(--ink-4)' }}>{a.total_feedback} ratings</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>

            {weekly && (
              <>
                <div className="section-head"><h2>Weekly report</h2></div>
                <div className="card card-pad">
                  <div className="grid-3">
                    <div>
                      <div className="eyebrow">Best agent</div>
                      <div style={{ fontFamily: 'var(--serif)', fontSize: 22, marginTop: 6 }}>{weekly.best_agent || '—'}</div>
                    </div>
                    <div>
                      <div className="eyebrow">Worst agent</div>
                      <div style={{ fontFamily: 'var(--serif)', fontSize: 22, marginTop: 6 }}>{weekly.worst_agent || '—'}</div>
                    </div>
                    <div>
                      <div className="eyebrow">Low-score outputs</div>
                      <div style={{ fontFamily: 'var(--serif)', fontSize: 22, marginTop: 6 }}>{weekly.low_score_count || 0}</div>
                    </div>
                  </div>
                </div>
              </>
            )}

            <div className="section-head"><h2>Recent feedback</h2><div className="after">{recent.length} items</div></div>
            <div className="card" style={{ overflow: 'hidden' }}>
              {recent.length === 0 ? (
                <div className="empty">
                  <div className="empty-title">No feedback yet</div>
                  <div>Submit feedback on an agent output to populate this view.</div>
                </div>
              ) : (
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Agent</th>
                      <th>Accuracy</th>
                      <th>Clarity</th>
                      <th>Helpfulness</th>
                      <th>Comment</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recent.map((fb) => (
                      <tr key={fb.id}>
                        <td className="mono">{fb.agent_type}</td>
                        <td className="num">{fb.accuracy}</td>
                        <td className="num">{fb.clarity}</td>
                        <td className="num">{fb.helpfulness}</td>
                        <td className="muted" style={{ fontSize: 12.5, fontStyle: fb.comment ? 'italic' : 'normal' }}>
                          {fb.comment || <span style={{ fontStyle: 'normal' }}>—</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}
      </div>
    </>
  );
}
