import { useState, useEffect } from 'react'
import { Lightbulb, Beaker, BookOpen, RefreshCw } from 'lucide-react'
import { api } from '../api'
import { useEventStore } from '../store/eventStore'

export function HypothesisDashboard() {
  const [hypotheses, setHypotheses] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [count, setCount] = useState(5)

  const pushEvents = useEventStore((s) => s.hypotheses)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const { hypotheses: data } = await api.generateHypotheses(count)
      setHypotheses(data)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [count])

  // Push new hypothesis events as they arrive
  useEffect(() => {
    if (pushEvents.length === 0) return
    const last = pushEvents[pushEvents.length - 1]
    if (!last.data?.id) return
    setHypotheses((prev) => {
      const exists = prev.some((h) => h.hypothesis_text === last.data?.text)
      if (exists) return prev
      return [{
        hypothesis_text: last.data?.text,
        confidence: last.data?.confidence,
        related_concepts: last.data?.concepts,
        supporting_evidence: [],
        suggested_experiments: [],
      }, ...prev].slice(0, 20)
    })
  }, [pushEvents.length])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold gradient-text">Hypothesis Dashboard</h1>
          <p className="text-slate-400 mt-1">AI-generated scientific hypotheses with supporting evidence</p>
        </div>
        <div className="flex items-center gap-3">
          <select value={count} onChange={e => setCount(Number(e.target.value))}
            className="px-3 py-1.5 rounded-lg glass-card text-sm text-slate-300 focus:outline-none">
            <option value={3}>3 hypotheses</option>
            <option value={5}>5 hypotheses</option>
            <option value={10}>10 hypotheses</option>
          </select>
          <button onClick={load} disabled={loading}
            className="glass-card px-4 py-2 flex items-center gap-2 text-sm text-slate-300 hover:text-white transition-colors">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Generate
          </button>
        </div>
      </div>

      {error && (
        <div className="glass-card p-4 border-rose-500/30">
          <p className="text-sm text-rose-400">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="glass-card p-5 animate-pulse">
              <div className="h-4 bg-slate-700 rounded w-1/4 mb-3" />
              <div className="h-5 bg-slate-700 rounded w-3/4 mb-2" />
              <div className="h-4 bg-slate-700 rounded w-1/2 mb-2" />
              <div className="h-20 bg-slate-700 rounded" />
            </div>
          ))}
        </div>
      ) : hypotheses.length === 0 ? (
        <div className="glass-card p-8 text-center">
          <Lightbulb className="h-8 w-8 text-slate-500 mx-auto mb-2" />
          <p className="text-slate-400">No hypotheses generated yet</p>
          <p className="text-sm text-slate-500 mt-1">Index some papers first, then generate hypotheses</p>
        </div>
      ) : (
        <div className="space-y-4">
          {hypotheses.map((item, i) => (
            <div key={i} className="glass-card p-5 hover:border-emerald-500/30 transition-all">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <Lightbulb className="h-4 w-4 text-yellow-400" />
                    <span className="text-xs font-medium text-emerald-400 uppercase">
                      Hypothesis #{i + 1}
                    </span>
                  </div>
                  <h3 className="text-lg font-semibold text-white mb-2">{item.hypothesis_text}</h3>
                  {item.related_concepts?.length > 0 && (
                    <div className="flex gap-1.5 mb-3">
                      {item.related_concepts.map((c: string, j: number) => (
                        <span key={j} className="px-2 py-0.5 rounded-full text-xs bg-purple-500/20 text-purple-300 border border-purple-500/20">
                          {c}
                        </span>
                      ))}
                    </div>
                  )}
                  {item.suggested_experiments?.length > 0 && (
                    <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                      <div className="flex items-center gap-1 mb-2">
                        <Beaker className="h-4 w-4 text-blue-400" />
                        <span className="text-sm font-medium text-blue-300">Suggested Experiments</span>
                      </div>
                      {item.suggested_experiments.map((exp: string, j: number) => (
                        <p key={j} className="text-sm text-slate-300 mt-1">• {exp}</p>
                      ))}
                    </div>
                  )}
                </div>
                <div className="ml-6 flex flex-col items-center gap-4">
                  <div className="text-center">
                    <div className="text-xs text-slate-500 mb-1">Confidence</div>
                    <div className="text-2xl font-bold text-emerald-400">
                      {item.confidence ? `${(item.confidence * 100).toFixed(0)}%` : 'N/A'}
                    </div>
                  </div>
                  {item.supporting_evidence?.length > 0 && (
                    <div className="text-center">
                      <div className="text-xs text-slate-500 mb-1">Evidence</div>
                      <div className="flex items-center gap-1">
                        <BookOpen className="h-4 w-4 text-blue-400" />
                        <span className="text-lg font-bold text-white">{item.supporting_evidence.length}</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
