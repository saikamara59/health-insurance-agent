import { useState } from 'react';
import api from '../api/client';
import TopBar from '../components/TopBar';
import Icon from '../components/ui/Icon';
import Chip from '../components/ui/Chip';
import AgentMarkdown from '../components/ui/AgentMarkdown';
import useLayout from '../components/ui/useLayout';

const SAMPLE_DOC = `SUMMARY OF BENEFITS — PRIME HMO
Member Responsibility:
  $0 Individual Deductible (In-Network)
  $5,900 Annual Out-of-Pocket Maximum

Professional Services:
  Primary Care Visit — $0 copay
  Specialist Visit — $35 copay (referral required)
  Urgent Care — $45 copay
  Emergency Room — $120 (waived if admitted)

Prescription Drugs:
  Tier 1 Preferred Generic — $0
  Tier 2 Generic — $8
  Tier 3 Preferred Brand — $40
  Tier 4 Non-Preferred Brand — $95
  Tier 5 Specialty — 33% coinsurance`;

const SUGGESTED = [
  'What is the ER copay if admitted?',
  'Does specialist care need a referral?',
  'When does the OOP maximum reset?',
  'How are Tier 5 specialty drugs covered?',
];

export default function CoverageTranslatorPage() {
  const { openMenu, openNotifications } = useLayout();
  const [doc, setDoc] = useState(SAMPLE_DOC);
  const [q, setQ] = useState('');
  const [messages, setMessages] = useState([
    { role: 'system', body: 'Coverage Translator ready. Paste a Summary of Benefits on the left and ask questions in plain English.' },
  ]);
  const [busy, setBusy] = useState(false);

  async function ask(text) {
    if (!text.trim() || !doc.trim()) return;
    const question = text.trim();
    setQ('');
    setMessages((prev) => [...prev, { role: 'user', body: question }]);
    setBusy(true);
    try {
      const res = await api.post('/translate', { document_text: doc, question });
      setMessages((prev) => [
        ...prev,
        { role: 'agent', body: res.answer, cites: res.relevant_sections || [] },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'agent', body: `Error: ${err.message}`, error: true },
      ]);
    } finally {
      setBusy(false);
    }
  }

  const exchanges = messages.filter((m) => m.role !== 'system').length;

  return (
    <>
      <TopBar
        crumbs={['Tools', 'Coverage translator']}
        onMenuClick={openMenu}
        onNotificationsClick={openNotifications}
      />
      <div className="page">
        <div className="page-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>AI-assisted · citations included</div>
            <h1 className="page-title">Make benefit<br />language <em>plain.</em></h1>
            <p className="page-sub">
              Paste any Summary of Benefits and ask questions in plain English. Every answer links back to the exact
              section it came from.
            </p>
          </div>
        </div>

        <div className="grid-12" style={{ gap: 24 }}>
          <div style={{ gridColumn: 'span 5' }}>
            <div className="section-head" style={{ marginTop: 0 }}>
              <h2>Document</h2>
              <div className="after">
                <button className="btn sm" onClick={() => setDoc(SAMPLE_DOC)}>Reset to sample</button>
              </div>
            </div>
            <div className="card">
              <textarea
                className="textarea"
                style={{
                  height: 520,
                  border: 0,
                  background: 'transparent',
                  fontFamily: 'var(--mono)',
                  fontSize: 12.5,
                }}
                value={doc}
                onChange={(e) => setDoc(e.target.value)}
                placeholder="Paste a Summary of Benefits here…"
              />
            </div>
          </div>

          <div style={{ gridColumn: 'span 7' }}>
            <div className="section-head" style={{ marginTop: 0 }}>
              <h2>Conversation</h2>
              <div className="after">{exchanges} exchange{exchanges === 1 ? '' : 's'}</div>
            </div>
            <div className="card card-pad">
              <div className="chat">
                {messages.map((m, i) =>
                  m.role === 'system' ? (
                    <div
                      key={i}
                      className="muted"
                      style={{
                        fontSize: 12.5,
                        textAlign: 'center',
                        fontStyle: 'italic',
                        padding: 12,
                        borderBottom: '1px dashed var(--line)',
                      }}
                    >
                      {m.body}
                    </div>
                  ) : (
                    <div key={i} className={`msg ${m.role}`}>
                      <div>
                        <div className="bub-label">{m.role === 'user' ? 'You asked' : 'Translator'}</div>
                        <div
                          className="bubble"
                          style={m.error ? { color: 'var(--neg)' } : undefined}
                        >
                          {m.role === 'agent'
                            ? <AgentMarkdown>{m.body}</AgentMarkdown>
                            : m.body}
                        </div>
                        {m.cites && m.cites.length > 0 && (
                          <div className="row" style={{ gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                            {m.cites.map((c, j) => (
                              <Chip key={j} tone="accent">{c}</Chip>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ),
                )}
                {busy && (
                  <div className="msg">
                    <div>
                      <div className="bub-label">Translator</div>
                      <div className="bubble agent-output">
                        <span className="loader" /> thinking…
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="row" style={{ gap: 8, marginTop: 18 }}>
                <input
                  className="input"
                  placeholder="Ask about coverage…"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') ask(q);
                  }}
                  disabled={busy}
                />
                <button className="btn accent" onClick={() => ask(q)} disabled={busy || !q.trim()}>
                  <Icon name="send" size={14} />
                </button>
              </div>

              <div className="row" style={{ gap: 6, marginTop: 14, flexWrap: 'wrap' }}>
                <span className="eyebrow" style={{ fontSize: 10 }}>Try</span>
                {SUGGESTED.map((s, i) => (
                  <button key={i} className="btn sm" onClick={() => ask(s)} disabled={busy}>{s}</button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
