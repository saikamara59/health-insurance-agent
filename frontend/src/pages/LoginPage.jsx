import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function LoginPage() {
  const navigate = useNavigate()
  const { login, register } = useAuth()

  const [isRegisterMode, setIsRegisterMode] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [remember, setRemember] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setInfo('')
    setLoading(true)

    if (isRegisterMode) {
      const result = await register(email, password, fullName)
      setLoading(false)
      if (result.success) {
        // New accounts land pending admin approval — don't try to auto-login,
        // it would fail with the same pending message and confuse the user.
        setIsRegisterMode(false)
        setPassword('')
        setInfo(
          `Account created for ${email}. An admin will review your registration before you can sign in.`,
        )
      } else {
        setError(result.error || 'Registration failed')
      }
      return
    }

    const result = await login(email, password)
    setLoading(false)
    if (result.success) {
      navigate('/')
    } else {
      setError(result.error || 'Authentication failed')
    }
  }

  return (
    <main className="relative min-h-screen flex items-stretch bg-surface font-body text-on-surface overflow-hidden">
      {/* Left Hero Panel — Full bleed image with gradient overlay */}
      <div className="hidden lg:flex lg:w-7/12 relative overflow-hidden items-end p-20">
        <div className="absolute inset-0 z-0">
          <img
            className="w-full h-full object-cover"
            alt="Modern clinical research laboratory with soft blue ambient lighting"
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuD225ctF3FHD6AVLvzEyrb5yp0zvYv-YLH7SuMFTzxiBvP0JUOQjy-hOWLDBfLf52WR3GCPH_6f2eVNAprPK1Gt1MoL4-29BXCxmPCDadtJHsK8kKwjP9ej7DAC5cPAuWcbhzbNBBhjqLxDpqSnzP8pW-3hiewkm965x0DrTyi4pXql9xOvib_9WzaVlU7QeIMKBelVhBOvtqGQtytul5S50AHViU--CQe_HLOnstl1CWRimZGb-RD502KLYdnC-CvR5AFJHw66-og"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-primary/90 via-primary/20 to-transparent"></div>
        </div>

        <div className="relative z-10 max-w-xl">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-12 h-12 bg-white rounded-xl flex items-center justify-center shadow-lg">
              <span className="material-symbols-outlined text-primary text-3xl">medical_services</span>
            </div>
            <span className="font-logo text-3xl tracking-tighter text-white">HealthFlow</span>
          </div>

          <h1 className="font-headline text-5xl font-bold text-white leading-tight mb-6 tracking-tight">
            Advancing precision medicine with editorial clarity.
          </h1>

          <p className="text-white/80 text-xl font-light leading-relaxed mb-8">
            Access the institutional HealthFlow gateway for clinical curation, patient management, and diagnostic oversight.
          </p>

          <div className="flex gap-4 items-center text-white/90 text-sm tracking-widest font-label">
            <span className="flex items-center gap-2">
              <span className="material-symbols-outlined text-xs">verified_user</span> INSTITUTIONAL GRADE
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-secondary"></span>
            <span className="flex items-center gap-2">
              <span className="material-symbols-outlined text-xs">encrypted</span> END-TO-END SECURE
            </span>
          </div>
        </div>
      </div>

      {/* Right Form Panel */}
      <div className="w-full lg:w-5/12 flex items-center justify-center p-8 bg-surface-container-lowest">
        <div className="w-full max-w-md space-y-12">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-3 mb-12">
            <span className="font-logo text-2xl tracking-tighter text-primary">HealthFlow</span>
          </div>

          {/* Heading */}
          <div className="space-y-4">
            <h2 className="font-headline text-4xl font-bold text-primary tracking-tight">
              {isRegisterMode ? 'Create Account' : 'Sign In'}
            </h2>
            <p className="text-on-surface-variant font-body">
              {isRegisterMode
                ? 'Set up your broker account to get started.'
                : 'Welcome to HealthFlow Institutional Access.'}
            </p>
          </div>

          {/* Error */}
          {error && (
            <div className="p-4 bg-error-container rounded-xl">
              <p className="text-sm text-on-error-container">{error}</p>
            </div>
          )}

          {/* Info (e.g. account-pending-approval after register) */}
          {info && (
            <div className="p-4 bg-primary-container rounded-xl">
              <p className="text-sm text-on-primary-container">{info}</p>
            </div>
          )}

          {/* Form */}
          <form className="space-y-8" onSubmit={handleSubmit}>
            <div className="space-y-6">
              {isRegisterMode && (
                <div className="relative group">
                  <label
                    className="block text-xs font-label uppercase tracking-[0.05em] text-on-surface-variant mb-2 ml-1"
                    htmlFor="fullName"
                  >
                    Full Name
                  </label>
                  <div className="relative flex items-center">
                    <input
                      className="w-full bg-surface-container-low border-none border-b-2 border-transparent focus:border-primary focus:ring-0 rounded-lg px-4 py-4 font-body transition-all group-hover:bg-surface-container placeholder:text-outline/50"
                      id="fullName"
                      placeholder="Dr. Sarah Vance"
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      required
                    />
                    <span className="material-symbols-outlined absolute right-4 text-outline group-hover:text-primary transition-colors">
                      person
                    </span>
                  </div>
                </div>
              )}

              <div className="relative group">
                <label
                  className="block text-xs font-label uppercase tracking-[0.05em] text-on-surface-variant mb-2 ml-1"
                  htmlFor="email"
                >
                  Work Email
                </label>
                <div className="relative flex items-center">
                  <input
                    className="w-full bg-surface-container-low border-none border-b-2 border-transparent focus:border-primary focus:ring-0 rounded-lg px-4 py-4 font-body transition-all group-hover:bg-surface-container placeholder:text-outline/50"
                    id="email"
                    placeholder="dr.smith@healthflow.com"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                  <span className="material-symbols-outlined absolute right-4 text-outline group-hover:text-primary transition-colors">
                    alternate_email
                  </span>
                </div>
              </div>

              <div className="relative group">
                <div className="flex justify-between items-end mb-2 ml-1">
                  <label
                    className="block text-xs font-label uppercase tracking-[0.05em] text-on-surface-variant"
                    htmlFor="password"
                  >
                    Credentials
                  </label>
                  {!isRegisterMode && (
                    <a className="text-xs font-medium text-secondary hover:text-primary transition-colors" href="#">
                      Recover Password
                    </a>
                  )}
                </div>
                <div className="relative flex items-center">
                  <input
                    className="w-full bg-surface-container-low border-none border-b-2 border-transparent focus:border-primary focus:ring-0 rounded-lg px-4 py-4 font-body transition-all group-hover:bg-surface-container placeholder:text-outline/50"
                    id="password"
                    placeholder="••••••••••••"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={8}
                  />
                  <span
                    className="material-symbols-outlined absolute right-4 text-outline group-hover:text-primary transition-colors cursor-pointer"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? 'visibility_off' : 'visibility'}
                  </span>
                </div>

                {isRegisterMode && (
                  <div className="mt-3 ml-1 text-xs text-on-surface-variant">
                    <p className="mb-1.5 font-medium">Password requirements</p>
                    <ul className="space-y-1 list-disc list-inside">
                      <li>At least 12 characters long</li>
                      <li>Mix of letters and at least one number</li>
                      <li>At least one symbol (e.g. ! ? @ # $)</li>
                      <li>Not a commonly used password</li>
                    </ul>
                  </div>
                )}
              </div>
            </div>

            {/* Remember checkbox */}
            <div className="flex items-center gap-3">
              <input
                className="w-5 h-5 rounded border-outline-variant text-primary focus:ring-primary/20"
                id="remember"
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
              />
              <label className="text-sm text-on-surface-variant font-medium cursor-pointer" htmlFor="remember">
                Remember this workstation for 30 days
              </label>
            </div>

            {/* Submit */}
            <div className="space-y-4">
              <button
                className="w-full bg-gradient-to-r from-primary to-primary-container text-on-primary py-4 rounded-xl font-bold text-lg shadow-xl shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-[0.98] flex items-center justify-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed"
                type="submit"
                disabled={loading}
              >
                {loading ? (
                  'Processing...'
                ) : (
                  <>
                    {isRegisterMode ? 'Create Account' : 'Authenticate'}
                    <span className="material-symbols-outlined text-xl">login</span>
                  </>
                )}
              </button>
            </div>
          </form>

          {/* Toggle register/login */}
          <div className="pt-8 text-center">
            <p className="text-sm text-on-surface-variant">
              {isRegisterMode ? 'Already have an account? ' : 'New institutional client? '}
              <button
                className="text-secondary font-bold hover:underline"
                onClick={() => {
                  setIsRegisterMode(!isRegisterMode)
                  setError('')
                }}
              >
                {isRegisterMode ? 'Sign in' : 'Request access'}
              </button>
            </p>
          </div>

          {/* Footer links */}
          <div className="pt-12 flex flex-wrap gap-x-6 gap-y-2 opacity-50">
            <a className="text-[10px] font-label uppercase tracking-widest hover:opacity-100" href="#">Privacy Protocol</a>
            <a className="text-[10px] font-label uppercase tracking-widest hover:opacity-100" href="#">Security Terms</a>
            <a className="text-[10px] font-label uppercase tracking-widest hover:opacity-100" href="#">Help Desk</a>
            <span className="text-[10px] font-label uppercase tracking-widest ml-auto">V.2.4.0</span>
          </div>
        </div>
      </div>

      {/* Network status indicator */}
      <div className="fixed bottom-12 right-12 flex items-center gap-4 bg-white/85 backdrop-blur-[16px] p-3 rounded-full border border-white/20 shadow-2xl z-50">
        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
        <span className="text-xs font-medium text-primary tracking-wide pr-2">HealthFlow Network: Active</span>
      </div>
    </main>
  )
}
