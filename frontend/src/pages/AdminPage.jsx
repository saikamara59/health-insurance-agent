import { useState, useEffect, useMemo } from 'react';
import api from '../api/client';
import TopBar from '../components/TopBar';
import Icon from '../components/ui/Icon';
import Chip from '../components/ui/Chip';
import Avatar from '../components/ui/Avatar';
import useLayout from '../components/ui/useLayout';

function sinceLabel(iso) {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 0) return 'soon';
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function isLocked(broker) {
  if (!broker.locked_until) return false;
  return new Date(broker.locked_until).getTime() > Date.now();
}

export default function AdminPage() {
  const { openMenu, openNotifications } = useLayout();
  const [brokers, setBrokers] = useState([]);
  const [audit, setAudit] = useState([]);
  const [loading, setLoading] = useState(true);
  const [unlocking, setUnlocking] = useState(null);
  const [error, setError] = useState(null);

  const [replayCaseId, setReplayCaseId] = useState('');
  const [replayLoading, setReplayLoading] = useState(false);
  const [replayResult, setReplayResult] = useState(null);
  const [replayError, setReplayError] = useState(null);

  const loadAll = () => {
    setLoading(true);
    Promise.all([
      api.get('/admin/brokers').catch((e) => { setError(e.message); return []; }),
      api.get('/admin/audit/recent').catch(() => []),
    ]).then(([b, a]) => {
      setBrokers(Array.isArray(b) ? b : []);
      setAudit(Array.isArray(a) ? a : []);
      setLoading(false);
    });
  };

  useEffect(() => { loadAll(); }, []);

  const stats = useMemo(() => {
    const locked = brokers.filter(isLocked).length;
    const admins = brokers.filter((b) => b.role === 'admin').length;
    const since = Date.now() - 24 * 3600 * 1000;
    const last24 = audit.filter((a) => new Date(a.created_at).getTime() > since).length;
    return { total: brokers.length, locked, admins, last24 };
  }, [brokers, audit]);

  const unlock = async (broker) => {
    setUnlocking(broker.id);
    try {
      await api.post(`/admin/brokers/${broker.id}/unlock`);
      loadAll();
    } catch (e) {
      setError(`Unlock failed: ${e.message}`);
    } finally {
      setUnlocking(null);
    }
  };

  const runReplay = async () => {
    setReplayLoading(true);
    setReplayError(null);
    setReplayResult(null);
    try {
      const result = await api.post('/forensics/replay', {
        mode: 'case',
        case_id: replayCaseId.trim(),
      });
      setReplayResult(result);
    } catch (e) {
      setReplayError(e.message);
    } finally {
      setReplayLoading(false);
    }
  };

  return (
    <>
      <TopBar
        crumbs={['Administration', 'Workspace']}
        onMenuClick={openMenu}
        onNotificationsClick={openNotifications}
      />
      <div className="page wide">
        <div className="page-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>Administration · Workspace</div>
            <h1 className="page-title">The <em>controls</em> behind your agency.</h1>
            <p className="page-sub">
              Manage broker access, unlock accounts that hit the rate limiter, and replay any
              agent-driven case for forensic review. Only visible to admins.
            </p>
          </div>
        </div>

        {error && (
          <div
            className="card card-pad"
            style={{ marginBottom: 24, borderColor: 'var(--neg)', color: 'var(--neg)' }}
          >
            {error}
          </div>
        )}

        <div className="card" style={{ marginBottom: 36 }}>
          <div className="stat-grid">
            <div className="stat">
              <div className="label">Team</div>
              <div className="value num">{loading ? '—' : stats.total}</div>
              <div className="delta">{stats.admins} admin · {stats.total - stats.admins} broker</div>
            </div>
            <div className="stat">
              <div className="label">Locked accounts</div>
              <div className="value num" style={{ color: stats.locked > 0 ? 'var(--warn)' : undefined }}>
                {loading ? '—' : stats.locked}
              </div>
              <div className="delta">awaiting unlock</div>
            </div>
            <div className="stat">
              <div className="label">Agent invocations (24h)</div>
              <div className="value num">{loading ? '—' : stats.last24}</div>
              <div className="delta">across {new Set(audit.map((a) => a.agent)).size || 0} agents</div>
            </div>
            <div className="stat">
              <div className="label">Audit log retention</div>
              <div className="value num">∞</div>
              <div className="delta">append-only, HIPAA-grade</div>
            </div>
          </div>
        </div>

        <div className="section-head">
          <h2>Team</h2>
          <div className="after">Brokers with access to this workspace</div>
        </div>
        <div className="card" style={{ overflow: 'hidden', marginBottom: 36 }}>
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: '32%' }}>Member</th>
                <th>Role</th>
                <th>Book</th>
                <th>Failed logins</th>
                <th>Joined</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={6} style={{ padding: 40, textAlign: 'center' }}>
                    <div className="loader" />
                  </td>
                </tr>
              )}
              {!loading && brokers.map((b) => {
                const locked = isLocked(b);
                return (
                  <tr key={b.id}>
                    <td>
                      <div className="row" style={{ gap: 12 }}>
                        <Avatar name={b.full_name || b.email} />
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontWeight: 500 }}>{b.full_name || '—'}</div>
                          <div className="sub mono">{b.email}</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <Chip tone={b.role === 'admin' ? 'accent' : ''}>{b.role}</Chip>
                      {locked && <Chip tone="warn" style={{ marginLeft: 6 }}>Locked</Chip>}
                      {!b.is_active && <Chip tone="neg" style={{ marginLeft: 6 }}>Inactive</Chip>}
                    </td>
                    <td className="num">
                      {b.client_count > 0 ? `${b.client_count} client${b.client_count === 1 ? '' : 's'}` : <span className="muted">—</span>}
                    </td>
                    <td className="num">
                      {b.failed_login_count > 0
                        ? <span style={{ color: 'var(--warn)' }}>{b.failed_login_count}</span>
                        : <span className="muted">0</span>}
                    </td>
                    <td className="muted">{sinceLabel(b.created_at)}</td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        className="btn sm"
                        onClick={() => unlock(b)}
                        disabled={unlocking === b.id || (!locked && b.failed_login_count === 0)}
                        title={locked ? 'Force-unlock account' : 'Already unlocked'}
                      >
                        {unlocking === b.id ? 'Unlocking…' : 'Unlock'}
                      </button>
                    </td>
                  </tr>
                );
              })}
              {!loading && brokers.length === 0 && (
                <tr>
                  <td colSpan={6}>
                    <div className="empty">
                      <div className="empty-title">No brokers loaded</div>
                      <div>{error ? 'Check console for details.' : 'The /admin/brokers endpoint returned an empty list.'}</div>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="section-head">
          <h2>Forensics replay</h2>
          <div className="after">Reconstruct a case timeline from the audit log</div>
        </div>
        <div className="card card-pad" style={{ marginBottom: 36 }}>
          <p className="muted" style={{ fontSize: 13.5, lineHeight: 1.6, marginBottom: 16 }}>
            Paste a <code>case_id</code> from the audit log below. The replay walks every agent invocation
            tagged to that case and joins it against PHI access events within a configurable window. The
            backend self-audits every replay query into <code>forensics_access_log</code>.
          </p>
          <div className="row" style={{ gap: 8, marginBottom: 16 }}>
            <input
              type="text"
              className="input"
              placeholder="case_id (UUID)"
              value={replayCaseId}
              onChange={(e) => setReplayCaseId(e.target.value)}
              style={{ flex: 1, fontFamily: 'var(--mono)', fontSize: 13 }}
            />
            <button
              className="btn accent"
              onClick={runReplay}
              disabled={replayLoading || !replayCaseId.trim()}
            >
              <Icon name="history" size={14} /> {replayLoading ? 'Replaying…' : 'Replay'}
            </button>
          </div>

          {replayError && (
            <div className="muted" style={{ color: 'var(--neg)', fontSize: 13 }}>
              Replay failed: {replayError}
            </div>
          )}

          {replayResult && (
            <div style={{ marginTop: 12 }}>
              <div className="row" style={{ gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
                <div>
                  <div className="eyebrow">Invocations</div>
                  <div className="num" style={{ fontSize: 22 }}>{replayResult.invocations?.length || 0}</div>
                </div>
                <div>
                  <div className="eyebrow">Integrity</div>
                  <div style={{ fontSize: 14 }}>
                    <Chip tone={replayResult.integrity?.tamper_evidence === 'clean' ? 'pos' : 'warn'} dot>
                      {replayResult.integrity?.tamper_evidence || 'unknown'}
                    </Chip>
                  </div>
                </div>
                <div>
                  <div className="eyebrow">Decisions</div>
                  <div className="num" style={{ fontSize: 22 }}>{replayResult.decision_chain?.length || 0}</div>
                </div>
              </div>
              {(replayResult.invocations || []).length === 0 ? (
                <div className="muted" style={{ fontSize: 13 }}>
                  No invocations found for this case under your tenant scope. Forensics is scoped to
                  the admin's own broker_id — to populate, log in as this admin and run a comparison.
                </div>
              ) : (
                <div className="card" style={{ background: 'var(--bg-2)' }}>
                  {replayResult.invocations.map((inv) => (
                    <div
                      key={inv.invocation_id}
                      style={{
                        padding: '12px 16px',
                        borderBottom: '1px solid var(--line)',
                        display: 'grid',
                        gridTemplateColumns: '110px 110px 1fr auto',
                        gap: 14,
                        alignItems: 'center',
                        fontSize: 13,
                      }}
                    >
                      <span className="mono muted">{sinceLabel(inv.timestamp)}</span>
                      <Chip>{inv.agent}</Chip>
                      <span className="mono" style={{ fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {inv.endpoint} · {inv.event_type}
                      </span>
                      <span className="muted mono" style={{ fontSize: 11 }}>
                        {inv.duration_ms != null ? `${inv.duration_ms}ms` : '—'}
                        {inv.phi_row_count > 0 && ` · ${inv.phi_row_count} PHI`}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="section-head">
          <h2>Audit log</h2>
          <div className="after">Most-recent agent invocations across the workspace</div>
        </div>
        <div className="card card-pad" style={{ marginBottom: 60 }}>
          {loading && <div className="loader" />}
          {!loading && audit.length === 0 && (
            <div className="muted" style={{ fontSize: 13 }}>
              No agent invocations recorded yet. Run a plan comparison or coverage translation to
              populate the log.
            </div>
          )}
          {!loading && audit.length > 0 && (
            <div>
              {audit.map((a, i) => (
                <div
                  key={a.id}
                  style={{
                    padding: '12px 0',
                    borderBottom: i < audit.length - 1 ? '1px dashed var(--line)' : 0,
                    display: 'grid',
                    gridTemplateColumns: '90px 120px 1fr auto',
                    gap: 14,
                    alignItems: 'center',
                  }}
                >
                  <span className="mono muted" style={{ fontSize: 11 }}>{sinceLabel(a.created_at)}</span>
                  <Chip tone={a.error ? 'neg' : ''}>{a.agent}</Chip>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13 }}>
                      <span style={{ fontWeight: 500 }}>{a.broker_email || 'system'}</span>
                      <span className="muted"> {a.event_type}</span>
                    </div>
                    <div className="muted mono" style={{ fontSize: 11, marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {a.endpoint}
                      {a.case_id && ` · case ${a.case_id.slice(0, 8)}`}
                    </div>
                  </div>
                  <span className="muted mono" style={{ fontSize: 11 }}>
                    {a.duration_ms != null ? `${a.duration_ms}ms` : '—'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
