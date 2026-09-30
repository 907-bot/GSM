import { ReactNode, useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Compass,
  AlertTriangle,
  Lightbulb,
  Network,
  Search,
  FileText,
  Settings,
  Brain,
  ChevronLeft,
  ChevronRight,
  Wifi,
  WifiOff,
  MessageSquare,
  GitCompare,
  Columns,
  Route,
  Clock,
  Sparkles,
  BookOpen,
  LogOut,
} from 'lucide-react'
import { clsx } from 'clsx'
import { NotificationBell } from './NotificationBell'
import { useEventStore } from '../store/eventStore'
import { useWebSocket } from '../hooks/useWebSocket'
import { useAuthStore } from '../store/authStore'

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Gap Finder', href: '/gaps', icon: Sparkles },
  { name: 'Paper Publisher', href: '/publish', icon: BookOpen },
  { name: 'AI Chat', href: '/chat', icon: MessageSquare },
  { name: 'Discovery Feed', href: '/discovery', icon: Compass },
  { name: 'Missing Links', href: '/missing-links', icon: GitCompare },
  { name: 'Novelty Score', href: '/novelty', icon: Sparkles },
  { name: 'Paper Compare', href: '/papers/compare', icon: Columns },
  { name: 'Roadmap Generator', href: '/roadmap', icon: Route },
  { name: 'Discovery Timeline', href: '/timeline', icon: Clock },
  { name: 'Bottlenecks', href: '/bottlenecks', icon: AlertTriangle },
  { name: 'Hypotheses', href: '/hypotheses', icon: Lightbulb },
  { name: 'Graph Explorer', href: '/graph', icon: Network },
  { name: 'Search', href: '/search', icon: Search },
  { name: 'Papers', href: '/papers', icon: FileText },
  { name: 'Settings', href: '/settings', icon: Settings },
]

interface LayoutProps {
  children: ReactNode
}

export function Layout({ children }: LayoutProps) {
  const [collapsed, setCollapsed] = useState(false)
  const location = useLocation()
  const pushEvent = useEventStore((s) => s.pushEvent)
  const setConnected = useEventStore((s) => s.setConnected)
  const { user, logout } = useAuthStore()

  const { connected } = useWebSocket({
    room: 'all',
    onEvent: (event) => {
      pushEvent(event)
    },
    enabled: true,
  })

  // Sync connected state to store safely inside useEffect
  useEffect(() => {
    setConnected(connected)
  }, [connected, setConnected])

  return (
    <div className="flex h-screen scientific-gradient">
      {/* Sidebar */}
      <aside
        className={clsx(
          'relative flex flex-col border-r border-white/10 bg-white/5 backdrop-blur-xl transition-all duration-300',
          collapsed ? 'w-16' : 'w-64'
        )}
      >
        {/* Logo + connection status */}
        <div className="flex h-16 items-center justify-between px-4 border-b border-white/10">
          <div className="flex items-center">
            <Brain className="h-8 w-8 text-blue-400 shrink-0" />
            {!collapsed && (
              <span className="ml-3 font-bold gradient-text text-lg whitespace-nowrap">
                GSM-OS
              </span>
            )}
          </div>
          <button
            className={clsx(
              'p-1.5 rounded-lg transition-colors',
              connected ? 'text-green-400' : 'text-red-400'
            )}
            title={connected ? 'Connected' : 'Disconnected'}
          >
            {connected ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-2 py-4 space-y-1">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href
            return (
              <Link
                key={item.name}
                to={item.href}
                className={clsx(
                  'flex items-center px-3 py-2.5 rounded-lg transition-all duration-200 group',
                  isActive
                    ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                    : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                )}
              >
                <item.icon className="h-5 w-5 shrink-0" />
                {!collapsed && (
                  <span className="ml-3 text-sm font-medium">{item.name}</span>
                )}
              </Link>
            )
          })}
        </nav>

        {/* Notification bell */}
        {!collapsed && (
          <div className="px-3 py-2 border-t border-white/10">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500 font-medium">Notifications</span>
              <NotificationBell />
            </div>
          </div>
        )}

        {/* User profile */}
        <div className="border-t border-white/10 bg-white/5 py-2">
          {collapsed ? (
            <div className="flex flex-col items-center gap-2 py-1">
              <div 
                className="h-8 w-8 rounded-full bg-gradient-to-tr from-blue-500 to-purple-500 flex items-center justify-center text-white text-xs font-semibold shadow-md"
                title={user?.name || 'User'}
              >
                {user?.name ? user.name[0].toUpperCase() : '?'}
              </div>
              <button
                onClick={logout}
                className="text-slate-400 hover:text-rose-400 p-1.5 rounded transition-colors"
                title="Log Out"
              >
                <LogOut className="h-4.5 w-4.5" />
              </button>
            </div>
          ) : (
            <div className="px-3 py-2 flex items-center gap-3">
              <div className="h-9 w-9 rounded-full bg-gradient-to-tr from-blue-500 to-purple-500 flex items-center justify-center text-white font-semibold shadow-md">
                {user?.name ? user.name[0].toUpperCase() : '?'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-white truncate">{user?.name || 'User'}</p>
                <span className="inline-block text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 bg-blue-500/20 text-blue-400 rounded mt-0.5">
                  {user?.role || 'viewer'}
                </span>
              </div>
              <button
                onClick={logout}
                className="text-slate-400 hover:text-rose-400 p-1.5 rounded transition-colors"
                title="Log Out"
              >
                <LogOut className="h-4.5 w-4.5" />
              </button>
            </div>
          )}
        </div>

        {/* Collapse button */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center justify-center h-12 border-t border-white/10 text-slate-400 hover:text-slate-200 transition-colors"
        >
          {collapsed ? (
            <ChevronRight className="h-5 w-5" />
          ) : (
            <ChevronLeft className="h-5 w-5" />
          )}
        </button>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-6">
        {children}
      </main>
    </div>
  )
}
