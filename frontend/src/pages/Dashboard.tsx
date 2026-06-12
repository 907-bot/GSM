import { useState, useEffect } from 'react'
import { Brain, Network, Lightbulb, AlertTriangle, Activity, BookOpen } from 'lucide-react'
import { api } from '../api'
import { useEventStore } from '../store/eventStore'

export function Dashboard() {
  const [health, setHealth] = useState<any>(null)
  const [memoryStats, setMemoryStats] = useState<any>(null)
  const [graphHealth, setGraphHealth] = useState<any>(null)
  const [contradictions, setContradictions] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const systemMetrics = useEventStore((s) => s.systemMetrics)
  const connected = useEventStore((s) => s.connected)

  useEffect(() => {
    async function load() {
      try {
        const [h, ms, gh, cs] = await Promise.all([
          api.health(),
          api.memoryStats(),
          api.graphHealth(),
          api.contradictionSummary(),
        ])
        setHealth(h)
        setMemoryStats(ms)
        setGraphHealth(gh)
        setContradictions(cs)
      } catch (e: any) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const statsCards = [
    {
      label: 'Papers Indexed',
      value: memoryStats?.semantic?.papers ?? systemMetrics.papers ?? '—',
      icon: BookOpen,
      color: 'text-blue-400',
      bg: 'bg-blue-500/10',
    },
    {
      label: 'Concepts Mapped',
      value: memoryStats?.semantic?.concepts ?? systemMetrics.concepts ?? '—',
      icon: Network,
      color: 'text-purple-400',
      bg: 'bg-purple-500/10',
    },
    {
      label: 'Relationships',
      value: memoryStats?.semantic?.relationships ?? systemMetrics.relationships ?? '—',
      icon: Activity,
      color: 'text-emerald-400',
      bg: 'bg-emerald-500/10',
    },
    {
      label: 'Bottlenecks',
      value: contradictions?.total_contradictions ?? systemMetrics.bottlenecks ?? '—',
      icon: AlertTriangle,
      color: 'text-orange-400',
      bg: 'bg-orange-500/10',
    },
    {
      label: 'Graph Health',
      value: graphHealth ? `${(graphHealth.health_score * 100).toFixed(0)}%` : systemMetrics.health_score != null ? `${(systemMetrics.health_score * 100).toFixed(0)}%` : '—',
      icon: Brain,
      color: 'text-yellow-400',
      bg: 'bg-yellow-500/10',
    },
    {
      label: 'Contradictions',
      value: contradictions?.high_confidence ?? systemMetrics.contradictions ?? '—',
      icon: Lightbulb,
      color: 'text-rose-400',
      bg: 'bg-rose-500/10',
    },
  ]

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <AlertTriangle className="h-12 w-12 text-rose-400 mx-auto mb-3" />
          <p className="text-slate-400">Unable to connect to backend</p>
          <p className="text-sm text-slate-500 mt-1">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold gradient-text">Scientific Command Center</h1>
          <p className="text-slate-400 mt-1">Global Scientific Memory OS — Real-time Dashboard</p>
        </div>
        <div className="flex items-center gap-3">
          {connected && (
            <span className="flex items-center gap-1.5 text-xs text-emerald-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Live
            </span>
          )}
          <div className="flex items-center gap-2 glass-card px-4 py-2">
            <div className={`w-2 h-2 rounded-full animate-pulse ${health?.status === 'healthy' ? 'bg-emerald-400' : 'bg-rose-400'}`} />
            <span className="text-sm text-slate-300">{loading ? 'Loading…' : health?.status === 'healthy' ? 'System Active' : 'Degraded'}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-6 gap-4">
        {statsCards.map(s => (
          <div key={s.label} className="glass-card p-4">
            <div className={`p-2 rounded-lg ${s.bg} inline-flex mb-3`}>
              <s.icon className={`h-5 w-5 ${s.color}`} />
            </div>
            <div className="text-2xl font-bold text-white">{loading ? '…' : s.value}</div>
            <div className="text-sm text-slate-400 mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white mb-4">System Health</h2>
          <div className="space-y-3">
            {Object.entries(health?.services ?? {}).map(([name, status]) => (
              <div key={name} className="flex items-center justify-between">
                <span className="text-sm text-slate-300 capitalize">{name}</span>
                <span className={`flex items-center gap-1.5 text-sm ${status === 'up' ? 'text-emerald-400' : 'text-rose-400'}`}>
                  <div className={`w-1.5 h-1.5 rounded-full ${status === 'up' ? 'bg-emerald-400' : 'bg-rose-400'}`} />
                  {status as string}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card p-6">
          <div className="flex items-center gap-2 mb-4">
            <Brain className="h-5 w-5 text-purple-400" />
            <h2 className="text-lg font-semibold text-white">Memory Statistics</h2>
          </div>
          {loading ? (
            <div className="animate-pulse space-y-3">
              {[1, 2, 3].map(i => <div key={i} className="h-5 bg-slate-700 rounded w-3/4" />)}
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-sm text-slate-300">Semantic Concepts</span>
                <span className="text-sm font-medium text-white">{memoryStats?.semantic?.concepts ?? 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-slate-300">Papers Stored</span>
                <span className="text-sm font-medium text-white">{memoryStats?.semantic?.papers ?? 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-slate-300">Graph Relationships</span>
                <span className="text-sm font-medium text-white">{memoryStats?.semantic?.relationships ?? 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-slate-300">Graph Health</span>
                <span className={`text-sm font-medium ${graphHealth ? 'text-emerald-400' : 'text-slate-400'}`}>
                  {graphHealth ? `${(graphHealth.health_score * 100).toFixed(1)}%` : 'N/A'}
                </span>
              </div>
            </div>
          )}
          {graphHealth?.recommendations?.length > 0 && (
            <div className="mt-4 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
              <p className="text-xs text-blue-300 font-medium mb-1">Recommendations</p>
              {graphHealth.recommendations.slice(0, 2).map((r: string, i: number) => (
                <p key={i} className="text-xs text-slate-400 mt-0.5">• {r}</p>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
