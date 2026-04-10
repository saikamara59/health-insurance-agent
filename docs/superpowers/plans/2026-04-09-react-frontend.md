# React Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a React SPA with Login, Client Portfolio, and Client Profile pages matching Stitch designs, connected to the FastAPI backend via JWT auth.

**Architecture:** Vite + React 18 SPA with Tailwind CSS using the Stitch M3 color system. AuthContext manages JWT tokens. API client wraps fetch with auth headers. React Router v6 with protected routes. Three pages pixel-matching the Stitch designs.

**Tech Stack:** React 18, Vite, Tailwind CSS, React Router v6, Material Symbols Outlined

---

### Task 1: Vite + React Scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/App.jsx`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/index.css`
- Remove: `frontend/.gitkeep`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "healthflow-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.15",
    "@tailwindcss/forms": "^0.5.9",
    "vite": "^6.0.0"
  }
}
```

- [ ] **Step 2: Create `frontend/vite.config.js`**

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://localhost:8000',
      '/clients': 'http://localhost:8000',
      '/compare': 'http://localhost:8000',
      '/calculate': 'http://localhost:8000',
      '/translate': 'http://localhost:8000',
      '/appeal': 'http://localhost:8000',
      '/verify': 'http://localhost:8000',
      '/estimate': 'http://localhost:8000',
      '/plans': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    }
  }
})
```

- [ ] **Step 3: Create `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>HealthFlow Brokerage Portal</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Manrope:wght@600;700;800&display=swap" rel="stylesheet" />
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
  </head>
  <body class="bg-surface text-on-surface">
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 4: Create `frontend/tailwind.config.js`**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        "primary": "#006194",
        "primary-container": "#007bb9",
        "on-primary": "#ffffff",
        "on-primary-container": "#fdfcff",
        "primary-fixed": "#cce5ff",
        "primary-fixed-dim": "#93ccff",
        "on-primary-fixed": "#001d31",
        "on-primary-fixed-variant": "#004b73",
        "secondary": "#006a61",
        "secondary-container": "#86f2e4",
        "secondary-fixed": "#89f5e7",
        "secondary-fixed-dim": "#6bd8cb",
        "on-secondary": "#ffffff",
        "on-secondary-container": "#006f66",
        "on-secondary-fixed": "#00201d",
        "on-secondary-fixed-variant": "#005049",
        "tertiary": "#006195",
        "tertiary-container": "#287ab3",
        "tertiary-fixed": "#cde5ff",
        "tertiary-fixed-dim": "#94ccff",
        "on-tertiary": "#ffffff",
        "on-tertiary-container": "#fdfcff",
        "on-tertiary-fixed": "#001d32",
        "on-tertiary-fixed-variant": "#004b74",
        "error": "#ba1a1a",
        "error-container": "#ffdad6",
        "on-error": "#ffffff",
        "on-error-container": "#93000a",
        "surface": "#f7f9fb",
        "surface-dim": "#d8dadc",
        "surface-bright": "#f7f9fb",
        "surface-container": "#eceef0",
        "surface-container-low": "#f2f4f6",
        "surface-container-high": "#e6e8ea",
        "surface-container-highest": "#e0e3e5",
        "surface-container-lowest": "#ffffff",
        "surface-tint": "#006398",
        "surface-variant": "#e0e3e5",
        "on-surface": "#191c1e",
        "on-surface-variant": "#3f4850",
        "on-background": "#191c1e",
        "background": "#f7f9fb",
        "outline": "#707881",
        "outline-variant": "#bfc7d2",
        "inverse-surface": "#2d3133",
        "inverse-on-surface": "#eff1f3",
        "inverse-primary": "#93ccff",
      },
      fontFamily: {
        headline: ["Manrope", "sans-serif"],
        body: ["Inter", "sans-serif"],
        label: ["Inter", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "0.125rem",
        lg: "0.25rem",
        xl: "0.5rem",
        full: "0.75rem",
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
}
```

- [ ] **Step 5: Create `frontend/postcss.config.js`**

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 6: Create `frontend/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  font-family: 'Inter', sans-serif;
}

.font-headline {
  font-family: 'Manrope', sans-serif;
}

.material-symbols-outlined {
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
}
```

- [ ] **Step 7: Create `frontend/src/main.jsx`**

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

- [ ] **Step 8: Create `frontend/src/App.jsx`**

Placeholder to verify the scaffold works:

```jsx
export default function App() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <h1 className="font-headline text-3xl font-bold text-primary">
        HealthFlow
      </h1>
    </div>
  )
}
```

- [ ] **Step 9: Remove `frontend/.gitkeep`**

Delete the placeholder file:

```bash
rm frontend/.gitkeep
```

- [ ] **Step 10: Install dependencies and verify**

```bash
cd frontend && npm install && npm run dev &
```

Wait a moment, then open `http://localhost:5173` in a browser or use `curl http://localhost:5173` to confirm the dev server starts. Kill the background process after verifying.

Alternatively, verify the build compiles without errors:

```bash
cd frontend && npm run build
```

Confirm `frontend/dist/` is created with no errors. Add `frontend/dist/` and `frontend/node_modules/` to `.gitignore` if not already present.

- [ ] **Step 11: Commit**

Commit message: `feat(frontend): scaffold Vite + React + Tailwind project with M3 color system`

---

### Task 2: API Client + Auth Context

**Files:**
- Create: `frontend/src/api/client.js`
- Create: `frontend/src/contexts/AuthContext.jsx`

- [ ] **Step 1: Create `frontend/src/api/client.js`**

```javascript
const API_BASE_URL = ''

let _token = null
let _refreshToken = null

export function setToken(token) {
  _token = token
}

export function getToken() {
  return _token
}

export function setRefreshToken(token) {
  _refreshToken = token
}

export function getRefreshToken() {
  return _refreshToken
}

export function clearTokens() {
  _token = null
  _refreshToken = null
}

async function refreshAccessToken() {
  if (!_refreshToken) return false

  try {
    const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: _refreshToken }),
    })

    if (!res.ok) return false

    const data = await res.json()
    _token = data.access_token
    return true
  } catch {
    return false
  }
}

async function request(method, path, body = null) {
  const headers = { 'Content-Type': 'application/json' }

  if (_token) {
    headers['Authorization'] = `Bearer ${_token}`
  }

  const config = { method, headers }
  if (body !== null) {
    config.body = JSON.stringify(body)
  }

  let res = await fetch(`${API_BASE_URL}${path}`, config)

  // On 401, attempt token refresh and retry once
  if (res.status === 401 && _refreshToken) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      headers['Authorization'] = `Bearer ${_token}`
      res = await fetch(`${API_BASE_URL}${path}`, { method, headers, body: config.body })
    }
  }

  if (res.status === 401) {
    clearTokens()
    throw new Error('Unauthorized')
  }

  if (res.status === 204) {
    return null
  }

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}))
    const error = new Error(errorData.detail || `Request failed: ${res.status}`)
    error.status = res.status
    error.data = errorData
    throw error
  }

  return res.json()
}

const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  put: (path, body) => request('PUT', path, body),
  del: (path) => request('DELETE', path),
}

export default api
```

- [ ] **Step 2: Create `frontend/src/contexts/AuthContext.jsx`**

```jsx
import { createContext, useContext, useState, useCallback } from 'react'
import api, { setToken, setRefreshToken, clearTokens, getToken } from '../api/client'

const AuthContext = createContext(null)

function decodeTokenPayload(token) {
  try {
    const base64 = token.split('.')[1]
    const json = atob(base64)
    return JSON.parse(json)
  } catch {
    return null
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  const login = useCallback(async (email, password) => {
    try {
      const data = await api.post('/auth/login', { email, password })
      setToken(data.access_token)
      setRefreshToken(data.refresh_token)

      const payload = decodeTokenPayload(data.access_token)
      setUser({ id: payload?.sub, role: payload?.role, email })
      setIsAuthenticated(true)

      return { success: true }
    } catch (error) {
      return { success: false, error: error.message || 'Login failed' }
    }
  }, [])

  const register = useCallback(async (email, password, fullName) => {
    try {
      await api.post('/auth/register', { email, password, full_name: fullName })
      return { success: true }
    } catch (error) {
      return { success: false, error: error.message || 'Registration failed' }
    }
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
    setIsAuthenticated(false)
  }, [])

  const value = {
    user,
    isAuthenticated,
    login,
    register,
    logout,
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
```

- [ ] **Step 3: Verify**

Run `cd frontend && npm run build` and confirm no import or syntax errors.

- [ ] **Step 4: Commit**

Commit message: `feat(frontend): add API client with JWT auth and AuthContext provider`

---

### Task 3: Layout Components

**Files:**
- Create: `frontend/src/components/ProtectedRoute.jsx`
- Create: `frontend/src/components/Sidebar.jsx`
- Create: `frontend/src/components/TopBar.jsx`
- Create: `frontend/src/components/Layout.jsx`

- [ ] **Step 1: Create `frontend/src/components/ProtectedRoute.jsx`**

```jsx
import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return children
}
```

- [ ] **Step 2: Create `frontend/src/components/Sidebar.jsx`**

```jsx
import { NavLink } from 'react-router-dom'

const navItems = [
  { icon: 'dashboard', label: 'Dashboard', path: '/' },
  { icon: 'group', label: 'Clients', path: '/' },
  { icon: 'history', label: 'History', path: '#' },
  { icon: 'settings', label: 'Settings', path: '#' },
]

const footerItems = [
  { icon: 'support_agent', label: 'Support' },
  { icon: 'account_circle', label: 'Account' },
]

export default function Sidebar() {
  return (
    <aside className="w-64 bg-surface-container-lowest border-r border-outline-variant flex flex-col min-h-screen">
      {/* Logo */}
      <div className="p-6 flex items-center gap-3">
        <div className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
          <span className="material-symbols-outlined text-on-primary text-xl">health_and_safety</span>
        </div>
        <span className="font-headline text-xl font-extrabold text-on-surface tracking-tight">HealthFlow</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 mt-4">
        <ul className="space-y-1">
          {navItems.map((item) => (
            <li key={item.label}>
              <NavLink
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-colors ${
                    isActive && item.path !== '#'
                      ? 'bg-primary/10 text-primary'
                      : 'text-on-surface-variant hover:bg-surface-container-high'
                  }`
                }
              >
                <span className="material-symbols-outlined text-xl">{item.icon}</span>
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* Footer */}
      <div className="px-4 pb-6 space-y-1">
        {footerItems.map((item) => (
          <button
            key={item.label}
            className="flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-on-surface-variant hover:bg-surface-container-high w-full text-left transition-colors"
          >
            <span className="material-symbols-outlined text-xl">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </div>
    </aside>
  )
}
```

- [ ] **Step 3: Create `frontend/src/components/TopBar.jsx`**

```jsx
import { useAuth } from '../contexts/AuthContext'

export default function TopBar() {
  const { user, logout } = useAuth()

  return (
    <header className="h-16 bg-surface-container-lowest border-b border-outline-variant flex items-center justify-between px-8">
      {/* Search */}
      <div className="relative w-96">
        <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-lg">search</span>
        <input
          type="text"
          placeholder="Search clients, plans, or analyses..."
          className="w-full pl-10 pr-4 py-2 bg-surface-container-high rounded-xl border-none text-sm text-on-surface placeholder:text-outline focus:ring-2 focus:ring-primary/20"
        />
      </div>

      {/* Right actions */}
      <div className="flex items-center gap-4">
        {/* Notification bell */}
        <button className="relative p-2 rounded-xl hover:bg-surface-container-high transition-colors">
          <span className="material-symbols-outlined text-on-surface-variant">notifications</span>
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-error rounded-full"></span>
        </button>

        {/* Help */}
        <button className="p-2 rounded-xl hover:bg-surface-container-high transition-colors">
          <span className="material-symbols-outlined text-on-surface-variant">help_outline</span>
        </button>

        {/* User avatar */}
        <button
          onClick={logout}
          className="flex items-center gap-3 pl-3 pr-4 py-1.5 rounded-xl hover:bg-surface-container-high transition-colors"
        >
          <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center">
            <span className="text-on-primary text-xs font-bold">
              {user?.email?.charAt(0)?.toUpperCase() || 'B'}
            </span>
          </div>
          <div className="text-left">
            <p className="text-sm font-medium text-on-surface">{user?.email || 'Broker'}</p>
            <p className="text-xs text-on-surface-variant">{user?.role || 'broker'}</p>
          </div>
        </button>
      </div>
    </header>
  )
}
```

- [ ] **Step 4: Create `frontend/src/components/Layout.jsx`**

```jsx
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-surface">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <TopBar />
        <main className="flex-1 p-8 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Verify**

Run `cd frontend && npm run build` and confirm no errors.

- [ ] **Step 6: Commit**

Commit message: `feat(frontend): add layout components — Sidebar, TopBar, ProtectedRoute, Layout shell`

---

### Task 4: App Router

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Update `frontend/src/App.jsx`**

Replace the entire contents with:

```jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import ClientListPage from './pages/ClientListPage'
import ClientProfilePage from './pages/ClientProfilePage'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<ClientListPage />} />
            <Route path="clients/:id" element={<ClientProfilePage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
```

- [ ] **Step 2: Create placeholder pages**

Create these three placeholder files so the router resolves without errors. They will be replaced in Tasks 5, 6, and 7.

`frontend/src/pages/LoginPage.jsx`:
```jsx
export default function LoginPage() {
  return <div className="p-8"><h1 className="font-headline text-2xl">Login</h1></div>
}
```

`frontend/src/pages/ClientListPage.jsx`:
```jsx
export default function ClientListPage() {
  return <div><h1 className="font-headline text-2xl">Client Portfolio</h1></div>
}
```

`frontend/src/pages/ClientProfilePage.jsx`:
```jsx
export default function ClientProfilePage() {
  return <div><h1 className="font-headline text-2xl">Client Profile</h1></div>
}
```

- [ ] **Step 3: Verify**

Run `cd frontend && npm run build` and confirm no errors. Optionally run the dev server and confirm:
- Visiting `/` redirects to `/login` (since not authenticated)
- `/login` renders the placeholder

- [ ] **Step 4: Commit**

Commit message: `feat(frontend): wire up React Router with auth-guarded routes`

---

### Task 5: Login Page

**Files:**
- Modify: `frontend/src/pages/LoginPage.jsx`

**Reference:** Read `docs/designs/login-screen-stitch.html` and translate the HTML to React JSX. Use the exact same Tailwind classes from the Stitch HTML.

- [ ] **Step 1: Replace `frontend/src/pages/LoginPage.jsx`**

Replace the entire file with:

```jsx
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
                    placeholder="&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;"
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
```

- [ ] **Step 2: Verify**

Run `cd frontend && npm run build` and confirm no errors. Optionally start the dev server and visit `/login` to see the full split-panel login page.

- [ ] **Step 3: Commit**

Commit message: `feat(frontend): implement Login page pixel-matching Stitch design`

---

### Task 6: Client List Page

**Files:**
- Modify: `frontend/src/pages/ClientListPage.jsx`

**Backend API reference:**
- `GET /clients` returns `[{ id, broker_id, full_name, zip_code, age, income_level, doctors, prescriptions, procedures, created_at, updated_at }]`
- `POST /clients` body: `{ full_name, zip_code, age, income_level, doctors?, prescriptions?, procedures? }`
- `DELETE /clients/{id}` returns 204

- [ ] **Step 1: Replace `frontend/src/pages/ClientListPage.jsx`**

Replace the entire file with:

```jsx
import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'

function getInitials(name) {
  return name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

const AVATAR_COLORS = [
  'bg-primary', 'bg-secondary', 'bg-tertiary',
  'bg-primary-container', 'bg-tertiary-container',
]

function avatarColor(name) {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]
}

const INCOME_LABELS = { low: 'Low', medium: 'Medium', high: 'High' }

const PAGE_SIZE = 10

export default function ClientListPage() {
  const navigate = useNavigate()

  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Filters
  const [filterZip, setFilterZip] = useState('')
  const [filterAge, setFilterAge] = useState('')
  const [filterIncome, setFilterIncome] = useState('')
  const [appliedFilters, setAppliedFilters] = useState({ zip: '', age: '', income: '' })

  // Pagination
  const [page, setPage] = useState(1)

  // Add Client modal
  const [showAddModal, setShowAddModal] = useState(false)
  const [newClient, setNewClient] = useState({
    full_name: '', zip_code: '', age: '', income_level: 'medium',
  })
  const [addError, setAddError] = useState('')
  const [addLoading, setAddLoading] = useState(false)

  useEffect(() => {
    loadClients()
  }, [])

  async function loadClients() {
    setLoading(true)
    try {
      const data = await api.get('/clients')
      setClients(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const filteredClients = useMemo(() => {
    return clients.filter((c) => {
      if (appliedFilters.zip && !c.zip_code.startsWith(appliedFilters.zip)) return false
      if (appliedFilters.income && c.income_level !== appliedFilters.income) return false
      if (appliedFilters.age) {
        const [min, max] = appliedFilters.age.split('-').map(Number)
        if (c.age < min || c.age > max) return false
      }
      return true
    })
  }, [clients, appliedFilters])

  const totalPages = Math.max(1, Math.ceil(filteredClients.length / PAGE_SIZE))
  const pagedClients = filteredClients.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  function applyFilters() {
    setAppliedFilters({ zip: filterZip, age: filterAge, income: filterIncome })
    setPage(1)
  }

  async function handleAddClient(e) {
    e.preventDefault()
    setAddError('')
    setAddLoading(true)
    try {
      await api.post('/clients', {
        full_name: newClient.full_name,
        zip_code: newClient.zip_code,
        age: parseInt(newClient.age, 10),
        income_level: newClient.income_level,
      })
      setShowAddModal(false)
      setNewClient({ full_name: '', zip_code: '', age: '', income_level: 'medium' })
      await loadClients()
    } catch (err) {
      setAddError(err.message)
    } finally {
      setAddLoading(false)
    }
  }

  async function handleDeleteClient(id) {
    if (!confirm('Delete this client?')) return
    try {
      await api.del(`/clients/${id}`)
      setClients((prev) => prev.filter((c) => c.id !== id))
    } catch (err) {
      alert(err.message)
    }
  }

  // Summary stats (derived)
  const newLeadsCount = clients.filter((c) => {
    const created = new Date(c.created_at)
    const weekAgo = new Date()
    weekAgo.setDate(weekAgo.getDate() - 7)
    return created >= weekAgo
  }).length

  return (
    <div>
      {/* Page Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-headline text-3xl font-bold text-on-surface">Client Portfolio</h1>
          <p className="text-on-surface-variant text-sm mt-1">{clients.length} total clients</p>
        </div>
        <button
          className="flex items-center gap-2 bg-primary hover:bg-primary-container text-on-primary font-semibold px-6 py-3 rounded-xl transition-colors shadow-sm"
          onClick={() => setShowAddModal(true)}
        >
          <span className="material-symbols-outlined text-lg">add</span>
          Add Client
        </button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-surface-container-lowest rounded-xl p-6 border border-outline-variant">
          <div className="flex items-center gap-3 mb-2">
            <span className="material-symbols-outlined text-primary text-2xl">person_add</span>
            <span className="text-sm font-medium text-on-surface-variant">New Leads (7d)</span>
          </div>
          <p className="text-3xl font-bold text-on-surface font-headline">{newLeadsCount}</p>
        </div>
        <div className="bg-surface-container-lowest rounded-xl p-6 border border-outline-variant">
          <div className="flex items-center gap-3 mb-2">
            <span className="material-symbols-outlined text-secondary text-2xl">analytics</span>
            <span className="text-sm font-medium text-on-surface-variant">Analysis Score Avg</span>
          </div>
          <p className="text-3xl font-bold text-on-surface font-headline">--</p>
        </div>
        <div className="bg-surface-container-lowest rounded-xl p-6 border border-outline-variant">
          <div className="flex items-center gap-3 mb-2">
            <span className="material-symbols-outlined text-error text-2xl">warning</span>
            <span className="text-sm font-medium text-on-surface-variant">Urgent Renewals</span>
          </div>
          <p className="text-3xl font-bold text-on-surface font-headline">--</p>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-surface-container-lowest rounded-xl p-6 border border-outline-variant mb-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
              Zip Code
            </label>
            <input
              type="text"
              placeholder="e.g. 90210"
              className="w-full px-4 py-2.5 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface placeholder:text-outline focus:ring-2 focus:ring-primary/20"
              value={filterZip}
              onChange={(e) => setFilterZip(e.target.value)}
              maxLength={5}
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
              Age Range
            </label>
            <select
              className="w-full px-4 py-2.5 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface focus:ring-2 focus:ring-primary/20"
              value={filterAge}
              onChange={(e) => setFilterAge(e.target.value)}
            >
              <option value="">All Ages</option>
              <option value="18-30">18-30</option>
              <option value="31-45">31-45</option>
              <option value="46-60">46-60</option>
              <option value="61-120">61+</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
              Income Level
            </label>
            <select
              className="w-full px-4 py-2.5 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface focus:ring-2 focus:ring-primary/20"
              value={filterIncome}
              onChange={(e) => setFilterIncome(e.target.value)}
            >
              <option value="">All Incomes</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
          <div className="flex items-end">
            <button
              className="w-full bg-primary hover:bg-primary-container text-on-primary font-semibold py-2.5 rounded-xl transition-colors text-sm"
              onClick={applyFilters}
            >
              Apply Filters
            </button>
          </div>
        </div>
      </div>

      {/* Client Table */}
      <div className="bg-surface-container-lowest rounded-xl border border-outline-variant overflow-hidden">
        {loading ? (
          <div className="p-12 text-center">
            <span className="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
            <p className="text-on-surface-variant text-sm mt-4">Loading clients...</p>
          </div>
        ) : error ? (
          <div className="p-12 text-center">
            <p className="text-error text-sm">{error}</p>
          </div>
        ) : filteredClients.length === 0 ? (
          <div className="p-12 text-center">
            <span className="material-symbols-outlined text-4xl text-outline mb-2">group_off</span>
            <p className="text-on-surface-variant text-sm">No clients found. Add your first client to get started.</p>
          </div>
        ) : (
          <>
            <table className="w-full">
              <thead>
                <tr className="border-b border-outline-variant bg-surface-container-low">
                  <th className="text-left px-6 py-4 text-xs font-semibold text-on-surface-variant uppercase tracking-wider">Name</th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-on-surface-variant uppercase tracking-wider">Zip Code</th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-on-surface-variant uppercase tracking-wider">Age</th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-on-surface-variant uppercase tracking-wider">Income</th>
                  <th className="text-left px-6 py-4 text-xs font-semibold text-on-surface-variant uppercase tracking-wider">Created</th>
                  <th className="text-right px-6 py-4 text-xs font-semibold text-on-surface-variant uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pagedClients.map((client) => (
                  <tr
                    key={client.id}
                    className="border-b border-outline-variant last:border-b-0 hover:bg-surface-container-low transition-colors group"
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-9 h-9 rounded-full flex items-center justify-center text-on-primary text-xs font-bold ${avatarColor(client.full_name)}`}>
                          {getInitials(client.full_name)}
                        </div>
                        <span className="text-sm font-medium text-on-surface">{client.full_name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-on-surface-variant">{client.zip_code}</td>
                    <td className="px-6 py-4 text-sm text-on-surface-variant">{client.age}</td>
                    <td className="px-6 py-4">
                      <span className="inline-block px-3 py-1 text-xs font-medium rounded-full bg-surface-container-high text-on-surface-variant">
                        {INCOME_LABELS[client.income_level] || client.income_level}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-on-surface-variant">
                      {new Date(client.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          className="p-2 rounded-lg hover:bg-surface-container-high transition-colors"
                          title="View Profile"
                          onClick={() => navigate(`/clients/${client.id}`)}
                        >
                          <span className="material-symbols-outlined text-lg text-primary">person</span>
                        </button>
                        <button
                          className="p-2 rounded-lg hover:bg-surface-container-high transition-colors"
                          title="Run Analysis"
                          onClick={() => navigate(`/clients/${client.id}`)}
                        >
                          <span className="material-symbols-outlined text-lg text-secondary">analytics</span>
                        </button>
                        <button
                          className="p-2 rounded-lg hover:bg-error-container transition-colors"
                          title="Delete"
                          onClick={() => handleDeleteClient(client.id)}
                        >
                          <span className="material-symbols-outlined text-lg text-error">delete</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            <div className="flex items-center justify-between px-6 py-4 border-t border-outline-variant bg-surface-container-low">
              <p className="text-sm text-on-surface-variant">
                Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, filteredClients.length)} of {filteredClients.length}
              </p>
              <div className="flex items-center gap-2">
                <button
                  className="p-2 rounded-lg hover:bg-surface-container-high transition-colors disabled:opacity-30"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  <span className="material-symbols-outlined text-lg text-on-surface-variant">chevron_left</span>
                </button>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                  <button
                    key={p}
                    className={`w-8 h-8 rounded-lg text-sm font-medium transition-colors ${
                      p === page
                        ? 'bg-primary text-on-primary'
                        : 'hover:bg-surface-container-high text-on-surface-variant'
                    }`}
                    onClick={() => setPage(p)}
                  >
                    {p}
                  </button>
                ))}
                <button
                  className="p-2 rounded-lg hover:bg-surface-container-high transition-colors disabled:opacity-30"
                  disabled={page >= totalPages}
                  onClick={() => setPage(page + 1)}
                >
                  <span className="material-symbols-outlined text-lg text-on-surface-variant">chevron_right</span>
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Add Client Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-surface-container-lowest rounded-xl w-full max-w-lg shadow-xl">
            <div className="flex items-center justify-between px-8 py-6 border-b border-outline-variant">
              <h2 className="font-headline text-xl font-bold text-on-surface">Add New Client</h2>
              <button
                className="p-2 rounded-lg hover:bg-surface-container-high transition-colors"
                onClick={() => { setShowAddModal(false); setAddError('') }}
              >
                <span className="material-symbols-outlined text-on-surface-variant">close</span>
              </button>
            </div>

            <form className="p-8 space-y-5" onSubmit={handleAddClient}>
              {addError && (
                <div className="p-4 bg-error-container rounded-xl">
                  <p className="text-sm text-on-error-container">{addError}</p>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
                  Full Name
                </label>
                <input
                  type="text"
                  className="w-full px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface placeholder:text-outline focus:ring-2 focus:ring-primary/20"
                  placeholder="John Doe"
                  value={newClient.full_name}
                  onChange={(e) => setNewClient({ ...newClient, full_name: e.target.value })}
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
                    Zip Code
                  </label>
                  <input
                    type="text"
                    className="w-full px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface placeholder:text-outline focus:ring-2 focus:ring-primary/20"
                    placeholder="90210"
                    value={newClient.zip_code}
                    onChange={(e) => setNewClient({ ...newClient, zip_code: e.target.value })}
                    required
                    maxLength={5}
                    pattern="\d{5}"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
                    Age
                  </label>
                  <input
                    type="number"
                    className="w-full px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface placeholder:text-outline focus:ring-2 focus:ring-primary/20"
                    placeholder="35"
                    value={newClient.age}
                    onChange={(e) => setNewClient({ ...newClient, age: e.target.value })}
                    required
                    min={18}
                    max={120}
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
                  Income Level
                </label>
                <select
                  className="w-full px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface focus:ring-2 focus:ring-primary/20"
                  value={newClient.income_level}
                  onChange={(e) => setNewClient({ ...newClient, income_level: e.target.value })}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  className="flex-1 py-3 rounded-xl border border-outline-variant text-on-surface-variant font-medium text-sm hover:bg-surface-container-high transition-colors"
                  onClick={() => { setShowAddModal(false); setAddError('') }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 py-3 rounded-xl bg-primary text-on-primary font-semibold text-sm hover:bg-primary-container transition-colors disabled:opacity-50"
                  disabled={addLoading}
                >
                  {addLoading ? 'Creating...' : 'Add Client'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify**

Run `cd frontend && npm run build` and confirm no errors.

- [ ] **Step 3: Commit**

Commit message: `feat(frontend): implement Client Portfolio page with filters, table, pagination, and add modal`

---

### Task 7: Client Profile Page

**Files:**
- Modify: `frontend/src/pages/ClientProfilePage.jsx`

**Backend API reference:**
- `GET /clients/{id}` returns `{ id, broker_id, full_name, zip_code, age, income_level, doctors, prescriptions, procedures, created_at, updated_at }`
- `PUT /clients/{id}` body: `{ full_name?, zip_code?, age?, income_level?, doctors?, prescriptions?, procedures? }`
- `POST /translate` body: `{ document_text }` — extract SoB data
- `POST /verify` body: `{ doctors, prescriptions, zip_code }` — network verification
- `POST /calculate` body: `{ age, zip_code, income_level, prescriptions, procedures }` — risk calculation
- `POST /compare` body: `{ zip_code, age, income_level, prescriptions, procedures, doctors }` — marketplace comparison
- `POST /estimate` body: `{ zip_code, age, income_level, prescriptions, procedures, doctors }` — cost estimation

- [ ] **Step 1: Replace `frontend/src/pages/ClientProfilePage.jsx`**

Replace the entire file with:

```jsx
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../api/client'

const TABS = ['Plan Analysis', 'Profile Details', 'Prescriptions', 'Preferred Doctors']

const WORKFLOW_STEPS = [
  {
    number: 1,
    title: 'Extract Data',
    description: 'Parse and translate Summary of Benefits documents into structured data.',
    icon: 'description',
    endpoint: '/translate',
    buildPayload: (client) => ({
      document_text: `Summary of Benefits for ${client.full_name}, age ${client.age}, zip ${client.zip_code}, income ${client.income_level}. Prescriptions: ${client.prescriptions.join(', ') || 'none'}. Procedures: ${client.procedures.join(', ') || 'none'}.`,
    }),
  },
  {
    number: 2,
    title: 'Verify Networks',
    description: 'Scrape provider directories to verify doctor and pharmacy network status.',
    icon: 'verified',
    endpoint: '/verify',
    buildPayload: (client) => ({
      doctors: client.doctors || [],
      prescriptions: client.prescriptions || [],
      zip_code: client.zip_code,
    }),
  },
  {
    number: 3,
    title: 'Calculate Risks',
    description: 'Categorize health risk levels and project utilization patterns.',
    icon: 'calculate',
    endpoint: '/calculate',
    buildPayload: (client) => ({
      age: client.age,
      zip_code: client.zip_code,
      income_level: client.income_level,
      prescriptions: client.prescriptions || [],
      procedures: client.procedures || [],
    }),
  },
  {
    number: 4,
    title: 'Compare Plans',
    description: 'Search marketplace for available plans and rank by total cost.',
    icon: 'compare_arrows',
    endpoint: '/compare',
    buildPayload: (client) => ({
      zip_code: client.zip_code,
      age: client.age,
      income_level: client.income_level,
      prescriptions: client.prescriptions || [],
      procedures: client.procedures || [],
      doctors: client.doctors || [],
    }),
  },
  {
    number: 5,
    title: 'Cost Estimate',
    description: 'Generate final cost breakdown with out-of-pocket projections.',
    icon: 'payments',
    endpoint: '/estimate',
    buildPayload: (client) => ({
      zip_code: client.zip_code,
      age: client.age,
      income_level: client.income_level,
      prescriptions: client.prescriptions || [],
      procedures: client.procedures || [],
      doctors: client.doctors || [],
    }),
  },
]

function getInitials(name) {
  return name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)
}

export default function ClientProfilePage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [client, setClient] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState(0)

  // Workflow state
  const [stepStatuses, setStepStatuses] = useState({})
  const [stepResults, setStepResults] = useState({})
  const [stepLoading, setStepLoading] = useState({})

  // Profile edit state
  const [editForm, setEditForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState('')

  // Prescriptions state
  const [newPrescription, setNewPrescription] = useState('')

  // Doctors state
  const [newDoctor, setNewDoctor] = useState({ name: '', npi: '' })

  useEffect(() => {
    loadClient()
  }, [id])

  async function loadClient() {
    setLoading(true)
    try {
      const data = await api.get(`/clients/${id}`)
      setClient(data)
      setEditForm({
        full_name: data.full_name,
        zip_code: data.zip_code,
        age: data.age,
        income_level: data.income_level,
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function runStep(stepIndex) {
    const step = WORKFLOW_STEPS[stepIndex]
    setStepLoading((prev) => ({ ...prev, [stepIndex]: true }))

    try {
      const payload = step.buildPayload(client)
      const result = await api.post(step.endpoint, payload)
      setStepResults((prev) => ({ ...prev, [stepIndex]: result }))
      setStepStatuses((prev) => ({ ...prev, [stepIndex]: 'complete' }))
    } catch (err) {
      setStepResults((prev) => ({ ...prev, [stepIndex]: { error: err.message } }))
      setStepStatuses((prev) => ({ ...prev, [stepIndex]: 'error' }))
    } finally {
      setStepLoading((prev) => ({ ...prev, [stepIndex]: false }))
    }
  }

  async function handleSaveProfile(e) {
    e.preventDefault()
    setSaving(true)
    setSaveMessage('')
    try {
      const updated = await api.put(`/clients/${id}`, {
        full_name: editForm.full_name,
        zip_code: editForm.zip_code,
        age: parseInt(editForm.age, 10),
        income_level: editForm.income_level,
      })
      setClient(updated)
      setSaveMessage('Profile saved successfully.')
    } catch (err) {
      setSaveMessage(`Error: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  async function addPrescription() {
    if (!newPrescription.trim()) return
    const updated = [...(client.prescriptions || []), newPrescription.trim()]
    try {
      const result = await api.put(`/clients/${id}`, { prescriptions: updated })
      setClient(result)
      setNewPrescription('')
    } catch (err) {
      alert(err.message)
    }
  }

  async function removePrescription(index) {
    const updated = client.prescriptions.filter((_, i) => i !== index)
    try {
      const result = await api.put(`/clients/${id}`, { prescriptions: updated })
      setClient(result)
    } catch (err) {
      alert(err.message)
    }
  }

  async function addDoctor() {
    if (!newDoctor.name.trim()) return
    const updated = [...(client.doctors || []), { name: newDoctor.name.trim(), npi: newDoctor.npi.trim() }]
    try {
      const result = await api.put(`/clients/${id}`, { doctors: updated })
      setClient(result)
      setNewDoctor({ name: '', npi: '' })
    } catch (err) {
      alert(err.message)
    }
  }

  async function removeDoctor(index) {
    const updated = client.doctors.filter((_, i) => i !== index)
    try {
      const result = await api.put(`/clients/${id}`, { doctors: updated })
      setClient(result)
    } catch (err) {
      alert(err.message)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <span className="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
      </div>
    )
  }

  if (error || !client) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px]">
        <span className="material-symbols-outlined text-4xl text-error mb-4">error</span>
        <p className="text-error text-sm">{error || 'Client not found'}</p>
        <button
          className="mt-4 text-sm text-primary font-medium hover:underline"
          onClick={() => navigate('/')}
        >
          Back to Portfolio
        </button>
      </div>
    )
  }

  return (
    <div>
      {/* Client Header */}
      <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-8 mb-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-6">
            <div className="w-16 h-16 bg-primary rounded-2xl flex items-center justify-center">
              <span className="text-on-primary text-xl font-bold">{getInitials(client.full_name)}</span>
            </div>
            <div>
              <h1 className="font-headline text-2xl font-bold text-on-surface">{client.full_name}</h1>
              <div className="flex items-center gap-4 mt-2 text-sm text-on-surface-variant">
                <span className="flex items-center gap-1">
                  <span className="material-symbols-outlined text-base">cake</span>
                  Age {client.age}
                </span>
                <span className="flex items-center gap-1">
                  <span className="material-symbols-outlined text-base">attach_money</span>
                  {client.income_level.charAt(0).toUpperCase() + client.income_level.slice(1)} Income
                </span>
                <span className="flex items-center gap-1">
                  <span className="material-symbols-outlined text-base">location_on</span>
                  {client.zip_code}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-secondary-container text-on-secondary-container text-sm font-medium">
              <span className="material-symbols-outlined text-sm">check_circle</span>
              Active Client
            </span>
            <button
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl border border-outline-variant text-on-surface-variant font-medium text-sm hover:bg-surface-container-high transition-colors"
              onClick={() => setActiveTab(1)}
            >
              <span className="material-symbols-outlined text-lg">edit</span>
              Edit Profile
            </button>
            <button
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-on-primary font-semibold text-sm hover:bg-primary-container transition-colors"
              onClick={() => {
                // Navigate or open appeal generation
              }}
            >
              <span className="material-symbols-outlined text-lg">gavel</span>
              Generate Appeal Draft
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-surface-container-low rounded-xl p-1">
        {TABS.map((tab, i) => (
          <button
            key={tab}
            className={`flex-1 py-3 px-4 rounded-xl text-sm font-medium transition-colors ${
              activeTab === i
                ? 'bg-surface-container-lowest text-primary shadow-sm'
                : 'text-on-surface-variant hover:text-on-surface'
            }`}
            onClick={() => setActiveTab(i)}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 0 && (
        <div>
          {/* Analysis Workflow */}
          <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-8 mb-6">
            <h2 className="font-headline text-xl font-bold text-on-surface mb-6">Analysis Workflow</h2>

            <div className="space-y-4">
              {WORKFLOW_STEPS.map((step, index) => {
                const status = stepStatuses[index]
                const isRunning = stepLoading[index]
                const result = stepResults[index]

                return (
                  <div key={index} className="border border-outline-variant rounded-xl p-6">
                    <div className="flex items-start gap-4">
                      {/* Step number circle */}
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                        status === 'complete'
                          ? 'bg-secondary text-on-secondary'
                          : status === 'error'
                            ? 'bg-error text-on-error'
                            : 'bg-surface-container-high text-on-surface-variant'
                      }`}>
                        {status === 'complete' ? (
                          <span className="material-symbols-outlined text-lg">check</span>
                        ) : (
                          <span className="text-sm font-bold">{step.number}</span>
                        )}
                      </div>

                      {/* Step content */}
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-1">
                          <h3 className="text-base font-semibold text-on-surface">{step.title}</h3>
                          {status === 'complete' && (
                            <span className="px-2.5 py-0.5 text-xs font-medium rounded-full bg-secondary-container text-on-secondary-container">
                              Complete
                            </span>
                          )}
                          {status === 'error' && (
                            <span className="px-2.5 py-0.5 text-xs font-medium rounded-full bg-error-container text-on-error-container">
                              Error
                            </span>
                          )}
                          {isRunning && (
                            <span className="px-2.5 py-0.5 text-xs font-medium rounded-full bg-primary-fixed text-on-primary-fixed">
                              In Progress
                            </span>
                          )}
                          {!status && !isRunning && (
                            <span className="px-2.5 py-0.5 text-xs font-medium rounded-full bg-surface-container-high text-on-surface-variant">
                              Pending
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-on-surface-variant mb-3">{step.description}</p>

                        <button
                          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-on-primary text-sm font-medium hover:bg-primary-container transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                          onClick={() => runStep(index)}
                          disabled={isRunning}
                        >
                          {isRunning ? (
                            <>
                              <span className="material-symbols-outlined text-sm animate-spin">progress_activity</span>
                              Running...
                            </>
                          ) : (
                            <>
                              <span className="material-symbols-outlined text-sm">{step.icon}</span>
                              {status === 'complete' ? 'Re-run' : 'Run'}
                            </>
                          )}
                        </button>

                        {/* Result display */}
                        {result && (
                          <div className={`mt-4 p-4 rounded-xl text-sm ${
                            result.error
                              ? 'bg-error-container text-on-error-container'
                              : 'bg-surface-container-low text-on-surface'
                          }`}>
                            <pre className="whitespace-pre-wrap font-body text-xs overflow-auto max-h-64">
                              {JSON.stringify(result, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-6">
              <div className="flex items-center gap-3 mb-3">
                <span className="material-symbols-outlined text-primary text-2xl">payments</span>
                <h3 className="text-sm font-semibold text-on-surface-variant uppercase tracking-wider">Annual Out-of-Pocket</h3>
              </div>
              <p className="text-3xl font-bold text-on-surface font-headline">
                {stepResults[4]?.estimated_annual_cost
                  ? `$${Number(stepResults[4].estimated_annual_cost).toLocaleString()}`
                  : '--'}
              </p>
              <p className="text-xs text-on-surface-variant mt-1">Run cost estimate to calculate</p>
            </div>
            <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-6">
              <div className="flex items-center gap-3 mb-3">
                <span className="material-symbols-outlined text-secondary text-2xl">savings</span>
                <h3 className="text-sm font-semibold text-on-surface-variant uppercase tracking-wider">Projected Savings</h3>
              </div>
              <p className="text-3xl font-bold text-on-surface font-headline">
                {stepResults[3]?.potential_savings
                  ? `$${Number(stepResults[3].potential_savings).toLocaleString()}`
                  : '--'}
              </p>
              <p className="text-xs text-on-surface-variant mt-1">Run plan comparison to calculate</p>
            </div>
          </div>
        </div>
      )}

      {activeTab === 1 && editForm && (
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-8">
          <h2 className="font-headline text-xl font-bold text-on-surface mb-6">Profile Details</h2>

          {saveMessage && (
            <div className={`mb-6 p-4 rounded-xl ${
              saveMessage.startsWith('Error')
                ? 'bg-error-container text-on-error-container'
                : 'bg-secondary-container text-on-secondary-container'
            }`}>
              <p className="text-sm">{saveMessage}</p>
            </div>
          )}

          <form className="space-y-5 max-w-lg" onSubmit={handleSaveProfile}>
            <div>
              <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
                Full Name
              </label>
              <input
                type="text"
                className="w-full px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface focus:ring-2 focus:ring-primary/20"
                value={editForm.full_name}
                onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
                  Zip Code
                </label>
                <input
                  type="text"
                  className="w-full px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface focus:ring-2 focus:ring-primary/20"
                  value={editForm.zip_code}
                  onChange={(e) => setEditForm({ ...editForm, zip_code: e.target.value })}
                  required
                  maxLength={5}
                  pattern="\d{5}"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
                  Age
                </label>
                <input
                  type="number"
                  className="w-full px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface focus:ring-2 focus:ring-primary/20"
                  value={editForm.age}
                  onChange={(e) => setEditForm({ ...editForm, age: e.target.value })}
                  required
                  min={18}
                  max={120}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
                Income Level
              </label>
              <select
                className="w-full px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface focus:ring-2 focus:ring-primary/20"
                value={editForm.income_level}
                onChange={(e) => setEditForm({ ...editForm, income_level: e.target.value })}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </div>

            <button
              type="submit"
              className="flex items-center gap-2 bg-primary hover:bg-primary-container text-on-primary font-semibold px-6 py-3 rounded-xl transition-colors disabled:opacity-50"
              disabled={saving}
            >
              <span className="material-symbols-outlined text-lg">save</span>
              {saving ? 'Saving...' : 'Save Profile'}
            </button>
          </form>
        </div>
      )}

      {activeTab === 2 && (
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-8">
          <h2 className="font-headline text-xl font-bold text-on-surface mb-6">Prescriptions</h2>

          {/* Add prescription */}
          <div className="flex gap-3 mb-6">
            <input
              type="text"
              className="flex-1 px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface placeholder:text-outline focus:ring-2 focus:ring-primary/20"
              placeholder="Enter prescription name"
              value={newPrescription}
              onChange={(e) => setNewPrescription(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addPrescription())}
            />
            <button
              className="flex items-center gap-2 px-5 py-3 bg-primary text-on-primary font-semibold rounded-xl hover:bg-primary-container transition-colors text-sm"
              onClick={addPrescription}
            >
              <span className="material-symbols-outlined text-lg">add</span>
              Add
            </button>
          </div>

          {/* Prescription list */}
          {(!client.prescriptions || client.prescriptions.length === 0) ? (
            <p className="text-sm text-on-surface-variant">No prescriptions added yet.</p>
          ) : (
            <ul className="space-y-2">
              {client.prescriptions.map((rx, i) => (
                <li key={i} className="flex items-center justify-between px-4 py-3 bg-surface-container-low rounded-xl">
                  <div className="flex items-center gap-3">
                    <span className="material-symbols-outlined text-primary text-lg">medication</span>
                    <span className="text-sm font-medium text-on-surface">{rx}</span>
                  </div>
                  <button
                    className="p-1.5 rounded-lg hover:bg-error-container transition-colors"
                    onClick={() => removePrescription(i)}
                  >
                    <span className="material-symbols-outlined text-lg text-error">close</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {activeTab === 3 && (
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-8">
          <h2 className="font-headline text-xl font-bold text-on-surface mb-6">Preferred Doctors</h2>

          {/* Add doctor */}
          <div className="flex gap-3 mb-6">
            <input
              type="text"
              className="flex-1 px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface placeholder:text-outline focus:ring-2 focus:ring-primary/20"
              placeholder="Doctor name"
              value={newDoctor.name}
              onChange={(e) => setNewDoctor({ ...newDoctor, name: e.target.value })}
            />
            <input
              type="text"
              className="w-40 px-4 py-3 bg-surface-container-highest rounded-xl border-none text-sm text-on-surface placeholder:text-outline focus:ring-2 focus:ring-primary/20"
              placeholder="NPI (optional)"
              value={newDoctor.npi}
              onChange={(e) => setNewDoctor({ ...newDoctor, npi: e.target.value })}
            />
            <button
              className="flex items-center gap-2 px-5 py-3 bg-primary text-on-primary font-semibold rounded-xl hover:bg-primary-container transition-colors text-sm"
              onClick={addDoctor}
            >
              <span className="material-symbols-outlined text-lg">add</span>
              Add
            </button>
          </div>

          {/* Doctor list */}
          {(!client.doctors || client.doctors.length === 0) ? (
            <p className="text-sm text-on-surface-variant">No preferred doctors added yet.</p>
          ) : (
            <ul className="space-y-2">
              {client.doctors.map((doc, i) => (
                <li key={i} className="flex items-center justify-between px-4 py-3 bg-surface-container-low rounded-xl">
                  <div className="flex items-center gap-3">
                    <span className="material-symbols-outlined text-primary text-lg">stethoscope</span>
                    <div>
                      <span className="text-sm font-medium text-on-surface">{doc.name}</span>
                      {doc.npi && (
                        <span className="ml-3 text-xs text-on-surface-variant">NPI: {doc.npi}</span>
                      )}
                    </div>
                  </div>
                  <button
                    className="p-1.5 rounded-lg hover:bg-error-container transition-colors"
                    onClick={() => removeDoctor(i)}
                  >
                    <span className="material-symbols-outlined text-lg text-error">close</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify**

Run `cd frontend && npm run build` and confirm no errors.

- [ ] **Step 3: Commit**

Commit message: `feat(frontend): implement Client Profile page with analysis workflow, profile editing, prescriptions, and doctors tabs`

---

### Task 8: Final Wiring + Verification

**Files:**
- Possibly modify: `.gitignore`
- No new files

- [ ] **Step 1: Update `.gitignore`**

Ensure the root `.gitignore` includes these lines (add them if missing):

```
frontend/node_modules/
frontend/dist/
```

- [ ] **Step 2: Build verification**

Run `cd frontend && npm run build` and confirm `frontend/dist/` is created with no errors. Check that `index.html`, CSS, and JS bundles exist in `dist/`.

- [ ] **Step 3: Full-stack smoke test**

Start the FastAPI backend:

```bash
cd /Users/saidukamara/code/projects/health-insurance-agent && .venv/bin/uvicorn healthflow.api.app:app --reload --port 8000 &
```

Start the Vite dev server:

```bash
cd frontend && npm run dev &
```

Then manually verify:

1. Visit `http://localhost:5173` — should redirect to `/login`
2. Register a new account via the "Create a Broker Account" form
3. Login with the new account — should redirect to `/`
4. The Client Portfolio page loads (empty table initially)
5. Click "Add Client" — modal opens, fill in fields, submit
6. New client appears in the table
7. Click the person icon on the client row — navigates to `/clients/:id`
8. Client Profile page loads with correct data
9. Click through all 4 tabs — each renders without errors
10. On "Plan Analysis" tab, click "Run" on Step 1 — API call fires (may fail if backend needs specific data, but the call should go through)
11. On "Profile Details" tab, edit a field and click "Save Profile" — should save and show success message
12. On "Prescriptions" tab, add a prescription — should persist
13. On "Preferred Doctors" tab, add a doctor — should persist
14. Logout (click user avatar area) — should return to `/login`

- [ ] **Step 4: Commit**

Commit message: `feat(frontend): finalize React frontend wiring and gitignore`

---

## File Inventory

| File | Task | Action |
|------|------|--------|
| `frontend/.gitkeep` | 1 | Delete |
| `frontend/package.json` | 1 | Create |
| `frontend/vite.config.js` | 1 | Create |
| `frontend/index.html` | 1 | Create |
| `frontend/tailwind.config.js` | 1 | Create |
| `frontend/postcss.config.js` | 1 | Create |
| `frontend/src/index.css` | 1 | Create |
| `frontend/src/main.jsx` | 1 | Create |
| `frontend/src/App.jsx` | 1, 4 | Create, then modify |
| `frontend/src/api/client.js` | 2 | Create |
| `frontend/src/contexts/AuthContext.jsx` | 2 | Create |
| `frontend/src/components/ProtectedRoute.jsx` | 3 | Create |
| `frontend/src/components/Sidebar.jsx` | 3 | Create |
| `frontend/src/components/TopBar.jsx` | 3 | Create |
| `frontend/src/components/Layout.jsx` | 3 | Create |
| `frontend/src/pages/LoginPage.jsx` | 4, 5 | Create placeholder, then replace |
| `frontend/src/pages/ClientListPage.jsx` | 4, 6 | Create placeholder, then replace |
| `frontend/src/pages/ClientProfilePage.jsx` | 4, 7 | Create placeholder, then replace |
| `.gitignore` | 8 | Modify (if needed) |
