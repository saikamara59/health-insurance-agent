import { useNavigate, useSearchParams } from 'react-router-dom'
import { useState, useEffect } from 'react'
import api from '../api/client'

export default function OnboardingSuccessPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const clientId = searchParams.get('id')
  const [client, setClient] = useState(null)

  useEffect(() => {
    if (clientId) {
      api.get(`/clients/${clientId}`).then(setClient).catch(() => {})
    }
  }, [clientId])

  return (
    <div className="relative">
      {/* Background accent */}
      <div className="absolute top-0 right-0 w-1/2 h-1/2 bg-gradient-to-bl from-primary-fixed/20 to-transparent -z-10"></div>

      {/* Success Header */}
      <section className="mb-12 flex flex-col items-center text-center">
        <div className="w-16 h-16 bg-secondary-container text-on-secondary-container rounded-full flex items-center justify-center mb-6 shadow-sm">
          <span className="material-symbols-outlined text-4xl" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
        </div>
        <h1 className="font-display text-4xl md:text-5xl text-primary mb-4">Onboarding Successful</h1>
        <p className="text-outline max-w-xl">
          The clinical profile for your new client has been verified and synced with the HealthFlow network. You can now proceed with plan modeling.
        </p>
      </section>

      {/* Bento Grid */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        {/* Client Summary */}
        <div className="md:col-span-7 bg-surface-container-lowest rounded shadow-sm border border-slate-100 p-8">
          <div className="flex justify-between items-start mb-8">
            <div>
              <span className="uppercase tracking-widest text-[11px] font-bold text-secondary mb-2 block">CLIENT PROFILE</span>
              <h2 className="font-headline text-2xl font-bold text-primary">{client?.full_name || 'New Client'}</h2>
            </div>
            <span className="px-3 py-1 bg-secondary-container text-on-secondary-container rounded-full text-[10px] font-bold uppercase tracking-widest">Active Status</span>
          </div>

          <div className="grid grid-cols-2 gap-y-8 gap-x-12">
            <div>
              <p className="uppercase tracking-widest text-[10px] text-outline mb-1">Age</p>
              <p className="font-headline font-semibold text-on-surface">{client?.age || '—'} years old</p>
            </div>
            <div>
              <p className="uppercase tracking-widest text-[10px] text-outline mb-1">Income Level</p>
              <p className="font-headline font-semibold text-on-surface capitalize">{client?.income_level || '—'}</p>
            </div>
            <div>
              <p className="uppercase tracking-widest text-[10px] text-outline mb-1">Zip Code</p>
              <p className="font-headline font-semibold text-on-surface">{client?.zip_code || '—'}</p>
            </div>
            <div>
              <p className="uppercase tracking-widest text-[10px] text-outline mb-1">Client ID</p>
              <p className="font-headline font-semibold text-on-surface text-sm">{client?.id?.slice(0, 12) || '—'}</p>
            </div>
          </div>

          <div className="mt-10 pt-8 border-t border-slate-100">
            <div className="flex flex-wrap gap-6">
              {client?.prescriptions?.length > 0 && (
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-surface-container-low rounded flex items-center justify-center">
                    <span className="material-symbols-outlined text-primary">medication</span>
                  </div>
                  <div>
                    <p className="font-headline font-bold text-sm text-primary">{client.prescriptions.length} Prescriptions</p>
                    <p className="text-xs text-outline">{client.prescriptions.slice(0, 3).join(', ')}{client.prescriptions.length > 3 ? '...' : ''}</p>
                  </div>
                </div>
              )}
              {client?.doctors?.length > 0 && (
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-surface-container-low rounded flex items-center justify-center">
                    <span className="material-symbols-outlined text-primary">stethoscope</span>
                  </div>
                  <div>
                    <p className="font-headline font-bold text-sm text-primary">{client.doctors.length} Providers</p>
                    <p className="text-xs text-outline">{client.doctors.slice(0, 2).map(d => d.name).join(', ')}{client.doctors.length > 2 ? '...' : ''}</p>
                  </div>
                </div>
              )}
              {client?.procedures?.length > 0 && (
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-surface-container-low rounded flex items-center justify-center">
                    <span className="material-symbols-outlined text-primary">medical_services</span>
                  </div>
                  <div>
                    <p className="font-headline font-bold text-sm text-primary">{client.procedures.length} Procedures</p>
                    <p className="text-xs text-outline">{client.procedures.slice(0, 2).join(', ')}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="md:col-span-5 flex flex-col gap-4">
          <div onClick={() => clientId && navigate(`/clients/${clientId}`)}
            className="bg-primary text-white p-6 rounded shadow-md group cursor-pointer hover:bg-primary-container transition-all">
            <div className="flex justify-between items-center mb-2">
              <span className="material-symbols-outlined text-secondary-container">compare_arrows</span>
              <span className="material-symbols-outlined opacity-0 group-hover:opacity-100 transition-opacity">arrow_forward</span>
            </div>
            <h3 className="font-headline font-bold text-lg mb-1">Run Plan Comparison</h3>
            <p className="text-sm text-blue-200/80">Compare plans based on {client?.full_name || 'client'}'s profile and prescriptions.</p>
          </div>

          <div onClick={() => navigate('/network')}
            className="bg-surface-container-low border border-slate-200/50 p-6 rounded group cursor-pointer hover:bg-surface-container-high transition-all">
            <div className="flex items-center gap-4 mb-3">
              <span className="material-symbols-outlined text-secondary">verified_user</span>
              <h3 className="font-headline font-bold text-primary">Verify Network</h3>
            </div>
            <p className="text-xs text-outline">Check provider and pharmacy network status for this region.</p>
          </div>

          <div onClick={() => clientId && navigate(`/clients/${clientId}`)}
            className="bg-surface-container-low border border-slate-200/50 p-6 rounded group cursor-pointer hover:bg-surface-container-high transition-all">
            <div className="flex items-center gap-4 mb-3">
              <span className="material-symbols-outlined text-secondary">person_search</span>
              <h3 className="font-headline font-bold text-primary">View Profile</h3>
            </div>
            <p className="text-xs text-outline">Review full demographic and clinical details for accuracy.</p>
          </div>

          <button onClick={() => navigate('/clients/new')}
            className="mt-4 w-full border border-blue-900 text-blue-900 font-bold py-3 px-6 rounded hover:bg-blue-50 transition-colors uppercase tracking-widest text-[11px]">
            Add Another Client
          </button>
        </div>

        {/* Tips Section */}
        <div className="md:col-span-12 mt-4">
          <div className="bg-white/80 backdrop-blur-[12px] rounded-lg border border-white/20 p-8 relative overflow-hidden">
            <div className="absolute -right-12 -bottom-12 w-48 h-48 bg-primary/5 rounded-full blur-3xl"></div>
            <div className="flex items-start gap-6 relative z-10">
              <div className="bg-white p-4 rounded shadow-sm border border-slate-100 shrink-0">
                <span className="material-symbols-outlined text-secondary text-3xl">lightbulb</span>
              </div>
              <div className="flex-1">
                <span className="uppercase tracking-widest text-[11px] font-bold text-secondary mb-2 block">ONBOARDING TIPS</span>
                <h3 className="font-display text-xl text-primary mb-4">Optimizing the Next Phase</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                  <div>
                    <p className="font-headline font-bold text-sm text-primary mb-2">Run Analysis First</p>
                    <p className="text-xs text-outline leading-relaxed">Plan comparison tools yield better results when the client profile includes prescriptions and preferred providers.</p>
                  </div>
                  <div>
                    <p className="font-headline font-bold text-sm text-primary mb-2">Network Verification</p>
                    <p className="text-xs text-outline leading-relaxed">Verify provider networks early to avoid out-of-network surprises during enrollment.</p>
                  </div>
                  <div>
                    <p className="font-headline font-bold text-sm text-primary mb-2">Cost Projection</p>
                    <p className="text-xs text-outline leading-relaxed">Use the cost calculator to estimate annual out-of-pocket based on expected healthcare utilization.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
