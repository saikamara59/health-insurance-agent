import { useState, useEffect } from 'react';
import api from '../api/client';
import TopBar from '../components/TopBar';
import Sparkline from '../components/ui/Sparkline';
import useLayout from '../components/ui/useLayout';

export default function AnalyticsPage() {
  const { openMenu, openNotifications } = useLayout();
  const [clients, setClients] = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get('/clients').catch(() => []),
      api.get('/history?limit=200').catch(() => []),
    ]).then(([c, h]) => {
      setClients(Array.isArray(c) ? c : []);
      setHistory(Array.isArray(h) ? h : []);
      setLoading(false);
    });
  }, []);

  const total = clients.length;
  const byIncome = clients.reduce((acc, c) => {
    const k = (c.income_level || 'unknown').toLowerCase();
    acc[k] = (acc[k] || 0) + 1;
    return acc;
  }, {});
  const byAgeGroup = clients.reduce(
    (acc, c) => {
      const a = c.age || 0;
      if (a < 65) acc.under65 += 1;
      else if (a < 75) acc.a65to74 += 1;
      else acc.a75plus += 1;
      return acc;
    },
    { under65: 0, a65to74: 0, a75plus: 0 },
  );
  const byAction = history.reduce((acc, h) => {
    acc[h.action_type] = (acc[h.action_type] || 0) + 1;
    return acc;
  }, {});

  const avgRx = total ? clients.reduce((s, c) => s + (c.prescriptions?.length || 0), 0) / total : 0;
  const avgProviders = total ? clients.reduce((s, c) => s + (c.doctors?.length || 0), 0) / total : 0;

  // Sort by creation date for a growth sparkline
  const sorted = [...clients].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  const growth = sorted.map((_, i) => i + 1);

  // Barchart helper
  function Bar({ label, value, max, tone = 'accent' }) {
    const pct = max > 0 ? Math.max(2, (value / max) * 100) : 2;
    return (
      <div className="cbar-row">
        <div style={{ fontSize: 13 }}>{label}</div>
        <div className="cbar-track">
          <div className="cbar-fill" style={{ width: `${pct}%`, background: tone === 'warn' ? 'var(--warn)' : tone === 'pos' ? 'var(--pos)' : 'var(--accent)' }} />
        </div>
        <div className="num mono" style={{ fontSize: 13, textAlign: 'right' }}>{value}</div>
      </div>
    );
  }

  const incomeMax = Math.max(byIncome.low || 0, byIncome.medium || 0, byIncome.high || 0, 1);
  const ageMax = Math.max(byAgeGroup.under65, byAgeGroup.a65to74, byAgeGroup.a75plus, 1);
  const actionMax = Math.max(...Object.values(byAction), 1);

  return (
    <>
      <TopBar crumbs={['Review', 'Analytics']} onMenuClick={openMenu} onNotificationsClick={openNotifications} />
      <div className="page wide">
        <div className="page-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>Book-level view</div>
            <h1 className="page-title"><em>Analytics</em></h1>
            <p className="page-sub">
              Trends across your entire book — income mix, age distribution, and tool use.
            </p>
          </div>
        </div>

        <div className="card">
          <div className="stat-grid">
            <div className="stat">
              <div className="label">Total clients</div>
              <div className="between" style={{ alignItems: 'flex-end' }}>
                <div className="value num">{loading ? '—' : total}</div>
                {growth.length > 1 && <Sparkline data={growth} w={70} h={26} />}
              </div>
              <div className="delta">over all time</div>
            </div>
            <div className="stat">
              <div className="label">Avg Rx / client</div>
              <div className="value num">{loading ? '—' : avgRx.toFixed(1)}</div>
              <div className="delta">{clients.reduce((s, c) => s + (c.prescriptions?.length || 0), 0)} total</div>
            </div>
            <div className="stat">
              <div className="label">Avg providers</div>
              <div className="value num">{loading ? '—' : avgProviders.toFixed(1)}</div>
              <div className="delta">{clients.reduce((s, c) => s + (c.doctors?.length || 0), 0)} total</div>
            </div>
            <div className="stat">
              <div className="label">Total actions</div>
              <div className="value num">{loading ? '—' : history.length}</div>
              <div className="delta">last 200 events</div>
            </div>
          </div>
        </div>

        <div className="grid-2" style={{ marginTop: 32 }}>
          <div>
            <div className="section-head" style={{ marginTop: 0 }}><h2>Income distribution</h2></div>
            <div className="card card-pad">
              <Bar label="High income" value={byIncome.high || 0} max={incomeMax} tone="accent" />
              <Bar label="Medium income" value={byIncome.medium || 0} max={incomeMax} tone="pos" />
              <Bar label="Low income" value={byIncome.low || 0} max={incomeMax} tone="warn" />
            </div>
          </div>
          <div>
            <div className="section-head" style={{ marginTop: 0 }}><h2>Age groups</h2></div>
            <div className="card card-pad">
              <Bar label="Under 65" value={byAgeGroup.under65} max={ageMax} tone="pos" />
              <Bar label="65–74" value={byAgeGroup.a65to74} max={ageMax} tone="accent" />
              <Bar label="75+" value={byAgeGroup.a75plus} max={ageMax} tone="warn" />
            </div>
          </div>
        </div>

        <div className="section-head"><h2>Tool use</h2></div>
        <div className="card card-pad">
          {Object.keys(byAction).length === 0 ? (
            <div className="muted" style={{ fontSize: 13 }}>No actions logged yet.</div>
          ) : (
            Object.entries(byAction).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
              <Bar key={k} label={k.charAt(0).toUpperCase() + k.slice(1).replace(/_/g, ' ')} value={v} max={actionMax} tone="accent" />
            ))
          )}
        </div>
      </div>
    </>
  );
}
