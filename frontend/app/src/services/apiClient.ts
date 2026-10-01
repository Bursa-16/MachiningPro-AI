const API_BASE = '/api'

const AUTH_TOKEN_KEY = 'machiningpro_token'
const AUTH_USER_KEY = 'machiningpro_user'
const AUTH_ROLE_KEY = 'machiningpro_role'

class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
    this.detail = detail
  }
}

function getToken(): string | null {
  return sessionStorage.getItem(AUTH_TOKEN_KEY)
}

export function setAuth(token: string, displayName: string, role: string) {
  sessionStorage.setItem(AUTH_TOKEN_KEY, token)
  sessionStorage.setItem(AUTH_USER_KEY, displayName)
  sessionStorage.setItem(AUTH_ROLE_KEY, role)
}

export function clearAuth() {
  sessionStorage.removeItem(AUTH_TOKEN_KEY)
  sessionStorage.removeItem(AUTH_USER_KEY)
  sessionStorage.removeItem(AUTH_ROLE_KEY)
}

export function getStoredAuth() {
  return {
    token: sessionStorage.getItem(AUTH_TOKEN_KEY),
    displayName: sessionStorage.getItem(AUTH_USER_KEY),
    role: sessionStorage.getItem(AUTH_ROLE_KEY) as 'admin' | 'engineer' | 'viewer' | null,
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers as Record<string, string>,
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })

  if (!res.ok) {
    let detail = 'İstek başarısız'
    try {
      const data = await res.json()
      detail = data.detail || detail
    } catch {
      // Keep the fallback detail for non-JSON error responses.
    }
    throw new ApiError(res.status, detail)
  }

  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return res.json()
  }

  return res as unknown as T
}

export { ApiError }
export default api
