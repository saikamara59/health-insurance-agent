import { useState, useEffect } from 'react'
import api from '../api/client'

const MONTHS = ['Jul','Aug','Sep','Oct','Nov','Dec','Jan','Feb','Mar','Apr','May','Jun']
const BAR_HEIGHTS = [40,45,50,55,65,60,75,85,90,95,80,85]
const BAR_OPACITY = ['bg-slate-100','bg-slate-100','bg-slate-100','bg-slate-100','bg-primary/20','bg-primary/40','bg-primary/60','bg-primary/80','bg-primary','bg-primary','bg-primary/30 border-t-2 border-dashed border-primary','bg-primary/20 border-t-2 border-dashed border-primary']

const COHORTS = [
  { icon: 'medical_services', iconBg: 'bg-primary/10 text-primary', name: 'Chronic Care Cohort', sub: 'Hypertension Focus', patients: '482 Patients', velocity: '+4.2%', velColor: 'text-error', velIcon: 'arrow_upward', savings: '$124,500', status: 'Urgent Review', statusCls: 'bg-error-container text-on-error-container' },
  { icon: 'eco', iconBg: 'bg-secondary/10 text-secondary', name: 'Preventative Care Pipeline', sub: 'Annual Check-up Compliance', patients: '1,120 Patients', velocity: '-2.1%', velColor: 'text-secondary', velIcon: 'arrow_downward', savings: '$82,000', status: 'On Track', statusCls: 'bg-secondary-container text-on-secondary-container' },
  { icon: 'psychology', iconBg: 'bg-tertiary/10 text-tertiary', name: 'Behavioral Health Cluster', sub: 'Specialized Counseling', patients: '245 Patients', velocity: 'Stable', velColor: 'text-slate-400', velIcon: 'horizontal_rule', savings: '$45,200', status: 'Scheduled', statusCls: 'bg-surface-container-high text-on-surface-variant' },
]

const REPORTS = [
  { icon: 'description', name: 'Q2_Market_Trend_Analysis.pdf', meta: 'Generated Apr 12, 2026 · 4.2 MB' },
  { icon: 'analytics', name: 'Monthly_Risk_Migration_Audit.xlsx', meta: 'Generated Apr 10, 2026 · 1.8 MB' },
  { icon: 'summarize', name: 'Clinical_Cohort_Savings_Report.pdf', meta: 'Generated Apr 08, 2026 · 3.5 MB' },
]

export default function AnalyticsPage() {
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/clients').then(data => { setClients(Array.isArray(data) ? data : []); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  const totalClients = loading ? '...' : clients.length
  const managedAssets = loading ? '...' : `$${(clients.length * 19.3).toFixed(1)}K`

  return (
    <>
      {/* Header */}
      <div className="flex items-end justify-between mb-8">
        <div>
          <h2 className="text-3xl font-extrabold font-headline text-on-surface tracking-tight">Performance Analytics</h2>
          <p className="text-on-surface-variant mt-1">Real-time health brokerage insights and clinical trend monitoring.</p>
        </div>
        <div className="flex gap-3">
          <button className="flex items-center gap-2 px-4 py-2 bg-surface-container-high text-primary rounded-xl font-semibold text-sm hover:bg-surface-container-highest transition-colors">
            <span className="material-symbols-outlined text-sm">calendar_today</span> Last 30 Days
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-xl font-semibold text-sm shadow-lg shadow-primary/20">
            <span className="material-symbols-outlined text-sm">file_download</span> Export PDF
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm border-l-4 border-primary">
          <div className="flex justify-between items-start mb-4">
            <div className="p-2 bg-primary/10 text-primary rounded-lg"><span className="material-symbols-outlined">account_balance_wallet</span></div>
            <span className="text-secondary text-xs font-bold flex items-center gap-1"><span className="material-symbols-outlined text-xs">trending_up</span>5.2%</span>
          </div>
          <p className="text-on-surface-variant text-xs font-medium uppercase tracking-wider">Total Managed Assets</p>
          <h3 className="text-2xl font-extrabold font-headline text-on-surface mt-1">{managedAssets}</h3>
        </div>
        <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <div className="p-2 bg-secondary/10 text-secondary rounded-lg"><span className="material-symbols-outlined">savings</span></div>
          </div>
          <p className="text-on-surface-variant text-xs font-medium uppercase tracking-wider">Average Plan Savings</p>
          <h3 className="text-2xl font-extrabold font-headline text-on-surface mt-1">18.5%</h3>
        </div>
        <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <div className="p-2 bg-tertiary/10 text-tertiary rounded-lg"><span className="material-symbols-outlined">groups</span></div>
            <span className="text-secondary text-xs font-bold flex items-center gap-1"><span className="material-symbols-outlined text-xs">arrow_upward</span>12.4%</span>
          </div>
          <p className="text-on-surface-variant text-xs font-medium uppercase tracking-wider">Client Growth Rate</p>
          <h3 className="text-2xl font-extrabold font-headline text-on-surface mt-1">12.4%</h3>
        </div>
        <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <div className="p-2 bg-secondary-container/30 text-on-secondary-container rounded-lg"><span className="material-symbols-outlined">verified_user</span></div>
          </div>
          <p className="text-on-surface-variant text-xs font-medium uppercase tracking-wider">Policy Retention</p>
          <h3 className="text-2xl font-extrabold font-headline text-on-surface mt-1">94%</h3>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-12 gap-6 mb-8">
        {/* Bar Chart */}
        <div className="col-span-12 lg:col-span-8 bg-surface-container-lowest p-8 rounded-xl shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h4 className="text-lg font-bold font-headline">Brokerage Growth & Projections</h4>
              <p className="text-xs text-on-surface-variant">Asset value performance over the trailing 12 months</p>
            </div>
            <div className="flex gap-4">
              <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-primary"></span><span className="text-xs font-medium">Actual</span></div>
              <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-slate-200"></span><span className="text-xs font-medium">Projected</span></div>
            </div>
          </div>
          <div className="h-64 flex items-end justify-between gap-2 relative">
            <div className="absolute inset-0 flex items-end">
              <svg className="w-full h-full opacity-20" preserveAspectRatio="none" viewBox="0 0 100 100">
                <path d="M0,80 L10,75 L20,78 L30,65 L40,60 L50,55 L60,45 L70,48 L80,35 L90,30 L100,25 L100,100 L0,100 Z" fill="url(#cg)"></path>
                <defs><linearGradient id="cg" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#006194"></stop><stop offset="100%" stopColor="transparent"></stop></linearGradient></defs>
              </svg>
            </div>
            <div className="w-full h-48 flex items-end justify-between px-4 relative z-10">
              {BAR_HEIGHTS.map((h, i) => (
                <div key={i} className={`w-6 ${BAR_OPACITY[i]} rounded-t-lg`} style={{ height: `${h}%` }}></div>
              ))}
            </div>
          </div>
          <div className="flex justify-between px-4 mt-4 text-[10px] font-bold text-slate-400 uppercase tracking-tighter">
            {MONTHS.map(m => <span key={m}>{m}</span>)}
          </div>
        </div>

        {/* Donut Chart */}
        <div className="col-span-12 lg:col-span-4 bg-surface-container-lowest p-8 rounded-xl shadow-sm">
          <h4 className="text-lg font-bold font-headline mb-1">Risk Profile Distribution</h4>
          <p className="text-xs text-on-surface-variant mb-8">Client allocation by clinical risk score</p>
          <div className="flex items-center justify-center py-4">
            <div className="relative w-48 h-48 rounded-full border-[20px] border-secondary-container flex items-center justify-center">
              <div className="absolute inset-0 rounded-full border-[20px] border-primary border-r-transparent border-b-transparent -rotate-45"></div>
              <div className="absolute inset-0 rounded-full border-[20px] border-error border-l-transparent border-r-transparent border-t-transparent rotate-12"></div>
              <div className="text-center">
                <span className="block text-2xl font-black font-headline">{totalClients}</span>
                <span className="text-[10px] text-on-surface-variant font-bold uppercase">Total Clients</span>
              </div>
            </div>
          </div>
          <div className="mt-8 space-y-3">
            {[{ color: 'bg-secondary-container', label: 'Low Risk', pct: '62%' }, { color: 'bg-primary', label: 'Medium Risk', pct: '28%' }, { color: 'bg-error', label: 'High Risk', pct: '10%' }].map(r => (
              <div key={r.label} className="flex items-center justify-between">
                <div className="flex items-center gap-2"><span className={`w-3 h-3 rounded-full ${r.color}`}></span><span className="text-sm font-medium">{r.label}</span></div>
                <span className="text-sm font-bold">{r.pct}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Cohorts Table */}
      <div className="bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden mb-8">
        <div className="px-8 py-6 flex items-center justify-between border-b border-surface-container">
          <div>
            <h4 className="text-lg font-bold font-headline">High-Impact Clinical Cohorts</h4>
            <p className="text-xs text-on-surface-variant">Recommended policy reviews based on health trend deviations</p>
          </div>
          <button className="text-primary text-sm font-bold hover:underline">View All Cohorts</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface-container-low text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">
                <th className="px-8 py-4">Cohort Identity</th>
                <th className="px-8 py-4">Patient Count</th>
                <th className="px-8 py-4">Risk Velocity</th>
                <th className="px-8 py-4">Est. Savings</th>
                <th className="px-8 py-4">Status</th>
                <th className="px-8 py-4">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container">
              {COHORTS.map(c => (
                <tr key={c.name} className="hover:bg-surface-container-low/50 transition-colors">
                  <td className="px-8 py-4">
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-lg ${c.iconBg} flex items-center justify-center`}><span className="material-symbols-outlined text-sm">{c.icon}</span></div>
                      <div><p className="text-sm font-bold">{c.name}</p><p className="text-[10px] text-on-surface-variant">{c.sub}</p></div>
                    </div>
                  </td>
                  <td className="px-8 py-4 font-medium text-sm">{c.patients}</td>
                  <td className="px-8 py-4"><div className={`flex items-center gap-1 ${c.velColor} text-xs font-bold`}><span className="material-symbols-outlined text-xs">{c.velIcon}</span>{c.velocity}</div></td>
                  <td className="px-8 py-4 font-bold text-sm text-secondary">{c.savings}</td>
                  <td className="px-8 py-4"><span className={`px-2 py-1 ${c.statusCls} text-[10px] font-bold rounded-md uppercase`}>{c.status}</span></td>
                  <td className="px-8 py-4"><button className="p-2 hover:bg-surface-container-high rounded-full transition-colors"><span className="material-symbols-outlined text-sm">more_vert</span></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Reports + CTA */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 bg-surface-container-lowest p-8 rounded-xl shadow-sm">
          <div className="flex items-center justify-between mb-6">
            <h4 className="text-lg font-bold font-headline">Recent Auto-Generated Reports</h4>
            <span className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">Last 7 Days</span>
          </div>
          <div className="space-y-4">
            {REPORTS.map(r => (
              <div key={r.name} className="flex items-center justify-between p-4 bg-surface-container-low rounded-xl hover:bg-surface-container transition-colors">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-lg bg-white shadow-sm flex items-center justify-center text-primary"><span className="material-symbols-outlined">{r.icon}</span></div>
                  <div><p className="text-sm font-bold">{r.name}</p><p className="text-[10px] text-on-surface-variant uppercase tracking-tighter">{r.meta}</p></div>
                </div>
                <button className="p-2 text-primary hover:bg-primary/10 rounded-lg transition-colors"><span className="material-symbols-outlined">download</span></button>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-primary p-8 rounded-xl shadow-lg shadow-primary/20 flex flex-col justify-between text-white relative overflow-hidden">
          <div className="absolute -top-12 -right-12 w-48 h-48 bg-white/10 rounded-full blur-3xl"></div>
          <div className="absolute -bottom-8 -left-8 w-32 h-32 bg-secondary-container/20 rounded-full blur-2xl"></div>
          <div className="relative z-10">
            <span className="material-symbols-outlined text-4xl mb-4">auto_awesome</span>
            <h4 className="text-xl font-bold font-headline mb-2 leading-tight">Need a custom clinical insight?</h4>
            <p className="text-white/80 text-sm">Schedule a recurring report or generate a one-time deep dive into any dataset.</p>
          </div>
          <div className="mt-8 space-y-3 relative z-10">
            <button className="w-full py-3 bg-white text-primary rounded-xl font-bold text-sm hover:bg-white/90 transition-colors">Schedule New Report</button>
            <button className="w-full py-3 bg-primary-container text-white rounded-xl font-bold text-sm border border-white/20 hover:bg-white/10 transition-colors">Configure Dashboards</button>
          </div>
        </div>
      </div>
    </>
  )
}
