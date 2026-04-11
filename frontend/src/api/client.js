const API_BASE_URL = ''

export function setToken(token) {
  sessionStorage.setItem('hf_token', token)
}

export function getToken() {
  return sessionStorage.getItem('hf_token')
}

export function setRefreshToken(token) {
  sessionStorage.setItem('hf_refresh', token)
}

export function getRefreshToken() {
  return sessionStorage.getItem('hf_refresh')
}

export function clearTokens() {
  sessionStorage.removeItem('hf_token')
  sessionStorage.removeItem('hf_refresh')
}

async function refreshAccessToken() {
  const refresh = getRefreshToken()
  if (!refresh) return false

  try {
    const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    })

    if (!res.ok) return false

    const data = await res.json()
    setToken(data.access_token)
    return true
  } catch {
    return false
  }
}

async function request(method, path, body = null) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const config = { method, headers }
  if (body !== null) {
    config.body = JSON.stringify(body)
  }

  let res = await fetch(`${API_BASE_URL}${path}`, config)

  // On 401, attempt token refresh and retry once
  if (res.status === 401 && getRefreshToken()) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      headers['Authorization'] = `Bearer ${getToken()}`
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
