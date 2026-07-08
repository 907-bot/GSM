import { create } from 'zustand'

export interface User {
  id: string
  email: string
  name: string
  role: string
  api_key: string
}

interface AuthState {
  user: User | null
  token: string | null
  loading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string, role: string) => Promise<void>
  logout: () => Promise<void>
  checkMe: () => Promise<void>
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: (() => {
    try {
      const stored = localStorage.getItem('gsm_user')
      return stored ? JSON.parse(stored) : null
    } catch {
      return null
    }
  })(),
  token: localStorage.getItem('gsm_access_token'),
  loading: false,
  error: null,

  login: async (email, password) => {
    set({ loading: true, error: null })
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || 'Login failed. Invalid email or password.')
      }

      const data = await response.json()
      localStorage.setItem('gsm_access_token', data.access_token)
      localStorage.setItem('gsm_user', JSON.stringify(data.user))
      
      set({
        token: data.access_token,
        user: data.user,
        loading: false,
      })
    } catch (err: any) {
      set({ error: err.message, loading: false })
      throw err
    }
  },

  register: async (name, email, password, role) => {
    set({ loading: true, error: null })
    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password, role }),
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || 'Registration failed.')
      }

      const data = await response.json()
      localStorage.setItem('gsm_access_token', data.access_token)
      localStorage.setItem('gsm_user', JSON.stringify(data.user))

      set({
        token: data.access_token,
        user: data.user,
        loading: false,
      })
    } catch (err: any) {
      set({ error: err.message, loading: false })
      throw err
    }
  },

  logout: async () => {
    const token = get().token
    if (token) {
      try {
        await fetch('/api/auth/logout', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
        })
      } catch (err) {
        console.error('Logout request failed', err)
      }
    }
    get().clearAuth()
  },

  checkMe: async () => {
    const token = get().token
    const headers: Record<string, string> = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    try {
      const response = await fetch('/api/auth/me', { headers })

      if (response.status === 401) {
        get().clearAuth()
        return
      }

      if (response.ok) {
        const user = await response.json()
        localStorage.setItem('gsm_user', JSON.stringify(user))
        if (!token) {
          localStorage.setItem('gsm_access_token', 'dev-mode-bypass')
          set({ user, token: 'dev-mode-bypass' })
        } else {
          set({ user })
        }
      }
    } catch (err) {
      console.error('Failed to verify token validity', err)
    }
  },

  clearAuth: () => {
    localStorage.removeItem('gsm_access_token')
    localStorage.removeItem('gsm_user')
    set({ user: null, token: null, error: null, loading: false })
  },
}))
