import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'

const TABS = ['Profile Identity', 'Security Protocols', 'API Integrations', 'Notifications']

export default function SettingsPage() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState(0)
  const [profile, setProfile] = useState({
    full_name: user?.full_name || user?.email?.split('@')[0] || '',
    title: 'Clinical Director',
    email: user?.email || '',
    department: 'Brokerage Operations',
  })
  const [saved, setSaved] = useState(false)

  function handleSave() {
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <>
      {/* Header */}
      <div className="mb-12">
        <h1 className="text-4xl font-extrabold text-primary tracking-tight mb-2 font-display">Account Settings</h1>
        <p className="text-on-surface-variant max-w-2xl text-lg leading-relaxed">
          Manage your institutional identity, security protocols, and third-party data connections from the central HealthFlow control panel.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-12 mb-10 border-b border-outline-variant/15">
        {TABS.map((tab, i) => (
          <button
            key={tab}
            onClick={() => setActiveTab(i)}
            className={`pb-4 font-medium transition-all ${
              activeTab === i
                ? 'text-primary font-bold border-b-2 border-primary'
                : 'text-on-surface-variant hover:text-primary'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Bento Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column */}
        <div className="lg:col-span-8 space-y-8">
          {/* Profile Card */}
          {activeTab === 0 && (
            <div className="bg-surface-container-lowest rounded-xl p-8 shadow-sm shadow-primary/5 ring-1 ring-black/[0.02]">
              <div className="flex items-start justify-between mb-8">
                <div className="flex items-center gap-6">
                  <div className="relative group">
                    <div className="w-24 h-24 rounded-full bg-primary flex items-center justify-center text-on-primary text-2xl font-bold shadow-md">
                      {profile.full_name.split(' ').map(n => n[0]).join('').toUpperCase()}
                    </div>
                    <div className="absolute inset-0 bg-primary/20 rounded-full opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center cursor-pointer">
                      <span className="material-symbols-outlined text-white">edit</span>
                    </div>
                  </div>
                  <div>
                    <h3 className="text-2xl font-bold text-primary">{profile.full_name}</h3>
                    <p className="text-on-surface-variant">{profile.title} • {user?.role || 'broker'}</p>
                  </div>
                </div>
                <button
                  onClick={handleSave}
                  className="bg-primary text-on-primary px-6 py-2.5 rounded-lg font-semibold hover:opacity-90 transition-opacity"
                >
                  {saved ? 'Saved!' : 'Save Changes'}
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-on-surface-variant/70 px-1">Full Legal Name</label>
                  <input
                    className="w-full bg-surface-container-low border-b-2 border-transparent focus:border-primary px-4 py-3 rounded-t-lg focus:outline-none transition-all"
                    type="text"
                    value={profile.full_name}
                    onChange={(e) => setProfile({ ...profile, full_name: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-on-surface-variant/70 px-1">Professional Title</label>
                  <input
                    className="w-full bg-surface-container-low border-b-2 border-transparent focus:border-primary px-4 py-3 rounded-t-lg focus:outline-none transition-all"
                    type="text"
                    value={profile.title}
                    onChange={(e) => setProfile({ ...profile, title: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-on-surface-variant/70 px-1">Institutional Email</label>
                  <input
                    className="w-full bg-surface-container-low border-b-2 border-transparent focus:border-primary px-4 py-3 rounded-t-lg focus:outline-none transition-all"
                    type="email"
                    value={profile.email}
                    readOnly
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-on-surface-variant/70 px-1">Department</label>
                  <input
                    className="w-full bg-surface-container-low border-b-2 border-transparent focus:border-primary px-4 py-3 rounded-t-lg focus:outline-none transition-all"
                    type="text"
                    value={profile.department}
                    onChange={(e) => setProfile({ ...profile, department: e.target.value })}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Security Tab */}
          {activeTab === 1 && (
            <div className="bg-surface-container-lowest rounded-xl p-8 shadow-sm shadow-primary/5 ring-1 ring-black/[0.02]">
              <h3 className="text-xl font-bold text-primary mb-6">Security Configuration</h3>
              <div className="space-y-6">
                <div className="flex items-center justify-between p-4 bg-surface-container-low rounded-lg">
                  <div>
                    <p className="font-bold text-on-surface">Two-Factor Authentication</p>
                    <p className="text-sm text-on-surface-variant">Add an extra layer of security to your account</p>
                  </div>
                  <span className="px-3 py-1 bg-green-100 text-green-700 text-xs font-bold rounded-full">ENABLED</span>
                </div>
                <div className="flex items-center justify-between p-4 bg-surface-container-low rounded-lg">
                  <div>
                    <p className="font-bold text-on-surface">Session Timeout</p>
                    <p className="text-sm text-on-surface-variant">Automatically sign out after inactivity</p>
                  </div>
                  <span className="text-sm font-bold text-primary">30 minutes</span>
                </div>
                <div className="flex items-center justify-between p-4 bg-surface-container-low rounded-lg">
                  <div>
                    <p className="font-bold text-on-surface">Password Last Changed</p>
                    <p className="text-sm text-on-surface-variant">Regular password updates recommended</p>
                  </div>
                  <button className="text-primary font-bold text-sm hover:underline">Change Password</button>
                </div>
              </div>
            </div>
          )}

          {/* API Tab */}
          {activeTab === 2 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-surface-container-low rounded-xl p-6 border border-outline-variant/10">
                <div className="flex items-center justify-between mb-4">
                  <div className="w-12 h-12 bg-white rounded-lg flex items-center justify-center shadow-sm">
                    <span className="material-symbols-outlined text-secondary">hub</span>
                  </div>
                  <span className="px-3 py-1 bg-green-100 text-green-700 text-xs font-bold rounded-full">CONNECTED</span>
                </div>
                <h4 className="font-bold text-lg text-primary mb-1">HealthStream API</h4>
                <p className="text-sm text-on-surface-variant mb-4">Real-time vital synchronization and clinical telemetry feed.</p>
                <button className="text-primary font-bold text-sm hover:underline flex items-center gap-2">
                  Configure Keys <span className="material-symbols-outlined text-sm">chevron_right</span>
                </button>
              </div>
              <div className="bg-surface-container-low rounded-xl p-6 border border-outline-variant/10">
                <div className="flex items-center justify-between mb-4">
                  <div className="w-12 h-12 bg-white rounded-lg flex items-center justify-center shadow-sm">
                    <span className="material-symbols-outlined text-tertiary">database</span>
                  </div>
                  <span className="px-3 py-1 bg-slate-200 text-slate-600 text-xs font-bold rounded-full">INACTIVE</span>
                </div>
                <h4 className="font-bold text-lg text-primary mb-1">Legacy EHR Sync</h4>
                <p className="text-sm text-on-surface-variant mb-4">Batch processing for historical patient records and archives.</p>
                <button className="text-primary font-bold text-sm hover:underline flex items-center gap-2">
                  Initialize Setup <span className="material-symbols-outlined text-sm">chevron_right</span>
                </button>
              </div>
            </div>
          )}

          {/* Notifications Tab */}
          {activeTab === 3 && (
            <div className="bg-surface-container-lowest rounded-xl p-8 shadow-sm shadow-primary/5 ring-1 ring-black/[0.02]">
              <h3 className="text-xl font-bold text-primary mb-6">Notification Preferences</h3>
              <div className="space-y-6">
                {[
                  { label: 'Client Activity Alerts', desc: 'Get notified when clients require attention', on: true },
                  { label: 'Compliance Deadlines', desc: 'Reminders for upcoming regulatory deadlines', on: true },
                  { label: 'System Maintenance', desc: 'Platform update and maintenance notifications', on: false },
                  { label: 'Weekly Digest', desc: 'Summary of portfolio performance every Monday', on: true },
                ].map((pref) => (
                  <div key={pref.label} className="flex items-center justify-between p-4 bg-surface-container-low rounded-lg">
                    <div>
                      <p className="font-bold text-on-surface">{pref.label}</p>
                      <p className="text-sm text-on-surface-variant">{pref.desc}</p>
                    </div>
                    <div className={`w-12 h-7 rounded-full flex items-center px-1 cursor-pointer transition-colors ${pref.on ? 'bg-primary justify-end' : 'bg-slate-300 justify-start'}`}>
                      <div className="w-5 h-5 bg-white rounded-full shadow-sm"></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right Column */}
        <div className="lg:col-span-4 space-y-8">
          {/* Security Posture */}
          <div className="bg-primary text-white rounded-xl p-8 shadow-xl shadow-primary/20 relative overflow-hidden">
            <div className="relative z-10">
              <div className="flex items-center gap-3 mb-6">
                <span className="material-symbols-outlined">verified_user</span>
                <h3 className="font-bold tracking-tight text-xl">Security Posture</h3>
              </div>
              <div className="mb-8">
                <div className="text-4xl font-extrabold mb-1">A+</div>
                <p className="text-blue-100 text-sm">Last audited 2 hours ago</p>
              </div>
              <div className="space-y-4 mb-8">
                <div className="flex justify-between items-center text-sm">
                  <span>2FA Status</span>
                  <span className="font-bold">Active</span>
                </div>
                <div className="w-full bg-blue-900/40 h-1.5 rounded-full">
                  <div className="bg-white h-1.5 rounded-full w-[94%]"></div>
                </div>
              </div>
              <button className="w-full bg-white text-primary py-3 rounded-lg font-bold hover:bg-blue-50 transition-colors">
                Manage Credentials
              </button>
            </div>
            <div className="absolute -bottom-10 -right-10 w-40 h-40 bg-blue-400/10 rounded-full blur-3xl"></div>
          </div>

          {/* Usage Stats */}
          <div className="bg-surface-container-high rounded-xl p-8 space-y-6">
            <h4 className="font-bold text-primary uppercase text-xs tracking-widest">Platform Usage</h4>
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                <span className="material-symbols-outlined text-blue-800 text-xl">key</span>
              </div>
              <div>
                <div className="text-xl font-bold text-primary">12 Active</div>
                <p className="text-xs text-on-surface-variant font-medium">API Tokens Generated</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center">
                <span className="material-symbols-outlined text-purple-800 text-xl">history</span>
              </div>
              <div>
                <div className="text-xl font-bold text-primary">2,482</div>
                <p className="text-xs text-on-surface-variant font-medium">Logins this Quarter</p>
              </div>
            </div>
            <div className="pt-4 mt-4 border-t border-outline-variant/20">
              <p className="text-xs text-on-surface-variant italic leading-relaxed">
                System access is logged under HIPAA compliance protocols. Unauthorized access attempts are flagged automatically.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
