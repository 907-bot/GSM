import { useEffect, useRef, useCallback, useState } from 'react'

const getWsBase = () => {
  const envTarget = (import.meta as any).env?.VITE_API_TARGET
  if (envTarget) {
    return envTarget.replace(/^http/, 'ws')
  }
  if (typeof window !== 'undefined') {
    return `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
  }
  return 'ws://localhost:8000'
}
const WS_BASE = getWsBase()
const RECONNECT_BASE = 1000
const RECONNECT_MAX = 30000
const PING_INTERVAL = 25000

export type EventPayload = {
  type: string
  data: Record<string, any>
  severity?: string
  timestamp?: string
  room?: string
  source?: string
  id?: string
}

type EventHandler = (event: EventPayload) => void

interface UseWebSocketOptions {
  room?: string
  onEvent?: EventHandler
  enabled?: boolean
}

export function useWebSocket({ room = 'all', onEvent, enabled = true }: UseWebSocketOptions = {}) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>()
  const pingTimerRef = useRef<ReturnType<typeof setInterval>>()
  const attemptRef = useRef(0)
  const enabledRef = useRef(enabled)
  const onEventRef = useRef(onEvent)
  const roomRef = useRef(room)
  const isManualDisconnectRef = useRef(false)
  const [connected, setConnected] = useState(false)
  const bufferRef = useRef<EventPayload[]>([])

  onEventRef.current = onEvent
  enabledRef.current = enabled
  roomRef.current = room

  const connect = useCallback(() => {
    if (!enabledRef.current) return
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) return

    isManualDisconnectRef.current = false
    const url = `${WS_BASE}/ws/${roomRef.current}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (isManualDisconnectRef.current) {
        ws.close()
        return
      }
      attemptRef.current = 0
      setConnected(true)

      // Flush buffer
      const buffered = bufferRef.current.splice(0)
      buffered.forEach((evt) => onEventRef.current?.(evt))

      // Heartbeat
      pingTimerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ action: 'ping' }))
        }
      }, PING_INTERVAL)
    }

    ws.onmessage = (msg) => {
      try {
        const event: EventPayload = JSON.parse(msg.data)
        if (event.type === 'pong') return
        if (document.hidden) {
          bufferRef.current.push(event)
        } else {
          onEventRef.current?.(event)
        }
      } catch {
        // ignore malformed
      }
    }

    ws.onclose = () => {
      setConnected(false)
      clearInterval(pingTimerRef.current)

      if (!isManualDisconnectRef.current && enabledRef.current) {
        const delay = Math.min(RECONNECT_BASE * Math.pow(2, attemptRef.current), RECONNECT_MAX)
        attemptRef.current += 1
        reconnectTimerRef.current = setTimeout(connect, delay)
      }
    }

    ws.onerror = () => {
      // Browser triggers onclose automatically
    }
  }, [])

  const disconnect = useCallback(() => {
    isManualDisconnectRef.current = true
    clearTimeout(reconnectTimerRef.current)
    clearInterval(pingTimerRef.current)

    if (wsRef.current) {
      const ws = wsRef.current
      wsRef.current = null
      if (ws.readyState === WebSocket.CONNECTING) {
        ws.onopen = () => {
          ws.close()
        }
      } else if (ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
    }
    setConnected(false)
  }, [])

  useEffect(() => {
    if (enabled) {
      connect()
    } else {
      disconnect()
    }
    return () => disconnect()
  }, [enabled, room, connect, disconnect])

  // Flush buffer when tab becomes visible
  useEffect(() => {
    const onVisible = () => {
      const buffered = bufferRef.current.splice(0)
      buffered.forEach((evt) => onEventRef.current?.(evt))
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [])

  const send = useCallback((action: string, payload: Record<string, any> = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, ...payload }))
    }
  }, [])

  const subscribe = useCallback((newRoom: string) => {
    send('subscribe', { room: newRoom })
  }, [send])

  return { connected, send, subscribe }
}
