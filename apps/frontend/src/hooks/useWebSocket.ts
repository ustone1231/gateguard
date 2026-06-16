import { useEffect, useRef, useState, useCallback } from 'react'
import type { GateGuardEvent } from '../types/event'
import { getAccessToken } from '../lib/auth'

const WS_URL = import.meta.env.VITE_WS_URL

export type WsMessage =
  | { type: 'event_new';          data: GateGuardEvent }
  | { type: 'event_updated';      data: GateGuardEvent }
  | { type: 'review_queue_added'; data: { queue_id: string; event_id: string } }
  | { type: 'heartbeat';          data: { ts: string } }

interface UseWebSocketResult {
  isConnected: boolean
  lastMessage: WsMessage | null
}

// 지수 백오프: 1s → 2s → 4s → ... → 30s
function backoff(attempt: number) {
  return Math.min(1000 * 2 ** attempt, 30000)
}

export function useWebSocket(): UseWebSocketResult {
  const wsRef      = useRef<WebSocket | null>(null)
  const attemptRef = useRef(0)
  const lastEventIdRef = useRef<string | null>(null)
  const [isConnected, setIsConnected]   = useState(false)
  const [lastMessage, setLastMessage]   = useState<WsMessage | null>(null)

  const connect = useCallback(() => {
    const token = getAccessToken()
    if (!token) return

    const url = lastEventIdRef.current
      ? `${WS_URL}?token=${token}&since=${lastEventIdRef.current}`
      : `${WS_URL}?token=${token}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      attemptRef.current = 0
    }

    ws.onmessage = (ev) => {
      const msg: WsMessage = JSON.parse(ev.data)
      if (msg.type === 'heartbeat') return
      if (msg.type === 'event_new' || msg.type === 'event_updated') {
        lastEventIdRef.current = msg.data.event_id
      }
      setLastMessage(msg)
    }

    ws.onclose = (ev) => {
      setIsConnected(false)
      wsRef.current = null

      // 토큰 만료 (api-contract.md §11-6)
      if (ev.code === 4401) {
        import('../lib/auth').then(({ logout }) => logout())
        return
      }

      // 지수 백오프 재연결
      const delay = backoff(attemptRef.current)
      attemptRef.current += 1
      setTimeout(connect, delay)
    }

    ws.onerror = () => ws.close()
  }, [])

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect])

  return { isConnected, lastMessage }
}
