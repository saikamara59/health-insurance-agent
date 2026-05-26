import { useState } from 'react';
import api from '../api/client';
import TopBar from '../components/TopBar';
import Icon from '../components/ui/Icon';
import Chip from '../components/ui/Chip';
import AgentMarkdown from '../components/ui/AgentMarkdown';
import useLayout from '../components/ui/useLayout';

const SAMPLE = `This letter is to inform you that your claim for MRI of the right shoulder
performed on 03/14/2026 has been denied.

Reason for denial: Services not medically necessary.
Policy section: Section 4.2(b) — Diagnostic Imaging.
Denial date: 03/28/2026.
You have 60 days to appeal this decision.`;

export default function ClaimsAppealPage() {
  const { openMenu, openNotifications } = useLayout();
  const [denialText, setDenialText] = useState('');
  const [context, setContext] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  async function run() {
    if (!denialText.trim()) return;
    setError('');
    setRunning(true);
    try {
      const res = await api.post('/appeal', {
        denial_text: denialText,
        additional_context: context,
      });
      setResult(res);
    } catch (err) {
      setError(err.message || 'Appeal generation failed');
    } finally {
      setRunning(false);
    }
  }

  function copyLetter() {
    if (!result?.appeal_letter) return;
    navigator.clipboard?.writeText(result.appeal_letter);
  }

  return (
    <>
      <TopBar crumbs={['Tools', 'Claim appeals']} onMenuClick={openMenu} onNotificationsClick={openNotifications} />
      <div className="page wide">
        <div className="page-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>Denial analysis · letter drafting</div>
            <h1 className="page-title">Turn a denial into<br /><em>an appeal.</em></h1>
            <p className="page-sub">
              Paste the denial letter. HealthFlow extracts the reason code, policy citation, and deadline, surfaces
              relevant CMS guidance, and drafts a formal appeal letter you can edit.
            </p>
          </div>
        </div>

        <div className="grid-12" style={{ gap: 24 }}>
          <div style={{ gridColumn: 'span 5' }}>
            <div className="section-head" style={{ marginTop: 0 }}>
              <h2>Denial letter</h2>
              <div className="after"><button className="btn sm" onClick={() => setDenialText(SAMPLE)}>Use sample</button></div>
            </div>
            <div className="card">
              <textarea
                className="textarea"
                style={{ height: 340, border: 0, background: 'transparent', fontFamily: 'var(--mono)', fontSize: 12.5 }}
                value={denialText}
                onChange={(e) => setDenialText(e.target.value)}
                placeholder="Paste the denial letter text…"
              />
            </div>

            <div className="section-head"><h2>Additional context</h2><div className="after">optional</div></div>
            <div className="card">
              <textarea
                className="textarea"
                style={{ height: 140, border: 0, background: 'transparent', fontSize: 13 }}
                value={context}
                onChange={(e) => setContext(e.target.value)}
                placeholder="Anything the reviewer should know — e.g. referring physician's notes, symptom history, prior failed treatments."
              />
            </div>

            {error && <div className="notice" style={{ marginTop: 16, color: 'var(--neg)', borderColor: 'var(--neg)' }}>{error}</div>}

            <div className="row" style={{ justifyContent: 'flex-end', marginTop: 20 }}>
              <button className="btn accent" onClick={run} disabled={running || !denialText.trim()}>
                {running ? <><span className="loader" /> Drafting…</> : <><Icon name="appeal" size={14} /> Analyze &amp; draft</>}
              </button>
            </div>
          </div>

          <div style={{ gridColumn: 'span 7' }}>
            {!result && !running && (
              <div className="card card-pad" style={{ padding: 40, textAlign: 'center' }}>
                <div className="placeholder-img" style={{ height: 240, marginBottom: 20 }}>Appeal output</div>
                <div className="muted" style={{ maxWidth: 440, margin: '0 auto' }}>
                  The denial analysis, CMS grounds, and drafted letter will appear here once you run analysis.
                </div>
              </div>
            )}

            {running && <div className="card card-pad" style={{ textAlign: 'center', padding: 60 }}><div className="loader" /></div>}

            {result && (
              <>
                <div className="section-head" style={{ marginTop: 0 }}>
                  <h2>Denial analysis</h2>
                </div>
                <div className="card card-pad">
                  <div className="kv-grid">
                    <div className="kv"><span className="k">Reason code</span><span className="v">{result.denial_analysis.denial_reason_code || 'Unknown'}</span></div>
                    <div className="kv"><span className="k">Treatment denied</span><span className="v">{result.denial_analysis.treatment_denied}</span></div>
                    <div className="kv"><span className="k">Appeal deadline</span><span className="v">{result.denial_analysis.appeal_deadline || '—'}</span></div>
                    <div className="kv"><span className="k">Policy cited</span><span className="v">{result.denial_analysis.policy_section_cited || '—'}</span></div>
                    <div className="kv"><span className="k">Denial date</span><span className="v">{result.denial_analysis.denial_date || '—'}</span></div>
                  </div>
                  <div className="divider dashed" style={{ margin: '20px 0' }} />
                  <div className="eyebrow" style={{ marginBottom: 8 }}>Stated reason</div>
                  <div style={{ fontSize: 13.5, color: 'var(--ink-2)' }}>{result.denial_analysis.denial_reason}</div>
                </div>

                <div className="section-head"><h2>Coverage grounds</h2></div>
                <div className="card card-pad">
                  <div className="eyebrow" style={{ marginBottom: 8 }}>CMS rule</div>
                  <div style={{ fontSize: 14, fontFamily: 'var(--serif)', fontStyle: 'italic', color: 'var(--ink-2)' }}>
                    {result.coverage_argument.cms_rule}
                  </div>
                  {result.coverage_argument.common_appeal_grounds?.length > 0 && (
                    <>
                      <div className="divider dashed" style={{ margin: '20px 0' }} />
                      <div className="eyebrow" style={{ marginBottom: 10 }}>Appeal grounds</div>
                      <div className="col" style={{ gap: 8 }}>
                        {result.coverage_argument.common_appeal_grounds.map((g, i) => (
                          <div key={i} className="row" style={{ gap: 10, fontSize: 13 }}>
                            <Icon name="check" size={14} style={{ color: 'var(--pos)' }} />
                            <span>{g}</span>
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                  {result.coverage_argument.success_precedents?.length > 0 && (
                    <>
                      <div className="divider dashed" style={{ margin: '20px 0' }} />
                      <div className="eyebrow" style={{ marginBottom: 10 }}>Success precedents</div>
                      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
                        {result.coverage_argument.success_precedents.map((p, i) => (
                          <Chip key={i} tone="accent">{p}</Chip>
                        ))}
                      </div>
                    </>
                  )}
                </div>

                <div className="section-head">
                  <h2>Drafted appeal letter</h2>
                  <div className="after">
                    <button className="btn sm" onClick={copyLetter}>
                      <Icon name="download" size={12} /> Copy
                    </button>
                  </div>
                </div>
                <div className="card" style={{ padding: 24 }}>
                  <AgentMarkdown style={{ fontSize: 14.5 }}>
                    {result.appeal_letter}
                  </AgentMarkdown>
                </div>

                {result.disclaimer && <div className="notice" style={{ marginTop: 20 }}>{result.disclaimer}</div>}
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
