import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import TopBar from '../components/TopBar';
import Icon from '../components/ui/Icon';
import useLayout from '../components/ui/useLayout';
import DrugAutocomplete from '../components/ui/DrugAutocomplete';

export default function AddClientPage() {
  const navigate = useNavigate();
  const { openMenu, openNotifications } = useLayout();

  const [form, setForm] = useState({
    full_name: '',
    zip_code: '',
    age: '',
    income_level: 'medium',
  });
  const [rx, setRx] = useState([]);
  const [procs, setProcs] = useState([]);
  const [procInput, setProcInput] = useState('');
  const [doctors, setDoctors] = useState([]);
  const [docName, setDocName] = useState('');
  const [docNpi, setDocNpi] = useState('');

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const canSubmit = form.full_name.trim() && form.zip_code.trim() && form.age;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!canSubmit) return;
    setSaving(true);
    setError('');
    try {
      const client = await api.post('/clients', {
        full_name: form.full_name.trim(),
        zip_code: form.zip_code.trim(),
        age: parseInt(form.age, 10),
        income_level: form.income_level,
        prescriptions: rx,
        procedures: procs,
        doctors,
      });
      navigate(`/clients/success?id=${client.id}`);
    } catch (err) {
      setError(err.message || 'Could not add client');
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <TopBar
        crumbs={['Clients', 'Add']}
        onMenuClick={openMenu}
        onNotificationsClick={openNotifications}
      />
      <div className="page">
        <div style={{ marginBottom: 20 }}>
          <a onClick={() => navigate('/clients')} className="muted" style={{ fontSize: 13, cursor: 'pointer' }}>
            ← All clients
          </a>
        </div>
        <div className="page-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>New record</div>
            <h1 className="page-title"><em>Add</em> a client.</h1>
            <p className="page-sub">
              Only name, ZIP, and age are required. Add medications, procedures, and providers if you already have
              them — they make comparisons more accurate.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="card card-pad" style={{ padding: 32 }}>
          <div className="eyebrow" style={{ marginBottom: 16 }}>Basics</div>
          <div className="grid-12" style={{ gap: 20 }}>
            <div className="field" style={{ gridColumn: 'span 6' }}>
              <label className="field-label">Full name</label>
              <input
                className="input"
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                placeholder="Marjorie Calloway"
                required
              />
            </div>
            <div className="field" style={{ gridColumn: 'span 2' }}>
              <label className="field-label">ZIP</label>
              <input
                className="input"
                value={form.zip_code}
                onChange={(e) => setForm({ ...form, zip_code: e.target.value })}
                placeholder="10025"
                pattern="\d{5}"
                required
              />
            </div>
            <div className="field" style={{ gridColumn: 'span 2' }}>
              <label className="field-label">Age</label>
              <input
                className="input"
                type="number"
                value={form.age}
                onChange={(e) => setForm({ ...form, age: e.target.value })}
                placeholder="67"
                required
              />
            </div>
            <div className="field" style={{ gridColumn: 'span 2' }}>
              <label className="field-label">Income</label>
              <select
                className="select"
                value={form.income_level}
                onChange={(e) => setForm({ ...form, income_level: e.target.value })}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </div>
          </div>

          <div className="divider" />

          <div className="eyebrow" style={{ marginBottom: 16 }}>Medical</div>
          <div className="grid-2">
            <div>
              <label className="field-label" style={{ marginBottom: 8 }}>Medications</label>
              <DrugAutocomplete values={rx} onChange={setRx} placeholder="e.g. Metformin 500mg" />
            </div>

            <div>
              <label className="field-label" style={{ marginBottom: 8 }}>Expected procedures</label>
              <div className="input-group">
                <input
                  className="input"
                  placeholder="e.g. Annual physical"
                  value={procInput}
                  onChange={(e) => setProcInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      if (procInput.trim()) { setProcs([...procs, procInput.trim()]); setProcInput(''); }
                    }
                  }}
                />
                <button type="button" className="btn" onClick={() => {
                  if (procInput.trim()) { setProcs([...procs, procInput.trim()]); setProcInput(''); }
                }}>Add</button>
              </div>
              <div className="row" style={{ gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                {procs.map((p, i) => (
                  <span key={i} className="chip">
                    {p}
                    <button type="button" onClick={() => setProcs(procs.filter((_, j) => j !== i))} style={{ marginLeft: 4, color: 'var(--ink-4)' }}>
                      <Icon name="x" size={10} />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="divider" />

          <div className="eyebrow" style={{ marginBottom: 16 }}>Providers</div>
          <div className="grid-12" style={{ gap: 12, alignItems: 'end' }}>
            <div className="field" style={{ gridColumn: 'span 6' }}>
              <label className="field-label">Doctor name</label>
              <input className="input" value={docName} onChange={(e) => setDocName(e.target.value)} placeholder="Dr. Patel" />
            </div>
            <div className="field" style={{ gridColumn: 'span 4' }}>
              <label className="field-label">NPI (optional)</label>
              <input className="input" value={docNpi} onChange={(e) => setDocNpi(e.target.value)} placeholder="1356789012" />
            </div>
            <div style={{ gridColumn: 'span 2' }}>
              <button
                type="button"
                className="btn"
                style={{ width: '100%' }}
                onClick={() => {
                  if (!docName.trim()) return;
                  setDoctors([...doctors, { name: docName.trim(), npi: docNpi.trim() || null }]);
                  setDocName('');
                  setDocNpi('');
                }}
              >
                Add provider
              </button>
            </div>
          </div>
          <div className="col" style={{ gap: 6, marginTop: 14 }}>
            {doctors.map((d, i) => (
              <div key={i} className="between" style={{ padding: '8px 12px', border: '1px solid var(--line)', borderRadius: 6 }}>
                <div className="row" style={{ gap: 10 }}>
                  <Icon name="stethoscope" size={14} className="ink-4" />
                  <span style={{ fontSize: 13.5 }}>{d.name}</span>
                  {d.npi && <span className="muted mono" style={{ fontSize: 11.5 }}>NPI {d.npi}</span>}
                </div>
                <button type="button" className="btn ghost icon sm" onClick={() => setDoctors(doctors.filter((_, j) => j !== i))}>
                  <Icon name="x" size={12} />
                </button>
              </div>
            ))}
          </div>

          {error && (
            <div className="notice" style={{ marginTop: 20, color: 'var(--neg)', borderColor: 'var(--neg)' }}>
              {error}
            </div>
          )}

          <div className="between" style={{ marginTop: 28 }}>
            <button type="button" className="btn" onClick={() => navigate('/clients')}>Cancel</button>
            <button type="submit" className="btn accent" disabled={!canSubmit || saving}>
              {saving ? 'Creating…' : <><Icon name="plus" size={14} /> Create client</>}
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
