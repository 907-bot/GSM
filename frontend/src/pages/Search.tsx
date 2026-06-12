import { useState, useEffect } from 'react'
import { Search as SearchIcon, BookOpen, Loader2, AlertTriangle, Clock, TrendingUp, ExternalLink } from 'lucide-react'
import { api } from '../api'
import { useNavigate } from 'react-router-dom'

const RECENT_VIEWED_KEY = 'gsm_recent_viewed_papers'

function getRecentViewed(): any[] {
  try {
    return JSON.parse(localStorage.getItem(RECENT_VIEWED_KEY) || '[]')
  } catch { return [] }
}

function addRecentViewed(paper: any) {
  const recent = getRecentViewed().filter((p: any) => p.title !== paper.title)
  recent.unshift({ title: paper.title, id: paper.id || paper.source_id, source: paper.source, time: Date.now() })
  localStorage.setItem(RECENT_VIEWED_KEY, JSON.stringify(recent.slice(0, 10)))
}

export function SearchPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [papers, setPapers] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'papers' | 'similar'>('papers')
  const [recentViewed, setRecentViewed] = useState<any[]>(getRecentViewed())
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)

  // Build suggestions from recent viewed paper categories + trending topics
  useEffect(() => {
    const topics = [
      'machine learning', 'quantum computing', 'CRISPR', 'drug discovery',
      'neural networks', 'genomics', 'AI safety', 'climate change',
      'natural language processing', 'robotics', 'gene therapy',
    ]
    const recent = getRecentViewed()
    const recentWords = recent.flatMap((r: any) =>
      (r.title || '').split(' ').filter((w: string) => w.length > 4)
    ).slice(0, 5)
    setSuggestions([...new Set([...recentWords, ...topics])].slice(0, 8))
  }, [])

  async function handleSearch() {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      if (activeTab === 'papers') {
        const data = await api.searchPapers(query, 25)
        setPapers(data.papers ?? [])
      } else {
        const data = await api.searchSimilar(query, 25)
        setPapers(data.results ?? [])
      }
      setShowSuggestions(false)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function viewPaper(paper: any) {
    const paperId = paper.id || paper.source_id
    addRecentViewed(paper)
    setRecentViewed(getRecentViewed())
    navigate(`/papers?paper=${encodeURIComponent(paperId)}`)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold gradient-text">Scientific Search</h1>
          <p className="text-slate-400 mt-1">Search across all research sources — suggestions based on your reading history</p>
        </div>
      </div>

      <div className="flex gap-2">
        <button onClick={() => setActiveTab('papers')}
          className={`px-4 py-2 text-sm rounded-lg border transition-all ${activeTab === 'papers' ? 'bg-blue-500/20 text-blue-300 border-blue-500/40' : 'border-white/10 text-slate-400 hover:text-white'}`}>
          Paper Search
        </button>
        <button onClick={() => setActiveTab('similar')}
          className={`px-4 py-2 text-sm rounded-lg border transition-all ${activeTab === 'similar' ? 'bg-blue-500/20 text-blue-300 border-blue-500/40' : 'border-white/10 text-slate-400 hover:text-white'}`}>
          Similarity Search
        </button>
      </div>

      {/* Search input with suggestions */}
      <div className="relative">
        <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-500" />
        <input
          type="text"
          placeholder={activeTab === 'papers' ? 'Search papers across arXiv, PubMed, Semantic Scholar…' : 'Find semantically similar content in memory…'}
          value={query}
          onChange={e => {
            setQuery(e.target.value)
            setShowSuggestions(e.target.value.length === 0)
          }}
          onFocus={() => setShowSuggestions(true)}
          onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          className="w-full pl-12 pr-32 py-3.5 rounded-xl glass-card text-white placeholder-slate-500 focus:outline-none focus:border-blue-500/50 text-lg"
        />
        <button onClick={handleSearch} disabled={loading || !query.trim()}
          className="absolute right-3 top-1/2 -translate-y-1/2 px-6 py-1.5 rounded-lg bg-blue-500 text-white text-sm font-medium hover:bg-blue-600 transition-colors disabled:opacity-50 flex items-center gap-2">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <SearchIcon className="h-4 w-4" />}
          Search
        </button>

        {/* Suggestions dropdown */}
        {showSuggestions && suggestions.length > 0 && query.length === 0 && (
          <div className="absolute top-full left-0 right-0 mt-2 glass-card border border-white/10 rounded-xl overflow-hidden z-50">
            <div className="px-4 py-2 text-xs text-slate-500 border-b border-white/5 flex items-center gap-1">
              <TrendingUp className="h-3 w-3" /> Suggestions
            </div>
            <div className="p-2 flex flex-wrap gap-1.5">
              {suggestions.map((s, i) => (
                <button key={i}
                  onClick={() => { setQuery(s); setShowSuggestions(false); }}
                  className="px-3 py-1.5 rounded-lg text-sm text-slate-300 bg-white/5 hover:bg-white/10 transition-colors border border-white/5">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Recently viewed */}
      {recentViewed.length > 0 && papers.length === 0 && !loading && (
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 text-sm text-slate-400 mb-3">
            <Clock className="h-4 w-4" />
            <span className="font-medium text-slate-300">Recently Viewed</span>
          </div>
          <div className="space-y-2">
            {recentViewed.slice(0, 5).map((item: any, i: number) => (
              <div key={i} className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-white/5 transition-colors">
                <div className="flex items-center gap-3 min-w-0">
                  <BookOpen className="h-4 w-4 text-blue-400 shrink-0" />
                  <span className="text-sm text-slate-300 truncate">{item.title}</span>
                  <span className="text-xs text-slate-500 shrink-0">{item.source}</span>
                </div>
                <button onClick={() => navigate(`/papers?paper=${encodeURIComponent(item.id || '')}`)}
                  className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 shrink-0 ml-2">
                  <ExternalLink className="h-3 w-3" /> View
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="glass-card p-4 border-rose-500/30 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-rose-400" />
          <span className="text-sm text-rose-400">{error}</span>
        </div>
      )}

      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="glass-card p-5 animate-pulse">
              <div className="h-5 bg-slate-700 rounded w-3/4 mb-3" />
              <div className="h-4 bg-slate-700 rounded w-1/2 mb-2" />
              <div className="h-4 bg-slate-700 rounded w-full mb-2" />
              <div className="h-3 bg-slate-700 rounded w-1/4" />
            </div>
          ))}
        </div>
      ) : papers.length === 0 && query ? (
        <div className="glass-card p-8 text-center">
          <BookOpen className="h-8 w-8 text-slate-500 mx-auto mb-2" />
          <p className="text-slate-400">No results found</p>
          <p className="text-sm text-slate-500 mt-1">Try a different query or check that research sources are available</p>
        </div>
      ) : papers.length === 0 ? (
        <div className="glass-card p-8 text-center">
          <SearchIcon className="h-8 w-8 text-slate-500 mx-auto mb-2" />
          <p className="text-slate-400">Enter a query to search scientific literature</p>
          <p className="text-sm text-slate-500 mt-1">Or click one of the suggestions above to get started</p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-500">{papers.length} results</p>
          </div>
          {papers.map((paper, i) => {
            const title = paper.title || paper.payload?.title || 'Untitled'
            const authors = paper.authors || paper.payload?.authors || []
            const source = paper.source || paper.payload?.source || 'unknown'
            const abstract = paper.abstract || paper.payload?.abstract || paper.payload?.finding_text || ''
            const score = paper.score || paper.relevance

            return (
              <div key={i} className="glass-card p-5 hover:border-blue-500/30 transition-all group">
                <div className="flex items-start gap-4">
                  {score != null && (
                    <div className="text-center shrink-0">
                      <div className="text-xs text-slate-500 mb-1">Match</div>
                      <div className="text-lg font-bold text-emerald-400">{(score * 100).toFixed(0)}%</div>
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold text-white hover:text-blue-400 transition-colors truncate">{title}</h3>
                    {authors.length > 0 && <p className="text-sm text-slate-400 mt-1 truncate">{authors.slice(0, 3).join(', ')}{authors.length > 3 ? ' et al.' : ''}</p>}
                    {abstract && <p className="text-sm text-slate-500 mt-2 line-clamp-2">{abstract}</p>}
                    <div className="flex items-center gap-2 mt-3">
                      <span className="px-2 py-0.5 rounded text-xs bg-blue-500/20 text-blue-300">{source}</span>
                      {paper.categories?.map((c: string, j: number) => (
                        <span key={j} className="px-2 py-0.5 rounded-full text-xs bg-white/5 text-slate-400 border border-white/10">{c}</span>
                      ))}
                      <button
                        onClick={() => viewPaper(paper)}
                        className="ml-auto flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <ExternalLink className="h-3 w-3" /> View Details
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}