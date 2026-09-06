export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const AUTH_STORAGE_KEY = 'sihfarm.auth'

export function getStoredAuth() {
  try {
    return JSON.parse(localStorage.getItem(AUTH_STORAGE_KEY) || 'null')
  } catch {
    return null
  }
}

export function storeAuth(auth) {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth))
}

export function clearStoredAuth() {
  localStorage.removeItem(AUTH_STORAGE_KEY)
}

export async function apiFetch(path, options = {}) {
  const auth = getStoredAuth()
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (auth?.access_token) headers.Authorization = `Bearer ${auth.access_token}`
  const response = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed with ${response.status}`)
  }
  return response.status === 204 ? null : response.json()
}
