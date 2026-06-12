import { create } from 'zustand'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'
const api = axios.create({ baseURL: API_BASE })

interface SystemState {
  health: { status: string; services: Record<string, string> } | null
  memoryStats: { episodic: any; semantic: any } | null
  graphHealth: any | null
  hypotheses: any[]
  bottlenecks: any[]
  discoveries: any[]
  loading: boolean
  error: string | null
  fetchHealth: () => Promise<void>
  fetchMemoryStats: () => Promise<void>
  fetchGraphHealth: () => Promise<void>
  generateHypotheses: (count?: number) => Promise<void>
  detectBottlenecks: (field?: string) => Promise<void>
  runReplay: () => Promise<void>
  runDream: () => Promise<void>
}

export const useSystemStore = create<SystemState>((set) => ({
  health: null,
  memoryStats: null,
  graphHealth: null,
  hypotheses: [],
  bottlenecks: [],
  discoveries: [],
  loading: false,
  error: null,

  fetchHealth: async () => {
    try {
      const { data } = await api.get('/health')
      set({ health: data })
    } catch (err: any) {
      set({ error: err.message })
    }
  },

  fetchMemoryStats: async () => {
    try {
      const { data } = await api.get('/memory/statistics')
      set({ memoryStats: data })
    } catch (err: any) {
      set({ error: err.message })
    }
  },

  fetchGraphHealth: async () => {
    try {
      const { data } = await api.get('/graph/health')
      set({ graphHealth: data })
    } catch (err: any) {
      set({ error: err.message })
    }
  },

  generateHypotheses: async (count = 5) => {
    set({ loading: true })
    try {
      const { data } = await api.post('/hypotheses/generate', { num_hypotheses: count })
      set({ hypotheses: data.hypotheses, loading: false })
    } catch (err: any) {
      set({ error: err.message, loading: false })
    }
  },

  detectBottlenecks: async (field = 'Cancer Research') => {
    set({ loading: true })
    try {
      const { data } = await api.post('/bottlenecks/detect', { field, time_window_days: 30 })
      set({ bottlenecks: data.bottlenecks, loading: false })
    } catch (err: any) {
      set({ error: err.message, loading: false })
    }
  },

  runReplay: async () => {
    set({ loading: true })
    try {
      await api.post('/replay/run', { time_window_days: 7, sample_size: 100 })
      set({ loading: false })
    } catch (err: any) {
      set({ error: err.message, loading: false })
    }
  },

  runDream: async () => {
    set({ loading: true })
    try {
      await api.post('/replay/dream', { duration_minutes: 30 })
      set({ loading: false })
    } catch (err: any) {
      set({ error: err.message, loading: false })
    }
  },
}))
