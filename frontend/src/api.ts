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

  if (!res.ok) {
    const payload = await res.json().catch(() => null)
    throw new ApiError(res.status, payload?.message || payload?.detail || `API ${res.status}: ${res.statusText}`)
  }
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

  comparePapers: (paperIdA: string, paperIdB: string) =>
    request<any>(`/papers/compare?paper_id_a=${encodeURIComponent(paperIdA)}&paper_id_b=${encodeURIComponent(paperIdB)}`),

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

  scoreNovelty: (concepts: string[]) =>
    request<any>('/novelty/score', {
      method: 'POST',
      body: JSON.stringify({ concepts }),
    }),

  noveltyCombinations: (minConfidence = 0.3, maxResults = 20) =>
    request<any>(`/novelty/combinations?min_confidence=${minConfidence}&max_results=${maxResults}`),

  drugRepurposing: () => request<any>('/novelty/drug-repurposing'),

  threeHopHypotheses: () => request<any>('/novelty/three-hop-hypotheses'),

  generateRoadmap: (topic: string, timeframeWeeks = 12, includeGaps = true) =>
    request<any>('/roadmap/generate', {
      method: 'POST',
      body: JSON.stringify({
        topic,
        timeframe_weeks: timeframeWeeks,
        timeframe_years: Math.max(1, Math.ceil(timeframeWeeks / 52)),
        include_gaps: includeGaps,
      }),
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

  // ── Subject Gap Discovery & Paper Publishing ───────────────
  analyzeGaps: (subject: string, maxPapers = 15) =>
    request<{
      subject: string
      papers_analyzed_count: number
      papers: any[]
      key_concepts: string[]
      bottlenecks: any[]
      contradictions: any[]
      missing_links: any[]
      hypotheses: any[]
      paper_angles: any[]
      analyzed_at: string
    }>('/gaps/analyze', {
      method: 'POST',
      body: JSON.stringify({ subject, max_papers: maxPapers }),
    }),

  generatePublishedPaper: (params: {
    topic: string
    gap: string
    venue?: string
    paper_type?: string
    authors?: Array<{ name: string; affiliation: string; email: string }>
    custom_notes?: string
    keywords?: string[]
  }) =>
    request<{
      id: string
      title: string
      topic: string
      gap: string
      venue: string
      venue_info: any
      paper_type: string
      authors: any[]
      keywords: string[]
      sections: Record<string, string>
      bibtex: string
      latex: string
      markdown: string
      stats: { word_count: number; sections_count: number; citations_count: number; generated_at: string }
    }>('/papers/publish/generate', {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  regeneratePaperSection: (params: {
    section_name: string
    topic: string
    current_content: string
    prompt: string
  }) =>
    request<{ section_name: string; content: string }>('/papers/publish/section', {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  simulatePaperReview: (params: {
    title: string
    abstract: string
    sections: Record<string, string>
    venue?: string
  }) =>
    request<{
      venue: string
      reviewer_role: string
      scores: {
        novelty: number
        theoretical_soundness: number
        empirical_rigor: number
        clarity_and_presentation: number
        overall_confidence: number
      }
      recommendation: string
      acceptance_probability: number
      review_summary: string
      action_checklist: string[]
      reviewed_at: string
    }>('/papers/publish/review', {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  exportPaperFile: async (format: 'latex' | 'bibtex' | 'markdown', content: string, filename: string) => {
    const res = await fetch('/api/papers/publish/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ format, content, filename }),
    })
    if (!res.ok) throw new Error('Export failed')
    const blob = await res.blob()
    const ext = format === 'latex' ? 'tex' : format === 'bibtex' ? 'bib' : 'md'
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${filename}.${ext}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  },
}

export type Api = typeof api
