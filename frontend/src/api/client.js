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
