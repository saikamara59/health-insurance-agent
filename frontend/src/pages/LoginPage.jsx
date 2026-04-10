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
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    let result
    if (isRegisterMode) {
      result = await register(email, password, fullName)
      if (result.success) {
        // After registration, auto-login
        result = await login(email, password)
      }
    } else {
      result = await login(email, password)
    }

    setLoading(false)

    if (result.success) {
      navigate('/')
    } else {
      setError(result.error || 'Authentication failed')
    }
  }

  return (
    <div className="bg-surface text-on-surface min-h-screen flex items-center justify-center p-4">
      <main className="w-full max-w-[1200px] grid grid-cols-1 md:grid-cols-2 bg-surface-container-lowest rounded-xl overflow-hidden shadow-sm">
        {/* Left Hero Panel */}
        <section className="hidden md:flex flex-col justify-between p-12 bg-primary relative overflow-hidden">
          <div
            className="absolute inset-0 opacity-10 pointer-events-none"
            style={{
              backgroundImage: 'radial-gradient(circle at 20% 30%, #ffffff 1px, transparent 1px)',
              backgroundSize: '40px 40px',
            }}
          ></div>

          <div className="relative z-10">
            <div className="flex items-center gap-3 mb-12">
              <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center backdrop-blur-md">
                <span className="material-symbols-outlined text-white">health_and_safety</span>
              </div>
              <span className="font-headline text-2xl font-extrabold text-white tracking-tight">HealthFlow</span>
            </div>

            <h1 className="font-headline text-5xl font-extrabold text-white leading-tight mb-6">
              Precision Analytics for <br />
              <span className="text-secondary-fixed">Healthcare Brokers.</span>
            </h1>

            <p className="text-primary-fixed text-lg max-w-md leading-relaxed">
              Access your comprehensive dashboard to manage clients, compare policies, and streamline your brokerage workflow with clinical accuracy.
            </p>
          </div>

          <div className="relative z-10">
            <div className="bg-white/10 backdrop-blur-xl rounded-xl p-6 border border-white/10">
              <div className="flex items-center gap-4 mb-4">
                <div className="flex -space-x-2">
                  <img
                    className="w-10 h-10 rounded-full border-2 border-primary"
                    alt="professional female doctor"
                    src="https://lh3.googleusercontent.com/aida-public/AB6AXuDxf_tp_kDtwBqV0CwMFH9Un3IPNDvh8i0qFJVZY3odjR8A-mpHkpggcDoC47_xy_RJev1uXdvxjKzk-JfpyBFWw8NQug9zL78YMKBbau0X2xuAdXR2lBz_iP_UfsD_12Z0v-y5LV0ncdeG2q2DyMZI4DGjNPVFVPCf_2xIbrZoQxM88h1U1gdoYYoweTQLrJmcRwMLa5XL4Tc3_7m-K2MXy71kg245RQW5jMgpSuUaOE1-9DkaON97WOe3z5wQfzZQOeyGMSJx5V8"
                  />
                  <img
                    className="w-10 h-10 rounded-full border-2 border-primary"
                    alt="male healthcare professional"
                    src="https://lh3.googleusercontent.com/aida-public/AB6AXuBGSDN9sdtlesQJWtaklIbdphfH2srkDn315mftwV8y7Muj6dehHVlgPYfqhiGGblIgy5eXx4s8JWmEtAqstc9QuBY1XRr6heuueK6eGqduemRkZQFrrP4pgLrwFguAd2DVUv3Qe_pfFn0_bOInkU4xKRmAV4agqMskkQlfLjvmhRiVnOMfvCUtqaMnVC5XZa10lZPYv-eP930X6XMQjMyXZwCuryiUPwt8QXWiSBWyf6h-L8jh6_8b2vcTwF0Y-g65oIGFSS4qeU8"
                  />
                  <img
                    className="w-10 h-10 rounded-full border-2 border-primary"
                    alt="professional male doctor"
                    src="https://lh3.googleusercontent.com/aida-public/AB6AXuBMqoN_zi4aAoyIU9Q_byjnec5KP5IlJ7RMoWPxUx2-4TPDnFvltdi5DTNqPBTmue1k4xyWfcT5BIoVx_QvoSlm1iYqnvqBWEYdAoTQ70mlfOFcDwSLCshEClpXIh5fDuq4OnGHs1VpLkBIAsixZ2F3vLs1McXuqJoaahS4m4CHWYTHYs90kJqhbVP-n4-JEnF--ZQN50UpgHSP6zgeHjOQMCoOcELZDN9L6DY6pMbHfkwJa5jevF7k4drbn3Crx5k_ImYPp7s65_Y"
                  />
                </div>
                <span className="text-white text-sm font-medium">Trusted by 2,000+ top-tier brokers</span>
              </div>

              <div className="flex items-center gap-2">
                {[1, 2, 3, 4, 5].map((i) => (
                  <span
                    key={i}
                    className="material-symbols-outlined text-secondary-fixed text-sm"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    star
                  </span>
                ))}
                <span className="text-primary-fixed text-xs ml-2">5.0 average user rating</span>
              </div>
            </div>
          </div>

          <div className="absolute -right-20 bottom-0 w-[80%] h-[60%] opacity-20 pointer-events-none">
            <img
              className="w-full h-full object-cover rounded-tl-[100px]"
              alt="abstract medical lab equipment"
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuBPAQ0yoL-aBmkG9zzU-qMvFG8hIflLLtxTh2G3nliSj7nu98SH9CpsnYS5dedrIJ7nelczkyg3MzTFTte1CLHSSPl1lh8wYIKOS6lwHhZrQJw0U7bfvfn9XHQvwG7KbM5vyyWvL5w4IgWHlev0pzukD69IRMjCjYysDtn-l0JntyORQip4EXqSWar0rAX9KEUlInQq2KQmAkpBfQ7eC_OvGZ6Rhf5cpudvO6VDY6h2_Xs8W7AZRzVA86wgyt3mhuEnQo78r-8x4kw"
            />
          </div>
        </section>

        {/* Right Form Panel */}
        <section className="flex flex-col justify-center p-8 md:p-16 lg:p-24 bg-surface-container-lowest">
          <div className="w-full max-w-sm mx-auto">
            {/* Mobile logo */}
            <div className="md:hidden flex items-center gap-2 mb-10">
              <span className="material-symbols-outlined text-primary text-3xl">health_and_safety</span>
              <span className="font-headline text-xl font-extrabold text-primary">HealthFlow</span>
            </div>

            {/* Heading */}
            <div className="mb-10">
              <h2 className="font-headline text-3xl font-bold text-on-surface mb-2">
                {isRegisterMode ? 'Create Account' : 'Welcome Back'}
              </h2>
              <p className="text-on-surface-variant text-sm">
                {isRegisterMode
                  ? 'Set up your broker account to get started.'
                  : 'Please enter your credentials to access your portal.'}
              </p>
            </div>

            {/* Error message */}
            {error && (
              <div className="mb-6 p-4 bg-error-container rounded-xl">
                <p className="text-sm text-on-error-container">{error}</p>
              </div>
            )}

            {/* Form */}
            <form className="space-y-6" onSubmit={handleSubmit}>
              {isRegisterMode && (
                <div>
                  <label
                    className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2"
                    htmlFor="fullName"
                  >
                    Full Name
                  </label>
                  <div className="relative">
                    <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-outline text-lg">
                      person
                    </span>
                    <input
                      className="w-full pl-12 pr-4 py-3.5 bg-surface-container-highest rounded-xl border-none focus:ring-2 focus:ring-primary/20 focus:bg-surface-container-lowest transition-all text-on-surface placeholder:text-outline"
                      id="fullName"
                      name="fullName"
                      placeholder="Jane Smith"
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      required
                    />
                  </div>
                </div>
              )}

              <div>
                <label
                  className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2"
                  htmlFor="email"
                >
                  Email Address
                </label>
                <div className="relative">
                  <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-outline text-lg">
                    mail
                  </span>
                  <input
                    className="w-full pl-12 pr-4 py-3.5 bg-surface-container-highest rounded-xl border-none focus:ring-2 focus:ring-primary/20 focus:bg-surface-container-lowest transition-all text-on-surface placeholder:text-outline"
                    id="email"
                    name="email"
                    placeholder="broker@healthflow.com"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-2">
                  <label
                    className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider"
                    htmlFor="password"
                  >
                    Password
                  </label>
                  {!isRegisterMode && (
                    <a className="text-xs font-medium text-primary hover:text-primary-container transition-colors" href="#">
                      Forgot password?
                    </a>
                  )}
                </div>
                <div className="relative">
                  <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-outline text-lg">
                    lock
                  </span>
                  <input
                    className="w-full pl-12 pr-12 py-3.5 bg-surface-container-highest rounded-xl border-none focus:ring-2 focus:ring-primary/20 focus:bg-surface-container-lowest transition-all text-on-surface placeholder:text-outline"
                    id="password"
                    name="password"
                    placeholder="••••••••"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={8}
                  />
                  <button
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-outline hover:text-on-surface-variant transition-colors"
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    <span className="material-symbols-outlined text-lg">
                      {showPassword ? 'visibility_off' : 'visibility'}
                    </span>
                  </button>
                </div>
              </div>

              {!isRegisterMode && (
                <div className="flex items-center">
                  <input
                    className="w-4 h-4 text-primary bg-surface-container-highest border-none rounded focus:ring-primary focus:ring-offset-0"
                    id="remember"
                    name="remember"
                    type="checkbox"
                    checked={remember}
                    onChange={(e) => setRemember(e.target.checked)}
                  />
                  <label className="ml-3 text-sm text-on-surface-variant" htmlFor="remember">
                    Remember me for 30 days
                  </label>
                </div>
              )}

              <button
                className="w-full bg-primary hover:bg-primary-container text-on-primary font-semibold py-4 rounded-xl transition-all shadow-lg shadow-primary/20 flex items-center justify-center gap-2 group disabled:opacity-50 disabled:cursor-not-allowed"
                type="submit"
                disabled={loading}
              >
                {loading ? (
                  'Processing...'
                ) : (
                  <>
                    {isRegisterMode ? 'Create Account' : 'Sign In'}
                    <span className="material-symbols-outlined text-lg transition-transform group-hover:translate-x-1">
                      arrow_forward
                    </span>
                  </>
                )}
              </button>
            </form>

            {/* Toggle register/login */}
            <div className="mt-10 pt-10 border-t border-surface-container text-center">
              <p className="text-sm text-on-surface-variant">
                {isRegisterMode ? 'Already have an account?' : "Don't have a broker account yet?"}
              </p>
              <button
                className="inline-block mt-4 text-sm font-bold text-primary px-6 py-2 rounded-full border border-primary/20 hover:bg-primary/5 transition-all"
                onClick={() => {
                  setIsRegisterMode(!isRegisterMode)
                  setError('')
                }}
              >
                {isRegisterMode ? 'Sign In Instead' : 'Create a Broker Account'}
              </button>
            </div>

            {/* Security badges */}
            <div className="mt-12 flex justify-center gap-6">
              <div className="flex items-center gap-2 opacity-40">
                <span className="material-symbols-outlined text-[10px]">lock_outline</span>
                <span className="text-[10px] font-bold uppercase tracking-[0.2em]">SSL Secure</span>
              </div>
              <div className="flex items-center gap-2 opacity-40">
                <span className="material-symbols-outlined text-[10px]">verified_user</span>
                <span className="text-[10px] font-bold uppercase tracking-[0.2em]">HIPAA Compliant</span>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="fixed bottom-6 w-full text-center pointer-events-none">
        <p className="text-[10px] font-medium text-on-surface-variant/40 uppercase tracking-[0.3em]">
          &copy; 2024 HealthFlow Brokerage Technologies. All Rights Reserved.
        </p>
      </footer>
    </div>
  )
}
