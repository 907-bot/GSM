import { useEventStore, TaskStatus } from '../store/eventStore'
import { CheckCircle2, XCircle, Loader2, Clock } from 'lucide-react'
import { clsx } from 'clsx'

function TaskRow({ task }: { task: TaskStatus }) {
  const ago = (ts: string) => {
    const diff = Date.now() - new Date(ts).getTime()
    const s = Math.floor(diff / 1000)
    if (s < 60) return `${s}s ago`
    const m = Math.floor(s / 60)
    return `${m}m ago`
  }

  return (
    <div className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-white/5 transition-colors">
      {task.status === 'started' && <Loader2 className="h-4 w-4 text-blue-400 animate-spin shrink-0" />}
      {task.status === 'completed' && <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />}
      {task.status === 'failed' && <XCircle className="h-4 w-4 text-red-400 shrink-0" />}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-200 truncate">
            {task.taskName.replace(/_/g, ' ')}
          </span>
          <span className={clsx(
            'text-xs ml-2 shrink-0',
            task.status === 'completed' && 'text-emerald-400',
            task.status === 'started' && 'text-blue-400',
            task.status === 'failed' && 'text-red-400',
          )}>
            {task.status}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
          <Clock className="h-3 w-3" />
          <span>{ago(task.startedAt)}</span>
          {task.error && <span className="text-red-400 truncate">· {task.error}</span>}
        </div>
      </div>
    </div>
  )
}

export function TaskStatusPanel() {
  const tasks = useEventStore((s) => s.tasks)
  const active = tasks.filter((t) => t.status === 'started')

  if (tasks.length === 0) {
    return (
      <div className="glass-card p-4">
        <div className="flex items-center gap-2 mb-3">
          <CheckCircle2 className="h-4 w-4 text-slate-600" />
          <h3 className="text-sm font-semibold text-white">Tasks</h3>
        </div>
        <p className="text-xs text-slate-500 text-center py-2">No recent tasks. Task activity will appear here.</p>
      </div>
    )
  }

  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-3">
        {active.length > 0 ? (
          <Loader2 className="h-4 w-4 text-blue-400 animate-spin" />
        ) : (
          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
        )}
        <h3 className="text-sm font-semibold text-white">
          Tasks
          {active.length > 0 && (
            <span className="ml-2 text-xs text-blue-400 font-normal">({active.length} active)</span>
          )}
        </h3>
      </div>
      <div className="space-y-0.5 max-h-60 overflow-y-auto">
        {tasks.slice(0, 10).map((t) => (
          <TaskRow key={t.taskId} task={t} />
        ))}
      </div>
    </div>
  )
}
