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
