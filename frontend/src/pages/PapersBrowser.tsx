import { useState, useEffect, useRef, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  BookOpen, Loader2, Search, AlertTriangle,
  Share2, Sparkles, ExternalLink,
  RefreshCw, User, Hash, Calendar, Quote,
} from 'lucide-react'
import { api } from '../api'

interface Paper {
  id: string
  payload: {
    title: string
    abstract: string
    authors: string[]
    source: string
    source_id: string
    doi?: string
    published_at?: string
    categories: string[]
    citations_count?: number
    url?: string
    metadata?: Record<string, any>
  }
}

interface KeyTerm {
  term: string
  definition: string
}

interface Relationship {
  paper_id: string
  title: string
  type: string
  strength: number
  shared_authors: string[]
  shared_categories: string[]
}

type DetailTab = 'summary' | 'keyterms' | 'relationships'

export function PapersBrowser() {
  const [searchParams] = useSearchParams()
  const preselectedId = searchParams.get('paper')
  const [papers, setPapers] = useState<Paper[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPaper, setSelectedPaper] = useState<Paper | null>(null)
  const [activeTab, setActiveTab] = useState<DetailTab>('summary')
  const [query, setQuery] = useState('')
  const [fetching, setFetching] = useState(false)

  const [summaryText, setSummaryText] = useState('')
  const [summarizing, setSummarizing] = useState(false)
  const [keyterms, setKeyterms] = useState<KeyTerm[]>([])
  const [keytermsLoading, setKeytermsLoading] = useState(false)
  const [relationships, setRelationships] = useState<Relationship[]>([])
  const [relationshipsLoading, setRelationshipsLoading] = useState(false)

  const eventSourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    loadPapers()
  }, [])

  async function loadPapers() {
    setLoading(true)
    setError(null)
    try {
      const data = await api.listPapers(1, 100)
      const paperList = data.data ?? []
      setPapers(paperList)

      // Auto-select paper from URL param or first
      if (paperList.length > 0 && !selectedPaper) {
        if (preselectedId) {
          const match = paperList.find(
            (p: Paper) => p.id === preselectedId || p.payload?.source_id === preselectedId
          )
          if (match) selectPaper(match)
          else selectPaper(paperList[0])
        } else {
          selectPaper(paperList[0])
        }
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleFetchLatest() {
    setFetching(true)
    setError(null)
    try {
      const data = await api.fetchLatestPapers(query, 25)
      if (data.papers?.length > 0) {
        setPapers((prev) => {
          const existing = new Set(prev.map((p) => p.id))
          const newPapers = data.papers.filter((p: any) => !existing.has(p.id))
          return [...newPapers, ...prev].slice(0, 100)
        })
        if (!selectedPaper) selectPaper(data.papers[0])
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setFetching(false)
    }
  }

  const selectPaper = useCallback((paper: Paper) => {
    setSelectedPaper(paper)
    setActiveTab('summary')
    setSummaryText('')
    setKeyterms([])
    setRelationships([])
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    streamSummary(paper.id)
    loadKeyterms(paper.id)
    loadRelationships(paper.id)
  }, [])

  function streamSummary(paperId: string) {
    setSummarizing(true)
    setSummaryText('')
    const es = api.summarizePaper(paperId)
    eventSourceRef.current = es

    es.onmessage = (event) => {
      if (event.data === '[DONE]') {
        setSummarizing(false)
        es.close()
        return
      }
      try {
        const parsed = JSON.parse(event.data)
        if (parsed.token) {
          setSummaryText((prev) => prev + parsed.token)
        }
      } catch {
        // ignore parse errors on partial data
      }
    }

    es.onerror = () => {
      setSummarizing(false)
      es.close()
    }
  }

  async function loadKeyterms(paperId: string) {
    setKeytermsLoading(true)
    try {
      const data = await api.extractKeyterms(paperId)
      setKeyterms(data.terms ?? [])
    } catch {
      // silently fail
    } finally {
      setKeytermsLoading(false)
    }
  }

  async function loadRelationships(paperId: string) {
    setRelationshipsLoading(true)
    try {
      const data = await api.findRelationships(paperId)
      setRelationships(data.relationships ?? [])
    } catch {
      // silently fail
    } finally {
      setRelationshipsLoading(false)
    }
  }

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-3xl font-bold gradient-text">Research Papers</h1>
          <p className="text-slate-400 mt-1">Browse papers with real-time AI summaries</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search HF papers..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleFetchLatest()}
              className="w-64 pl-9 pr-3 py-2 rounded-lg glass-card text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500/50"
            />
          </div>
          <button
            onClick={handleFetchLatest}
            disabled={fetching}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-500 text-white text-sm font-medium hover:bg-blue-600 transition-colors disabled:opacity-50"
          >
            {fetching ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Fetch Papers
          </button>
        </div>
      </div>

      {error && (
        <div className="glass-card p-4 border-rose-500/30 flex items-center gap-2 mb-4">
          <AlertTriangle className="h-4 w-4 text-rose-400 shrink-0" />
          <span className="text-sm text-rose-400">{error}</span>
        </div>
      )}

      {/* Main split panel */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* Left: Paper list */}
        <div className="w-96 shrink-0 flex flex-col glass-card overflow-hidden">
          <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
            <span className="text-sm font-medium text-slate-300">
              {loading ? 'Loading...' : `${papers.length} papers`}
            </span>
            <button onClick={loadPapers} className="p-1 text-slate-500 hover:text-slate-300 transition-colors">
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="p-4 space-y-3">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="animate-pulse">
                    <div className="h-4 bg-slate-700/50 rounded w-3/4 mb-2" />
                    <div className="h-3 bg-slate-700/50 rounded w-1/2" />
                  </div>
                ))}
              </div>
            ) : papers.length === 0 ? (
              <div className="p-8 text-center">
                <BookOpen className="h-8 w-8 text-slate-500 mx-auto mb-2" />
                <p className="text-sm text-slate-400">No papers yet</p>
                <p className="text-xs text-slate-500 mt-1">Click "Fetch Papers" to load latest research</p>
              </div>
            ) : (
              <div className="divide-y divide-white/5">
                {papers.map((paper) => {
                  const p = paper.payload
                  const isSelected = selectedPaper?.id === paper.id
                  return (
                    <button
                      key={paper.id}
                      onClick={() => selectPaper(paper)}
                      className={`w-full text-left px-4 py-3 transition-colors hover:bg-white/5 ${
                        isSelected ? 'bg-blue-500/10 border-l-2 border-blue-400' : ''
                      }`}
                    >
                      <h3 className={`text-sm font-medium truncate ${isSelected ? 'text-blue-300' : 'text-slate-200'}`}>
                        {p?.title || 'Untitled'}
                      </h3>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-slate-500 truncate">
                          {p?.authors?.slice(0, 2).join(', ') || 'Unknown author'}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 mt-1.5">
                        <span className="px-1.5 py-0.5 rounded text-[10px] bg-blue-500/20 text-blue-300 uppercase">
                          {p?.source || 'unknown'}
                        </span>
                        {p?.categories?.slice(0, 2).map((c: string, j: number) => (
                          <span key={j} className="text-[10px] text-slate-500 truncate">{c}</span>
                        ))}
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right: Paper detail */}
        <div className="flex-1 glass-card overflow-hidden flex flex-col">
          {!selectedPaper ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <BookOpen className="h-12 w-12 text-slate-600 mx-auto mb-3" />
                <p className="text-slate-400">Select a paper to view details</p>
              </div>
            </div>
          ) : (
            <>
              {/* Paper header */}
              <div className="px-6 py-5 border-b border-white/10">
                <h2 className="text-xl font-bold text-white leading-snug">
                  {selectedPaper.payload?.title || 'Untitled'}
                </h2>
                <div className="flex items-center flex-wrap gap-3 mt-3">
                  <div className="flex items-center gap-1 text-sm text-slate-400">
                    <User className="h-3.5 w-3.5" />
                    <span className="truncate max-w-xs">
                      {selectedPaper.payload?.authors?.join(', ') || 'Unknown'}
                    </span>
                  </div>
                  {selectedPaper.payload?.published_at && (
                    <div className="flex items-center gap-1 text-sm text-slate-500">
                      <Calendar className="h-3.5 w-3.5" />
                      <span>{String(selectedPaper.payload.published_at).slice(0, 10)}</span>
                    </div>
                  )}
                  {selectedPaper.payload?.citations_count != null && (
                    <div className="flex items-center gap-1 text-sm text-slate-500">
                      <Quote className="h-3.5 w-3.5" />
                      <span>{selectedPaper.payload.citations_count} citations</span>
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-3">
                  <span className="px-2 py-0.5 rounded text-xs bg-blue-500/20 text-blue-300 uppercase">
                    {selectedPaper.payload?.source || 'unknown'}
                  </span>
                  {selectedPaper.payload?.categories?.map((c: string, i: number) => (
                    <span key={i} className="px-2 py-0.5 rounded-full text-xs bg-white/5 text-slate-400 border border-white/10">
                      {c}
                    </span>
                  ))}
                  {selectedPaper.payload?.doi && (
                    <a
                      href={`https://doi.org/${selectedPaper.payload.doi}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 ml-auto"
                    >
                      <ExternalLink className="h-3 w-3" />
                      DOI
                    </a>
                  )}
                </div>
              </div>

              {/* Abstract */}
              <div className="px-6 py-3 border-b border-white/5">
                <p className="text-sm text-slate-400 leading-relaxed line-clamp-4">
                  {selectedPaper.payload?.abstract || 'No abstract available'}
                </p>
              </div>

              {/* Tabs */}
              <div className="flex border-b border-white/10 px-6">
                {([
                  { key: 'summary', label: 'Summary', icon: Sparkles },
                  { key: 'keyterms', label: 'Key Terms', icon: Hash },
                  { key: 'relationships', label: 'Relationships', icon: Share2 },
                ] as const).map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                      activeTab === tab.key
                        ? 'text-blue-400 border-blue-400'
                        : 'text-slate-500 border-transparent hover:text-slate-300'
                    }`}
                  >
                    <tab.icon className="h-4 w-4" />
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Tab content */}
              <div className="flex-1 overflow-y-auto p-6">
                {activeTab === 'summary' && (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-sm text-slate-400">
                      <Sparkles className="h-4 w-4 text-yellow-400" />
                      AI-generated summary
                      {summarizing && (
                        <span className="flex items-center gap-1 text-xs text-blue-400">
                          <Loader2 className="h-3 w-3 animate-spin" />
                          generating...
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
                      {summaryText || (
                        <span className="text-slate-500 italic">Summary will appear here...</span>
                      )}
                    </div>
                  </div>
                )}

                {activeTab === 'keyterms' && (
                  <div className="space-y-3">
                    {keytermsLoading ? (
                      <div className="flex items-center gap-2 text-sm text-slate-400">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Extracting key terms...
                      </div>
                    ) : keyterms.length === 0 ? (
                      <p className="text-sm text-slate-500 italic">No key terms extracted yet.</p>
                    ) : (
                      keyterms.map((kt, i) => (
                        <div key={i} className="glass-card p-4 border-white/5">
                          <div className="flex items-center gap-2">
                            <Hash className="h-4 w-4 text-blue-400 shrink-0" />
                            <span className="text-sm font-medium text-white">{kt.term}</span>
                          </div>
                          <p className="text-sm text-slate-400 mt-1 ml-6">{kt.definition}</p>
                        </div>
                      ))
                    )}
                  </div>
                )}

                {activeTab === 'relationships' && (
                  <div className="space-y-3">
                    {relationshipsLoading ? (
                      <div className="flex items-center gap-2 text-sm text-slate-400">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Finding relationships...
                      </div>
                    ) : relationships.length === 0 ? (
                      <p className="text-sm text-slate-500 italic">No relationships found with other papers.</p>
                    ) : (
                      relationships.map((rel, i) => (
                        <div key={i} className="glass-card p-4 border-white/5">
                          <div className="flex items-start gap-3">
                            <Share2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-white truncate">{rel.title}</p>
                              <div className="flex items-center gap-2 mt-1">
                                <span className={cx(
                                  'px-1.5 py-0.5 rounded text-[10px] font-medium',
                                  rel.type === 'shared_author'
                                    ? 'bg-purple-500/20 text-purple-300'
                                    : rel.type === 'shared_category'
                                    ? 'bg-emerald-500/20 text-emerald-300'
                                    : 'bg-blue-500/20 text-blue-300'
                                )}>
                                  {rel.type.replace('_', ' ')}
                                </span>
                                <span className="text-xs text-slate-500">
                                  strength {rel.strength}
                                </span>
                              </div>
                              {rel.shared_authors.length > 0 && (
                                <p className="text-xs text-slate-500 mt-1">
                                  Shared authors: {rel.shared_authors.join(', ')}
                                </p>
                              )}
                              {rel.shared_categories.length > 0 && (
                                <p className="text-xs text-slate-500 mt-0.5">
                                  Shared categories: {rel.shared_categories.join(', ')}
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function cx(...classes: (string | false | undefined | null)[]): string {
  return classes.filter(Boolean).join(' ')
}