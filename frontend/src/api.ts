const API_BASE = '/api'

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem('gsm_access_token')
  const headers = new Headers(init?.headers)
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  })

  if (res.status === 401) {
    localStorage.removeItem('gsm_access_token')
    localStorage.removeItem('gsm_user')
    window.dispatchEvent(new Event('gsm_auth_unauthorized'))
  }

  if (!res.ok) throw new ApiError(res.status, `API ${res.status}: ${res.statusText}`)
  return res.json()
}

export const api = {
  // ── Paper Browser / Research Assistant ───────────────────────

  listPapers: (page = 1, pageSize = 20) =>
    request<{ data: any[]; pagination: any }>(`/papers?page=${page}&page_size=${pageSize}`),

  getPaper: (id: string) =>
    request<{ id: string; payload: Record<string, any> }>(`/papers/${encodeURIComponent(id)}`),

  summarizePaper: (id: string): EventSource => {
    return new EventSource(`/api/papers/${encodeURIComponent(id)}/summarize`)
  },

  extractKeyterms: (id: string) =>
    request<{ paper_id: string; terms: { term: string; definition: string }[] }>(
      `/papers/${encodeURIComponent(id)}/keyterms`
    ),

  findRelationships: (id: string) =>
    request<{ paper_id: string; relationships: any[]; total: number }>(
      `/papers/${encodeURIComponent(id)}/relationships`
    ),

  fetchLatestPapers: (query = '', maxResults = 25) =>
    request<{ papers: any[]; total: number; source: string }>('/papers/fetch', {
      method: 'POST',
      body: JSON.stringify({ query, max_results: maxResults }),
    }),

  // ── Existing ────────────────────────────────────────────────
  health: () => request<{ status: string; services: Record<string, string> }>('/health'),

  memoryStats: () =>
    request<{ episodic: any; semantic: { concepts: number; papers: number; relationships: number } }>('/memory/statistics'),

  graphHealth: () =>
    request<{ statistics: any; density: number; connectivity: number; health_score: number; recommendations: string[] }>('/graph/health'),

  searchPapers: (query: string, limit = 100) =>
    request<{ query: string; papers: any[]; total: number }>('/search/papers', {
      method: 'POST',
      body: JSON.stringify({ query, limit }),
    }),

  searchSimilar: (query: string, limit = 10, filterType?: string) => {
    let p = `/search/similar?query=${encodeURIComponent(query)}&limit=${limit}`
    if (filterType) p += `&filter_type=${filterType}`
    return request<any>('/search/similar', { method: 'POST', body: JSON.stringify({ query, limit, filter_type: filterType }) })
  },

  runAgentSearch: (domain?: string) =>
    request<{ results: any[]; total: number }>('/agents/search', {
      method: 'POST',
      body: JSON.stringify({ domain }),
    }),

  runReplay: (tw = 7, ss = 100) =>
    request<any>('/replay/run', {
      method: 'POST',
      body: JSON.stringify({ time_window_days: tw, sample_size: ss }),
    }),

  runDream: (dm = 30) =>
    request<any>('/replay/dream', {
      method: 'POST',
      body: JSON.stringify({ duration_minutes: dm }),
    }),

  contradictionSummary: () => request<any>('/contradictions/summary'),

  detectBottlenecks: (field: string, twd = 30) =>
    request<{ field: string; bottlenecks: any[]; total: number }>('/bottlenecks/detect', {
      method: 'POST',
      body: JSON.stringify({ field, time_window_days: twd }),
    }),

  bottleneckSummary: (field: string) => request<any>(`/bottlenecks/summary/${encodeURIComponent(field)}`),

  generateHypotheses: (num = 5) =>
    request<{ hypotheses: any[]; total: number }>('/hypotheses/generate', {
      method: 'POST',
      body: JSON.stringify({ num_hypotheses: num }),
    }),

  discoverPath: (source: string, target: string, md = 5) =>
    request<any>('/graph/discover/path', {
      method: 'POST',
      body: JSON.stringify({ source, target, max_depth: md }),
    }),

  emergingClusters: () => request<any>('/graph/clusters/emerging'),

  missingLinks: () => request<any>('/graph/missing-links'),

  visualizeGraph: (concept: string, depth = 2) =>
    request<any>(`/graph/visualize/${encodeURIComponent(concept)}?depth=${depth}`),
}

export type Api = typeof api
