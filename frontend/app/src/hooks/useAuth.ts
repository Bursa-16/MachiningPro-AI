import { useState, useCallback, useEffect } from 'react'
import { getStoredAuth } from '../services/apiClient'
import { login as doLogin, logout as doLogout } from '../services/auth'

export function useAuth() {
  const stored = getStoredAuth()
  const [token, setToken] = useState(stored.token)
  const [user, setUser] = useState(stored.displayName)
  const [role, setRole] = useState(stored.role)

  const isAuthenticated = !!token
  const isAdmin = role === 'admin'

  const login = useCallback(async (username: string, password: string) => {
    const res = await doLogin({ username, password })
    setToken(res.token); setUser(res.display_name); setRole(res.role as any)
    return res
  }, [])

  const logout = useCallback(() => {
    doLogout(); setToken(null); setUser(null); setRole(null)
  }, [])

  useEffect(() => {
    const s = getStoredAuth()
    if (s.token !== token) { setToken(s.token); setUser(s.displayName); setRole(s.role) }
  }, [])

  return { isAuthenticated, isAdmin, token, user, role, login, logout }
}
