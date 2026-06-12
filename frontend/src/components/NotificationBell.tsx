import { useState, useRef, useEffect } from 'react'
import { Bell, X, Check, AlertTriangle, Info, AlertCircle } from 'lucide-react'
import { clsx } from 'clsx'
import { useEventStore } from '../store/eventStore'

const severityIcon: Record<string, React.ComponentType<{ className?: string }>> = {
  debug: Info,
  info: Info,
  warning: AlertTriangle,
  critical: AlertCircle,
}

function sev(key: string | undefined, map: Record<string, string>): string {
  return map[key ?? 'info'] ?? 'text-slate-400'
}

const severityColor: Record<string, string> = {
  debug: 'text-slate-400',
  info: 'text-blue-400',
  warning: 'text-amber-400',
  critical: 'text-red-400',
}

const severityBg: Record<string, string> = {
  debug: 'bg-slate-500/10',
  info: 'bg-blue-500/10',
  warning: 'bg-amber-500/10',
  critical: 'bg-red-500/10',
}

export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const notifications = useEventStore((s) => s.notifications)
  const markRead = useEventStore((s) => s.markNotificationRead)
  const dismiss = useEventStore((s) => s.dismissNotification)

  const unreadCount = notifications.filter((n) => !n.read).length

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="relative p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-all"
      >
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 bg-slate-800 border border-white/10 rounded-xl shadow-2xl backdrop-blur-xl z-50 max-h-96 overflow-hidden flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
            <h3 className="text-sm font-semibold text-slate-200">Notifications</h3>
            {unreadCount > 0 && (
              <button
                onClick={() => notifications.forEach((n) => markRead(n.id))}
                className="text-xs text-blue-400 hover:text-blue-300"
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="overflow-y-auto flex-1">
            {notifications.length === 0 ? (
              <p className="text-center text-slate-500 text-sm py-8">No notifications</p>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  className={clsx(
                    'flex items-start gap-3 px-4 py-3 border-b border-white/5 transition-colors',
                    n.read ? 'opacity-60' : 'bg-white/5'
                  )}
                >
                  <div className={clsx('p-1.5 rounded-lg shrink-0', sev(n.severity, severityBg))}>
                    {(() => {
                      const Icon = severityIcon[n.severity ?? 'info'] ?? Info
                      return <Icon className={clsx('h-4 w-4', sev(n.severity, severityColor))} />
                    })()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-200 truncate">{n.title}</p>
                    <p className="text-xs text-slate-400 mt-0.5 line-clamp-2">{n.message}</p>
                    <p className="text-[10px] text-slate-500 mt-1">
                      {new Date(n.timestamp).toLocaleTimeString()}
                    </p>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    {!n.read && (
                      <button
                        onClick={() => markRead(n.id)}
                        className="p-1 rounded text-slate-500 hover:text-blue-400 hover:bg-white/5"
                      >
                        <Check className="h-3.5 w-3.5" />
                      </button>
                    )}
                    <button
                      onClick={() => dismiss(n.id)}
                      className="p-1 rounded text-slate-500 hover:text-red-400 hover:bg-white/5"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
