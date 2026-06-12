import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'
const api = axios.create({ baseURL: API_BASE })

export function useApi<T = any>(endpoint: string, options?: { immediate?: boolean }) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data: result } = await api.get(endpoint)
      setData(result)
      return result
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err.message || 'Request failed'
      setError(msg)
      throw err
    } finally {
      setLoading(false)
    }
  }, [endpoint])

  useEffect(() => {
    if (options?.immediate !== false) {
      fetch()
    }
  }, [fetch, options?.immediate])

  return { data, loading, error, refetch: fetch }
}

export function useMutation<T = any>() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const mutate = useCallback(async (method: 'post' | 'put' | 'delete', endpoint: string, body?: any) => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await api[method](endpoint, body)
      return data as T
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err.message || 'Request failed'
      setError(msg)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return { mutate, loading, error }
}

export function usePolling<T = any>(endpoint: string, intervalMs: number = 30000) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    const fetch = async () => {
      try {
        const { data: result } = await api.get(endpoint)
        if (mounted) setData(result)
      } catch (err: any) {
        if (mounted) setError(err.message)
      }
    }
    fetch()
    const id = setInterval(fetch, intervalMs)
    return () => { mounted = false; clearInterval(id) }
  }, [endpoint, intervalMs])

  return { data, error }
}
