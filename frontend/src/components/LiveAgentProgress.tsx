import { useEventStore, AgentSourceProgress, AgentSearchProgress } from '../store/eventStore'
import { Search, CheckCircle2, XCircle, Loader2, BookOpen } from 'lucide-react'
import { clsx } from 'clsx'

const DOMAIN_COLORS: Record<string, string> = {
  biology: 'from-green-500 to-emerald-600',
  ai: 'from-purple-500 to-violet-600',
  materials: 'from-red-500 to-rose-600',
  medicine: 'from-blue-500 to-indigo-600',
  chemistry: 'from-cyan-500 to-teal-600',
  physics: 'from-amber-500 to-orange-600',
}

const DOMAIN_BORDER: Record<string, string> = {
  biology: 'border-green-500/30',
  ai: 'border-purple-500/30',
  materials: 'border-red-500/30',
  medicine: 'border-blue-500/30',
  chemistry: 'border-cyan-500/30',
  physics: 'border-amber-500/30',
}

function SourceRow({ progress }: { progress: AgentSourceProgress }) {
  const pct = ((progress.current - 1 + (progress.status === 'done' ? 1 : 0)) / progress.total) * 100

  return (
    <div className="flex items-center gap-3 py-2">
      <div className="flex-1">
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm text-slate-300 capitalize">{progress.source.replace(/_/g, ' ')}</span>
          <div className="flex items-center gap-2">
            {progress.status === 'querying' && <Loader2 className="h-3.5 w-3.5 text-blue-400 animate-spin" />}
            {progress.status === 'done' && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />}
            {progress.status === 'failed' && <XCircle className="h-3.5 w-3.5 text-red-400" />}
            <span className="text-xs text-slate-500">{progress.count ?? 0} papers</span>
          </div>
        </div>
        <div className="h-1.5 bg-slate-700/50 rounded-full overflow-hidden">
          <div
            className={clsx(
              'h-full rounded-full transition-all duration-500',
              progress.status === 'querying' && 'bg-blue-500 animate-pulse',
              progress.status === 'done' && 'bg-emerald-500',
              progress.status === 'failed' && 'bg-red-500',
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  )
}

function KeywordProgress({ progress }: { progress: AgentSearchProgress }) {
  const pct = ((progress.current_keyword - 1) / progress.total_keywords) * 100
  const paperPct = progress.total_papers
    ? ((progress.current_paper ?? 0) / progress.total_papers) * 100
    : 0

  return (
    <div className="space-y-1.5 mb-3">
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-400">
          Keyword: <span className="text-slate-200 font-medium">{progress.keyword}</span>
        </span>
        <span className="text-slate-500">
          {progress.current_keyword} / {progress.total_keywords}
        </span>
      </div>
      {progress.status === 'processing_paper' && (
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <BookOpen className="h-3 w-3" />
          <span className="truncate max-w-[200px]">{progress.paper_title || 'Processing…'}</span>
          <span className="ml-auto">
            {progress.current_paper}/{progress.total_papers}
          </span>
        </div>
      )}
      <div className="flex gap-1">
        <div className="flex-1 h-1 bg-slate-700/50 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full bg-blue-500 transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
        {progress.status === 'processing' || progress.status === 'processing_paper' ? (
          <div className="flex-1 h-1 bg-slate-700/50 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-emerald-500 transition-all duration-500"
              style={{ width: `${paperPct}%` }}
            />
          </div>
        ) : null}
      </div>
    </div>
  )
}

export function LiveAgentProgress() {
  const sourceProgress = useEventStore((s) => s.agentSourceProgress)
  const searchProgress = useEventStore((s) => s.agentSearchProgress)

  const domains = Object.keys(sourceProgress)
  const searchDomains = Object.keys(searchProgress)
  const hasAny = domains.length > 0 || searchDomains.length > 0
  const allDomains = [...new Set([...domains, ...searchDomains])]

  return (
    <div className="glass-card p-5 border-blue-500/20">
      <div className="flex items-center gap-2 mb-4">
        <Search className="h-4 w-4 text-blue-400 animate-pulse" />
        <h3 className="text-sm font-semibold text-white">Active Agent Searches</h3>
      </div>

      <div className="space-y-4">
        {!hasAny ? (
          <div className="text-center py-4">
            <Search className="h-6 w-6 text-slate-600 mx-auto mb-2" />
            <p className="text-sm text-slate-500">Waiting for agent searches…</p>
            <p className="text-xs text-slate-600 mt-1">Progress will appear here when agents run</p>
          </div>
        ) : (
          allDomains.map((domain) => {
            const sources = sourceProgress[domain] || []
            const search = searchProgress[domain]
            const doneCount = sources.filter((s) => s.status === 'done' || s.status === 'failed').length

            return (
            <div
              key={domain}
              className={clsx(
                'rounded-lg border p-4 bg-white/5',
                DOMAIN_BORDER[domain] || 'border-white/10'
              )}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className={clsx('w-2 h-2 rounded-full bg-gradient-to-r', DOMAIN_COLORS[domain] || 'from-slate-500 to-slate-600')} />
                  <span className="text-sm font-medium text-white capitalize">{domain}</span>
                </div>
                <span className="text-xs text-slate-500">
                  {doneCount}/{sources.length} sources done
                </span>
              </div>

              {search && <KeywordProgress progress={search} />}

              {sources.length > 0 && (
                <div className="space-y-1">
                  {sources.map((s) => (
                    <SourceRow key={s.source} progress={s} />
                  ))}
                </div>
              )}
            </div>
          )
        }))}
      </div>
    </div>
  )
}
