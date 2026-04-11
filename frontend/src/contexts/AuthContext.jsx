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

function getInitialAuth() {
  const token = getToken()
  if (!token) return { user: null, isAuthenticated: false }

  const payload = decodeTokenPayload(token)
  if (!payload) return { user: null, isAuthenticated: false }

  // Check if token is expired
  if (payload.exp && payload.exp * 1000 < Date.now()) {
    clearTokens()
    return { user: null, isAuthenticated: false }
  }

  return {
    user: { id: payload.sub, role: payload.role, email: payload.email || '' },
    isAuthenticated: true,
  }
}

export function AuthProvider({ children }) {
  const initial = getInitialAuth()
  const [user, setUser] = useState(initial.user)
  const [isAuthenticated, setIsAuthenticated] = useState(initial.isAuthenticated)

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
