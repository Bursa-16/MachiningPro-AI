import api, { setAuth, clearAuth } from './apiClient'
import type { LoginRequest, LoginResponse } from '../types/api'

export async function login(req: LoginRequest): Promise<LoginResponse> {
  const data = await api<LoginResponse>('/login', { method: 'POST', body: JSON.stringify(req) })
  setAuth(data.token, data.display_name, data.role)
  return data
}

export function logout() { clearAuth() }

export async function changePassword(current: string, newPw: string) {
  return api<{ ok: boolean }>('/change-password', {
    method: 'POST', body: JSON.stringify({ current_password: current, new_password: newPw })
  })
}
