import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/client';
import TopBar from '../components/TopBar';
import Icon from '../components/ui/Icon';
import useLayout from '../components/ui/useLayout';

const TABS = ['profile', 'appearance', 'sign-out'];

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const { openMenu, openNotifications } = useLayout();

  const [tab, setTab] = useState('profile');
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState({ full_name: '', email: '' });
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');

  useEffect(() => {
    api.get('/auth/profile').then((p) => {
      setProfile(p);
      setForm({ full_name: p.full_name || '', email: p.email || '' });
    }).catch(() => {});
  }, []);

  async function saveProfile(e) {
    e.preventDefault();
    setSaving(true);
    setSaveMsg('');
    try {
      const updated = await api.put('/auth/profile', form);
      setProfile(updated);
      setSaveMsg('Saved');
      setTimeout(() => setSaveMsg(''), 2000);
    } catch (err) {
      setSaveMsg(`Error: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <TopBar crumbs={['Review', 'Settings']} onMenuClick={openMenu} onNotificationsClick={openNotifications} />
      <div className="page" style={{ fontFamily: '"Times New Roman"' }}>
        <div className="page-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>Your account</div>
            <h1 className="page-title"><em>Settings</em></h1>
            <p className="page-sub">
              Name, email, and appearance. More settings will land here as team access and commission tracking ship.
            </p>
          </div>
        </div>

        <div className="tabs-row">
          {TABS.map((t) => (
            <button key={t} onClick={() => setTab(t)} className={`tab-btn ${tab === t ? 'active' : ''}`}>
              {t.replace('-', ' ')}
            </button>
          ))}
        </div>

        {tab === 'profile' && (
          <form onSubmit={saveProfile} className="card card-pad" style={{ marginTop: 28, maxWidth: 620 }}>
            <div className="eyebrow" style={{ marginBottom: 16 }}>Profile</div>
            <div className="col" style={{ gap: 16 }}>
              <div className="field">
                <label className="field-label">Full name</label>
                <input className="input" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
              </div>
              <div className="field">
                <label className="field-label">Email</label>
                <input className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
              </div>
              {profile && (
                <div className="field">
                  <label className="field-label">Role</label>
                  <input className="input" value={profile.role} disabled style={{ opacity: 0.7 }} />
                </div>
              )}
            </div>
            <div className="between" style={{ marginTop: 24 }}>
              {saveMsg && <span className="muted" style={{ fontSize: 12 }}>{saveMsg}</span>}
              <div style={{ marginLeft: 'auto' }}>
                <button type="submit" className="btn accent" disabled={saving}>
                  {saving ? 'Saving…' : 'Save changes'}
                </button>
              </div>
            </div>
          </form>
        )}

        {tab === 'appearance' && (
          <div className="card card-pad" style={{ marginTop: 28, maxWidth: 620 }}>
            <div className="eyebrow" style={{ marginBottom: 16 }}>Appearance</div>
            <p style={{ fontSize: 13.5, color: 'var(--ink-2)', lineHeight: 1.6 }}>
              Accent color, dark mode, and density are controlled from the <strong>Tweaks</strong> panel in the
              bottom-right corner. Your choices are saved to this browser.
            </p>
          </div>
        )}

        {tab === 'sign-out' && (
          <div className="card card-pad" style={{ marginTop: 28, maxWidth: 620 }}>
            <div className="eyebrow" style={{ marginBottom: 16 }}>Session</div>
            <p style={{ fontSize: 13.5, color: 'var(--ink-2)', marginBottom: 20 }}>
              Signed in as <strong>{user?.email}</strong>. Signing out clears your session on this device.
            </p>
            <button className="btn danger" onClick={logout}>
              <Icon name="logout" size={14} /> Sign out
            </button>
          </div>
        )}
      </div>
    </>
  );
}
