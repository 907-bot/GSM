import { create } from 'zustand'

export interface EventPayload {
  type: string
  data: Record<string, any>
  severity?: string
  timestamp?: string
  room?: string
  source?: string
  id?: string
}

export interface AgentSourceProgress {
  domain: string
  query: string
  source: string
  current: number
  total: number
  status: 'querying' | 'done' | 'failed'
  count?: number
  error?: string
}

export interface AgentSearchProgress {
  domain: string
  keyword: string
  current_keyword: number
  total_keywords: number
  status: 'searching' | 'processing' | 'processing_paper'
  total_papers?: number
  current_paper?: number
  paper_title?: string
}

export interface TaskStatus {
  taskId: string
  taskName: string
  status: 'started' | 'completed' | 'failed'
  error?: string
  startedAt: string
  completedAt?: string
}

export interface Notification {
  id: string
  title: string
  message: string
  severity: EventPayload['severity']
  type: string
  timestamp: string
  read: boolean
  actionUrl?: string
}

interface EventState {
  /** Ring buffer of recent events per room */
  events: Record<string, EventPayload[]>
  /** Unread notifications (messages with severity >= warning) */
  notifications: Notification[]
  /** Latest discovery events */
  discoveries: EventPayload[]
  /** Latest contradiction events */
  contradictions: EventPayload[]
  /** Latest bottleneck events */
  bottlenecks: EventPayload[]
  /** Latest hypothesis events */
  hypotheses: EventPayload[]
  /** Latest system metrics */
  systemMetrics: Record<string, any>
  /** WebSocket status */
  connected: boolean
  /** Agent source-level progress (domain -> progress) */
  agentSourceProgress: Record<string, AgentSourceProgress[]>
  /** Agent search-level progress (domain -> progress) */
  agentSearchProgress: Record<string, AgentSearchProgress>
  /** Celery task statuses */
  tasks: TaskStatus[]

  pushEvent: (event: EventPayload) => void
  setConnected: (connected: boolean) => void
  markNotificationRead: (id: string) => void
  dismissNotification: (id: string) => void
  clearEvents: (room?: string) => void
}

const MAX_EVENTS_PER_ROOM = 200
const MAX_NOTIFICATIONS = 50
const MAX_TASKS = 30

export const useEventStore = create<EventState>((set, get) => ({
  events: {},
  notifications: [],
  discoveries: [],
  contradictions: [],
  bottlenecks: [],
  hypotheses: [],
  systemMetrics: {},
  connected: false,
  agentSourceProgress: {},
  agentSearchProgress: {},
  tasks: [],

  pushEvent: (event) => {
    const room = event.room || 'all'
    const events = { ...get().events }
    const roomEvents = [...(events[room] || []), event].slice(-MAX_EVENTS_PER_ROOM)
    events[room] = roomEvents

    const upd: Partial<EventState> = { events }

    // Route to typed arrays
    if (event.type.includes('contradiction') || event.type.includes('contradiction')) {
      upd.contradictions = [...get().contradictions, event].slice(-20)
    }
    if (event.type.includes('bottleneck')) {
      upd.bottlenecks = [...get().bottlenecks, event].slice(-20)
    }
    if (event.type.includes('hypothesis')) {
      upd.hypotheses = [...get().hypotheses, event].slice(-20)
    }
    if (event.type.startsWith('agent.') || event.type.startsWith('paper.')) {
      upd.discoveries = [...get().discoveries, event].slice(-50)
    }
    if (event.type === 'system.metrics') {
      upd.systemMetrics = { ...get().systemMetrics, ...event.data }
    }

    // Agent source-level progress
    if (event.type === 'agent.source.progress') {
      const d = event.data
      const domain = d.domain
      const current = get().agentSourceProgress
      const existing = current[domain] || []
      const updated = existing.filter((p) => p.source !== d.source)
      updated.push({
        domain,
        query: d.query,
        source: d.source,
        current: d.current,
        total: d.total,
        status: d.status,
        count: d.count,
        error: d.error,
      })
      upd.agentSourceProgress = { ...current, [domain]: updated }
    }

    // Agent search-level progress
    if (event.type === 'agent.search.progress') {
      const d = event.data
      upd.agentSearchProgress = {
        ...get().agentSearchProgress,
        [d.domain]: {
          domain: d.domain,
          keyword: d.keyword,
          current_keyword: d.current_keyword,
          total_keywords: d.total_keywords,
          status: d.status,
          total_papers: d.total_papers,
          current_paper: d.current_paper,
          paper_title: d.paper_title,
        },
      }
    }

    // Celery task status changes
    if (event.type === 'task.status.change') {
      const d = event.data
      if (d.status === 'started') {
        const task: TaskStatus = {
          taskId: d.task_id,
          taskName: d.task_name,
          status: 'started',
          startedAt: event.timestamp || new Date().toISOString(),
        }
        upd.tasks = [task, ...get().tasks].slice(0, MAX_TASKS)
      } else {
        upd.tasks = get().tasks.map((t) =>
          t.taskId === d.task_id
            ? { ...t, status: d.status, error: d.error, completedAt: event.timestamp || new Date().toISOString() }
            : t
        )
      }
    }

    // Task progress
    if (event.type === 'task.progress') {
      // Progress events are stored in the room buffer but don't need special state
    }

    // Notifications for warnings and criticals
    if (event.severity === 'warning' || event.severity === 'critical') {
      const notification: Notification = {
        id: event.id || `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
        title: event.type.replace(/\./g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        message: event.data?.explanation || event.data?.error || JSON.stringify(event.data).slice(0, 120),
        severity: event.severity,
        type: event.type,
        timestamp: event.timestamp || new Date().toISOString(),
        read: false,
      }
      upd.notifications = [...get().notifications, notification].slice(-MAX_NOTIFICATIONS)
    }

    set(upd as EventState)
  },

  setConnected: (connected) => set({ connected }),

  markNotificationRead: (id) => {
    set({
      notifications: get().notifications.map((n) =>
        n.id === id ? { ...n, read: true } : n
      ),
    })
  },

  dismissNotification: (id) => {
    set({
      notifications: get().notifications.filter((n) => n.id !== id),
    })
  },

  clearEvents: (room) => {
    if (room) {
      const events = { ...get().events }
      delete events[room]
      set({ events })
    } else {
      set({
        events: {},
        discoveries: [],
        contradictions: [],
        bottlenecks: [],
        hypotheses: [],
        notifications: [],
        agentSourceProgress: {},
        agentSearchProgress: {},
        tasks: [],
      })
    }
  },
}))
