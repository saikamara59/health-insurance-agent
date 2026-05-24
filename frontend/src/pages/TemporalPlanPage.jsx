import { useEffect, useState } from 'react';
import api from '../api/client';
import TopBar from '../components/TopBar';
import Icon from '../components/ui/Icon';
import Chip from '../components/ui/Chip';
import useLayout from '../components/ui/useLayout';

// ── Event-type metadata (client-side; backend returns the enum value) ────────

const EVENT_TYPE_OPTIONS = [
  { value: 'open_enrollment', label: 'Open Enrollment' },
  { value: 'medicare_aep', label: 'Medicare AEP' },
  { value: 'sep_job_loss', label: 'SEP — Job loss', isSep: true },
  { value: 'sep_marriage', label: 'SEP — Marriage', isSep: true },
  { value: 'sep_birth', label: 'SEP — Birth or adoption', isSep: true },
  { value: 'sep_move', label: 'SEP — Move', isSep: true },
  { value: 'sep_divorce', label: 'SEP — Divorce', isSep: true },
  { value: 'pa_appeal', label: 'Prior Authorization appeal', isPaAppeal: true },
];

const EVENT_LABELS = Object.fromEntries(
  EVENT_TYPE_OPTIONS.map((o) => [o.value, o.label])
);

const EVENT_SUMMARIES = {
  open_enrollment: 'ACA Open Enrollment runs Nov 1 – Jan 15. Review the broker book for plan changes, formulary shifts, and renewal flags.',
  medicare_aep: 'Medicare AEP runs Oct 15 – Dec 7. Pull ANOC letters, flag material changes, and schedule re-shop calls for affected clients.',
  sep_job_loss: '60-day Special Enrollment window starts from the loss of employer coverage. Compare Marketplace plans and document the qualifying event.',
  sep_marriage: '60-day SEP window from the marriage date. Confirm spouse coverage options and consolidate as appropriate.',
  sep_birth: '60-day SEP window from the birth or adoption date. Add the dependent and confirm pediatric network coverage.',
  sep_move: '60-day SEP from the move date. Confirm in-network providers exist in the new ZIP and re-enroll if the prior plan is unavailable.',
  sep_divorce: '60-day SEP from the divorce decree. Each party may need independent coverage; check Marketplace eligibility.',
  pa_appeal: 'Prior authorization appeals must be filed within the carrier-specific window. Gather denial letter, clinical criteria, and medical-necessity documentation.',
};

const URGENCY = {
  critical: { tone: 'neg', label: 'Critical', color: 'var(--neg)' },
  high: { tone: 'warn', label: 'High', color: 'var(--warn)' },
  medium: { tone: '', label: 'Medium', color: 'var(--ink-3)' },
  low: { tone: 'pos', label: 'Low', color: 'var(--pos)' },
};

// ── Date helpers ────────────────────────────────────────────────────────────

const todayISO = () => new Date().toISOString().slice(0, 10);

const fmtDateLong = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso + 'T12:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};

const fmtDateShort = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso + 'T12:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

const daysBetween = (a, b) => {
  const da = new Date(a + 'T12:00:00');
  const db = new Date(b + 'T12:00:00');
  return Math.round((db - da) / (1000 * 60 * 60 * 24));
};

// ── Input card ──────────────────────────────────────────────────────────────

function InputCard({ onSubmit, loading }) {
  const [mode, setMode] = useState('structured');
  const [eventType, setEventType] = useState('sep_job_loss');
  const [triggerDate, setTriggerDate] = useState(todayISO());
  const [planType, setPlanType] = useState('PPO');
  const [text, setText] = useState('');

  const selectedOption = EVENT_TYPE_OPTIONS.find((o) => o.value === eventType);
  const needsPlanType = !!selectedOption?.isPaAppeal;

  const submit = () => {
    if (loading) return;
    if (mode === 'freetext') {
      if (!text.trim()) return;
      onSubmit({ description: text.trim() });
    } else {
      const event = { event_type: eventType, trigger_date: triggerDate };
      if (needsPlanType) event.plan_type = planType;
      onSubmit({ event });
    }
  };

  return (
    <div className="card card-pad" style={{ padding: 28, marginBottom: 28 }}>
      <div className="between" style={{ marginBottom: 18 }}>
        <div className="eyebrow">Plan a temporal event</div>
        <div className="row" style={{ gap: 4 }}>
          <button
            className={`btn sm ${mode === 'structured' ? 'primary' : 'ghost'}`}
            onClick={() => setMode('structured')}
            type="button"
          >
            Structured
          </button>
          <button
            className={`btn sm ${mode === 'freetext' ? 'primary' : 'ghost'}`}
            onClick={() => setMode('freetext')}
            type="button"
          >
            Free-text
          </button>
        </div>
      </div>

      {mode === 'structured' ? (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: needsPlanType ? '1.4fr 1fr 1fr auto' : '1.4fr 1fr auto',
            gap: 16,
            alignItems: 'end',
          }}
        >
          <div className="field">
            <label className="field-label">Event type</label>
            <select className="select" value={eventType} onChange={(e) => setEventType(e.target.value)}>
              {EVENT_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label className="field-label">Trigger date</label>
            <input
              className="input mono"
              type="date"
              value={triggerDate}
              onChange={(e) => setTriggerDate(e.target.value)}
            />
          </div>
          {needsPlanType && (
            <div className="field">
              <label className="field-label">Plan type</label>
              <select className="select" value={planType} onChange={(e) => setPlanType(e.target.value)}>
                <option value="HMO">HMO (60d window)</option>
                <option value="PPO">PPO (180d window)</option>
                <option value="EPO">EPO (120d default)</option>
                <option value="POS">POS (120d default)</option>
                <option value="MA">Medicare Advantage (60d window)</option>
              </select>
            </div>
          )}
          <button
            className="btn accent lg"
            onClick={submit}
            disabled={loading}
            style={{ height: 38, padding: '0 18px' }}
            type="button"
          >
            {loading ? 'Generating…' : <>Generate plan <Icon name="arrow_r" size={14} /></>}
          </button>
        </div>
      ) : (
        <div className="field">
          <label className="field-label">Describe what just happened</label>
          <textarea
            className="textarea"
            rows={3}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g. My client lost their job two weeks ago and needs to enroll in a Marketplace plan."
          />
          <div className="row" style={{ justifyContent: 'flex-end', marginTop: 12, gap: 8 }}>
            <span className="muted" style={{ fontSize: 12 }}>
              The agent will infer the event type and trigger date.
            </span>
            <button className="btn accent" onClick={submit} disabled={loading || !text.trim()} type="button">
              {loading ? 'Generating…' : <>Generate plan <Icon name="arrow_r" size={14} /></>}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Days-remaining big number ───────────────────────────────────────────────

function DaysRemaining({ deadline, daysRemaining, urgency }) {
  const u = URGENCY[urgency] || URGENCY.low;
  const isPast = daysRemaining < 0;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 8 }}>
      <div className="eyebrow">{isPast ? 'Days overdue' : 'Days remaining'}</div>
      <div className="row" style={{ alignItems: 'baseline', gap: 12 }}>
        <div
          className="serif"
          style={{ fontSize: 96, lineHeight: 0.9, letterSpacing: '-0.03em', color: u.color }}
        >
          {Math.abs(daysRemaining)}
        </div>
        <div className="muted" style={{ fontSize: 14, paddingBottom: 8 }}>
          {isPast ? 'past ' : 'until '}
          <span className="mono">{fmtDateLong(deadline)}</span>
        </div>
      </div>
    </div>
  );
}

// ── Horizontal timeline ─────────────────────────────────────────────────────

function TimelineMarker({ pct, label, date, align, tone }) {
  const offset = align === 'right' ? 'translateX(-100%)' : align === 'center' ? 'translateX(-50%)' : 'translateX(0)';
  const color = tone === 'accent' ? 'var(--accent)' : tone === 'ink' ? 'var(--ink)' : 'var(--ink-3)';
  return (
    <>
      <div
        style={{
          position: 'absolute', left: `${pct}%`, top: -6, height: 16, width: 2,
          background: color, marginLeft: -1, zIndex: 2,
        }}
      />
      <div
        style={{
          position: 'absolute', left: `${pct}%`, bottom: 'calc(100% + 10px)',
          transform: offset, whiteSpace: 'nowrap',
        }}
      >
        <div className="eyebrow" style={{ color, fontSize: 9.5 }}>{label}</div>
      </div>
      <div
        style={{
          position: 'absolute', left: `${pct}%`, top: 'calc(100% + 12px)',
          transform: offset, whiteSpace: 'nowrap',
        }}
      >
        <div className="mono" style={{ fontSize: 11, color }}>{fmtDateShort(date)}</div>
      </div>
    </>
  );
}

function Timeline({ triggerDate, deadline, actions, today }) {
  const total = Math.max(1, daysBetween(triggerDate, deadline));
  const todayPct = Math.max(0, Math.min(100, (daysBetween(triggerDate, today) / total) * 100));
  const actionPositions = actions.map((a) => ({
    ...a,
    pct: Math.max(0, Math.min(100, (daysBetween(triggerDate, a.target_date) / total) * 100)),
  }));

  return (
    <div style={{ marginTop: 28 }}>
      <div className="between" style={{ marginBottom: 18 }}>
        <div className="eyebrow">Timeline</div>
        <div className="muted mono" style={{ fontSize: 11 }}>
          {total} days · today is {fmtDateShort(today)}
        </div>
      </div>
      <div style={{ position: 'relative', padding: '40px 0 50px' }}>
        <div style={{ position: 'relative', height: 4, background: 'var(--line)', borderRadius: 2 }}>
          <div
            style={{
              position: 'absolute', left: 0, top: 0, bottom: 0,
              width: `${todayPct}%`, background: 'var(--ink-3)', borderRadius: 2,
            }}
          />
          <TimelineMarker pct={0} label="Trigger" date={triggerDate} align="left" tone="muted" />
          <TimelineMarker pct={todayPct} label="Today" date={today} align="center" tone="ink" />
          <TimelineMarker pct={100} label="Deadline" date={deadline} align="right" tone="accent" />
          {actionPositions.map((a) => {
            const past = daysBetween(today, a.target_date) < 0;
            return (
              <div
                key={a.step}
                title={`#${a.step} · ${fmtDateShort(a.target_date)}`}
                style={{
                  position: 'absolute', left: `${a.pct}%`, top: -4,
                  width: 12, height: 12, marginLeft: -6, borderRadius: '50%',
                  background: past ? 'var(--ink-4)' : 'var(--card)',
                  border: `2px solid ${past ? 'var(--ink-4)' : 'var(--accent)'}`,
                  zIndex: 1,
                }}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Action list with local-only completion ─────────────────────────────────

function ActionList({ actions, today }) {
  const [done, setDone] = useState({});
  const toggle = (step) => setDone((d) => ({ ...d, [step]: !d[step] }));
  const completedCount = Object.values(done).filter(Boolean).length;

  return (
    <div style={{ marginTop: 36 }}>
      <div className="between" style={{ marginBottom: 14 }}>
        <div className="row" style={{ gap: 12, alignItems: 'baseline' }}>
          <h2 style={{ fontFamily: 'var(--serif)', fontSize: 24, letterSpacing: '-0.01em' }}>Action plan</h2>
          <span className="muted" style={{ fontSize: 13 }}>
            {completedCount} of {actions.length} done
          </span>
        </div>
      </div>
      <div className="card">
        {actions.map((a, i) => {
          const isDone = !!done[a.step];
          const daysOut = daysBetween(today, a.target_date);
          const overdue = daysOut < 0 && !isDone;
          return (
            <div
              key={a.step}
              onClick={() => toggle(a.step)}
              style={{
                display: 'grid',
                gridTemplateColumns: '24px 28px 1fr auto auto',
                gap: 16,
                alignItems: 'center',
                padding: '16px 22px',
                borderBottom: i < actions.length - 1 ? '1px solid var(--line)' : 0,
                cursor: 'pointer',
                opacity: isDone ? 0.5 : 1,
                transition: 'opacity 200ms',
              }}
            >
              <div
                style={{
                  width: 18, height: 18, borderRadius: 4,
                  border: `1.5px solid ${isDone ? 'var(--accent)' : 'var(--line-2)'}`,
                  background: isDone ? 'var(--accent)' : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#fff', flex: '0 0 auto',
                }}
              >
                {isDone && <Icon name="check" size={12} />}
              </div>
              <span className="mono muted" style={{ fontSize: 12 }}>
                {String(a.step).padStart(2, '0')}
              </span>
              <div style={{ minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 14,
                    textDecoration: isDone ? 'line-through' : 'none',
                    textDecorationThickness: '1px',
                    textDecorationColor: 'var(--ink-3)',
                  }}
                >
                  {a.description}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div className="mono" style={{ fontSize: 12.5 }}>{fmtDateShort(a.target_date)}</div>
                <div
                  className="mono"
                  style={{
                    fontSize: 11,
                    color: overdue ? 'var(--neg)' : daysOut <= 3 ? 'var(--warn)' : 'var(--ink-4)',
                    marginTop: 2,
                  }}
                >
                  {overdue ? `${Math.abs(daysOut)}d overdue` : daysOut === 0 ? 'today' : `in ${daysOut}d`}
                </div>
              </div>
              <Icon name="chev_r" size={14} className="ink-4" />
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Plan result wrapper ────────────────────────────────────────────────────

function PlanResult({ plan, today }) {
  const u = URGENCY[plan.urgency] || URGENCY.low;
  const label = EVENT_LABELS[plan.event_type] || plan.event_type;
  const summary = EVENT_SUMMARIES[plan.event_type] || '';
  return (
    <div>
      <div className="card card-pad" style={{ padding: 32, marginBottom: 28 }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 32, flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 360px', minWidth: 0 }}>
            <div className="row" style={{ gap: 10, marginBottom: 12 }}>
              <Chip tone={u.tone} dot>{u.label} urgency</Chip>
              <Chip>{plan.event_type}</Chip>
            </div>
            <h2
              style={{
                fontFamily: 'var(--serif)', fontSize: 32, letterSpacing: '-0.015em',
                lineHeight: 1.15, marginBottom: 12,
              }}
            >
              {label}
            </h2>
            <p className="muted" style={{ maxWidth: 560, fontSize: 14, lineHeight: 1.55 }}>{summary}</p>
          </div>
          <DaysRemaining
            deadline={plan.deadline}
            daysRemaining={plan.days_remaining}
            urgency={plan.urgency}
          />
        </div>
        <Timeline
          triggerDate={plan.trigger_date}
          deadline={plan.deadline}
          actions={plan.actions}
          today={today}
        />
      </div>
      <ActionList actions={plan.actions} today={today} />
    </div>
  );
}

// ── Loading + error states ─────────────────────────────────────────────────

function LoadingState() {
  return (
    <div className="card card-pad" style={{ padding: 48, textAlign: 'center' }}>
      <div style={{ display: 'inline-flex', alignItems: 'center', gap: 12, color: 'var(--ink-3)', fontSize: 14 }}>
        <Icon name="spark" size={16} />
        <span>Generating action plan…</span>
      </div>
      <div
        style={{
          marginTop: 18, height: 2, width: 200, marginLeft: 'auto', marginRight: 'auto',
          background: 'var(--line)', borderRadius: 1, overflow: 'hidden', position: 'relative',
        }}
      >
        <div
          style={{
            position: 'absolute', top: 0, bottom: 0, width: '40%',
            background: 'var(--accent)', animation: 'tplLoadbar 1.2s ease-in-out infinite',
          }}
        />
      </div>
      <style>{`@keyframes tplLoadbar { 0% { left: -40%; } 100% { left: 100%; } }`}</style>
    </div>
  );
}

function ErrorState({ msg, onRetry }) {
  return (
    <div className="card card-pad" style={{ padding: 28, borderColor: 'var(--neg)' }}>
      <div className="row" style={{ gap: 12, alignItems: 'flex-start' }}>
        <Icon name="x" size={18} style={{ color: 'var(--neg)', marginTop: 2 }} />
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 500, color: 'var(--neg)' }}>Couldn't generate plan</div>
          <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>{msg}</div>
        </div>
        {onRetry && (
          <button className="btn sm" onClick={onRetry} type="button">Retry</button>
        )}
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

const DEMO_PAYLOADS = {
  sep: {
    event: { event_type: 'sep_job_loss', trigger_date: todayISO() },
  },
  oe: {
    event: { event_type: 'open_enrollment', trigger_date: todayISO() },
  },
  pa: {
    event: { event_type: 'pa_appeal', trigger_date: todayISO(), plan_type: 'PPO' },
  },
};

export default function TemporalPlanPage() {
  const { openMenu, openNotifications } = useLayout();
  const [state, setState] = useState({ status: 'idle', plan: null, error: null, lastPayload: null });

  const generate = async (payload) => {
    setState({ status: 'loading', plan: null, error: null, lastPayload: payload });
    try {
      const plan = await api.post('/temporal/plan', payload);
      setState({ status: 'ok', plan, error: null, lastPayload: payload });
    } catch (err) {
      setState({
        status: 'error',
        plan: null,
        error: err?.message || 'Unknown error from /temporal/plan',
        lastPayload: payload,
      });
    }
  };

  // Pre-seed with the SEP demo on first load so the page isn't empty.
  useEffect(() => { generate(DEMO_PAYLOADS.sep); /* eslint-disable-line react-hooks/exhaustive-deps */ }, []);

  const today = state.plan?.today || todayISO();

  return (
    <>
      <TopBar
        crumbs={['Tools', 'Plan']}
        onMenuClick={openMenu}
        onNotificationsClick={openNotifications}
      />
      <div className="page">
        <div className="page-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>Temporal Plan Agent</div>
            <h1 className="page-title">
              Turn a deadline into a <em>plan.</em>
            </h1>
            <p className="page-sub">
              Describe what just happened — a life event, a denial, an enrollment window —
              and the agent returns an ordered action list, anchored to the real dates.
            </p>
          </div>
          <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
            <span className="eyebrow" style={{ marginRight: 8 }}>Demo</span>
            <button className="btn sm" type="button" onClick={() => generate(DEMO_PAYLOADS.sep)}>SEP</button>
            <button className="btn sm" type="button" onClick={() => generate(DEMO_PAYLOADS.oe)}>Open Enroll.</button>
            <button className="btn sm" type="button" onClick={() => generate(DEMO_PAYLOADS.pa)}>PA appeal</button>
          </div>
        </div>

        <InputCard onSubmit={generate} loading={state.status === 'loading'} />

        {state.status === 'loading' && <LoadingState />}
        {state.status === 'error' && (
          <ErrorState
            msg={state.error}
            onRetry={state.lastPayload ? () => generate(state.lastPayload) : null}
          />
        )}
        {state.status === 'ok' && state.plan && <PlanResult plan={state.plan} today={today} />}
      </div>
    </>
  );
}
