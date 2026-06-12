import { useState, useEffect } from 'react'
import { AlertTriangle, ArrowUp, ArrowDown, Minus, RefreshCw, Search } from 'lucide-react'
import { api } from '../api'
import { useEventStore } from '../store/eventStore'

const FIELDS = ['Cancer Research', 'Drug Discovery', 'AI/ML', 'Materials Science', 'Quantum Computing', 'Physics', 'Genetics', 'Neuroscience']

export function BottleneckDashboard() {
  const [field, setField] = useState('Cancer Research')
  const [bottlenecks, setBottlenecks] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const pushEvents = useEventStore((s) => s.bottlenecks)

  async function load(f: string) {
    setLoading(true)
    setError(null)
    try {
      const { bottlenecks: data } = await api.detectBottlenecks(f, 10)
      setBottlenecks(data)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(field) }, [field])

  // Push new bottleneck events as they arrive
  useEffect(() => {
    if (pushEvents.length === 0) return
    const last = pushEvents[pushEvents.length - 1]
    if (!last.data?.field || last.data.field === field) {
      setBottlenecks((prev) => {
        const exists = prev.some((b) => b.major_bottleneck === last.data?.bottleneck)
        if (exists) return prev
        return [{
          major_bottleneck: last.data?.bottleneck,
          field: last.data?.field || field,
          description: last.data?.description,
          confidence: last.data?.confidence,
          trend: 'stable',
        }, ...prev].slice(0, 20)
      })
    }
  }, [pushEvents.length])

  const trendIcon = (t: string) => {
    switch (t) {
      case 'worsening': return <ArrowDown className="h-3 w-3" />
      case 'improving': return <ArrowUp className="h-3 w-3" />
      default: return <Minus className="h-3 w-3" />
    }
  }

  const trendColor = (t: string) => {
    switch (t) {
      case 'worsening': return 'bg-rose-500/20 text-rose-300'
      case 'improving': return 'bg-emerald-500/20 text-emerald-300'
      default: return 'bg-blue-500/20 text-blue-300'
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold gradient-text">Bottleneck Dashboard</h1>
          <p className="text-slate-400 mt-1">Scientific bottlenecks and obstacles preventing progress</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <AlertTriangle className="h-4 w-4 text-orange-400" />
          <span className="font-bold text-white">{bottlenecks.length}</span> detected
        </div>
      </div>

      <div className="flex gap-2">
        {FIELDS.map(f => (
          <button key={f} onClick={() => setField(f)}
            className={`px-4 py-2 text-sm rounded-lg border transition-all ${
              field === f ? 'bg-orange-500/20 text-orange-300 border-orange-500/40' : 'border-white/10 text-slate-400 hover:text-white hover:border-orange-500/30'
            }`}>
            {f}
          </button>
        ))}
        <button onClick={() => load(field)} disabled={loading} className="px-3 py-2 rounded-lg border border-white/10 text-slate-400 hover:text-white transition-all">
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="glass-card p-5 animate-pulse">
              <div className="h-4 bg-slate-700 rounded w-1/4 mb-3" />
              <div className="h-5 bg-slate-700 rounded w-2/3 mb-2" />
              <div className="h-4 bg-slate-700 rounded w-1/2 mb-2" />
              <div className="h-3 bg-slate-700 rounded w-1/3" />
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="glass-card p-8 text-center border-rose-500/30">
          <AlertTriangle className="h-8 w-8 text-rose-400 mx-auto mb-2" />
          <p className="text-slate-400">{error}</p>
        </div>
      ) : bottlenecks.length === 0 ? (
        <div className="glass-card p-8 text-center">
          <Search className="h-8 w-8 text-slate-500 mx-auto mb-2" />
          <p className="text-slate-400">No bottlenecks detected for {field}</p>
          <p className="text-sm text-slate-500 mt-1">Try a different field or run a research agent search first</p>
        </div>
      ) : (
        <div className="space-y-4">
          {bottlenecks.map((item, i) => (
            <div key={i} className="glass-card p-5 hover:border-orange-500/30 transition-all">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-medium text-orange-400 uppercase">{field}</span>
                    <span className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs ${trendColor(item.trend || 'stable')}`}>
                      {trendIcon(item.trend || 'stable')} {item.trend || 'stable'}
                    </span>
                  </div>
                  <h3 className="text-xl font-semibold text-white mb-2">{item.major_bottleneck || item.description}</h3>
                  <p className="text-sm text-slate-400 mb-3">{item.description}</p>
                  {item.suggested_approaches?.length > 0 && (
                    <div>
                      <span className="text-xs text-slate-500 uppercase tracking-wider">Suggested Approaches:</span>
                      {item.suggested_approaches.map((a: string, j: number) => (
                        <div key={j} className="flex items-center gap-2 text-sm text-slate-300 mt-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0" />
                          {a}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className="ml-6 text-center">
                  <div className="text-xs text-slate-500 mb-1">Confidence</div>
                  <div className="text-2xl font-bold text-white">{(item.confidence * 100).toFixed(0)}%</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
