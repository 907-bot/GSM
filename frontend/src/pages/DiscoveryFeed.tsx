import { useState, useEffect } from 'react'
import { BookOpen, AlertTriangle, RefreshCw, ExternalLink, Loader2 } from 'lucide-react'
import { api } from '../api'
import { LiveAgentProgress } from '../components/LiveAgentProgress'
import { TaskStatusPanel } from '../components/TaskStatusPanel'
import { useNavigate } from 'react-router-dom'

export function DiscoveryFeed() {
  const navigate = useNavigate()
  const [results, setResults] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [fetching, setFetching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState('all')

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const { papers: latestPapers } = await api.fetchLatestPapers('', 30)
      const paperItems = (latestPapers || []).map((p: any) => ({
        type: 'paper',
        title: p.title || 'Untitled paper',
        source: p.source || 'Research source',
        time: p.published_at || 'recent',
        summary: (p.abstract || '').slice(0, 150),
        confidence: null,
        paper: p,
      }))

      const { data: memoryPapers } = await api.listPapers(1, 20)
      const memoryItems = (memoryPapers || []).map((p: any) => ({
        type: 'paper',
        title: p.payload?.title || 'Paper from memory',
        source: p.payload?.source || 'Memory',
        time: 'stored',
        summary: (p.payload?.abstract || '').slice(0, 150),
        confidence: null,
        paper: { id: p.id, ...p.payload },
      }))

      setResults([...paperItems, ...memoryItems].slice(0, 50))
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function fetchMore() {
    setFetching(true)
    try {
      const { papers: morePapers } = await api.fetchLatestPapers('', 30)
      if (morePapers?.length) {
        const items = morePapers.map((p: any) => ({
          type: 'paper',
          title: p.title || 'Untitled',
          source: p.source || 'Research source',
          time: p.published_at || 'recent',
          summary: (p.abstract || '').slice(0, 150),
          confidence: null,
          paper: p,
        }))
        setResults((prev) => [...items, ...prev].slice(0, 100))
      }
    } catch {
      // silent
    } finally {
      setFetching(false)
    }
  }

  function viewDetails(paper: any) {
    const url = paper.paper?.url || (paper.paper?.doi ? `https://doi.org/${paper.paper.doi}` : '')
    if (url) {
      window.open(url, '_blank', 'noopener,noreferrer')
      return
    }
    navigate(`/papers?paper=${encodeURIComponent(paper.paper?.id || paper.paper?.source_id || '')}`)
  }

  const filtered = filter === 'all' ? results : results.filter(r => r.type === filter)
  const types = ['all', 'paper']

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold gradient-text">Discovery Feed</h1>
          <p className="text-slate-400 mt-1">Real papers from Hugging Face, arXiv, PubMed, and OpenAlex with source links</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={fetchMore} disabled={fetching}
            className="glass-card px-3 py-2 flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors disabled:opacity-50">
            {fetching ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
            Fetch More
          </button>
          <button onClick={load} disabled={loading}
            className="glass-card px-4 py-2 flex items-center gap-2 text-sm text-slate-300 hover:text-white transition-colors">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            {loading ? 'Loading…' : 'Refresh'}
          </button>
        </div>
      </div>

      {error && (
        <div className="glass-card p-4 border-rose-500/30">
          <div className="flex items-center gap-2 text-rose-400">
            <AlertTriangle className="h-4 w-4" />
            <span className="text-sm">{error}</span>
          </div>
        </div>
      )}

      <LiveAgentProgress />
      <TaskStatusPanel />

      <div className="flex gap-2">
        {types.map(t => (
          <button key={t} onClick={() => setFilter(t)}
            className={`px-4 py-2 text-sm rounded-lg border transition-all capitalize ${
              filter === t ? 'bg-blue-500/20 text-blue-300 border-blue-500/40' : 'border-white/10 text-slate-400 hover:text-white hover:border-blue-500/30'
            }`}>
            {t}
          </button>
        ))}
      </div>

      {loading && filtered.length === 0 ? (
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="glass-card p-5 animate-pulse">
              <div className="h-4 bg-slate-700 rounded w-1/4 mb-3" />
              <div className="h-5 bg-slate-700 rounded w-3/4 mb-2" />
              <div className="h-4 bg-slate-700 rounded w-1/2" />
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass-card p-8 text-center">
          <p className="text-slate-400">No papers yet. Click "Fetch More" to load latest from public research sources.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {filtered.map((item, i) => (
            <div key={i} className="glass-card p-5 hover:border-blue-500/30 transition-all group">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="px-2 py-0.5 rounded text-xs font-medium flex items-center gap-1 bg-blue-500/20 text-blue-300">
                      <BookOpen className="h-3 w-3" /> paper
                    </span>
                    <span className="text-xs text-slate-500">{item.source}</span>
                  </div>
                  <h3 className="text-lg font-semibold text-white mb-1 truncate">{item.title}</h3>
                  <p className="text-sm text-slate-400 line-clamp-2">{item.summary}</p>
                </div>
              </div>
              <div className="mt-3 pt-3 border-t border-white/5 flex items-center justify-between">
                <span className="text-xs text-slate-500">{item.time}</span>
                <button
                  onClick={() => viewDetails(item)}
                  className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
                >
                  <ExternalLink className="h-3 w-3" /> Details
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
