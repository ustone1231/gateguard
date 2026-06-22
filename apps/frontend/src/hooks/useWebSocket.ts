import { useEffect, useRef, useState } from 'react'
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
}

// 지수 백오프: 1s → 2s → 4s → ... → 30s
function backoff(attempt: number) {
  return Math.min(1000 * 2 ** attempt, 30000)
}

export function useWebSocket(onMessage: (msg: WsMessage) => void): UseWebSocketResult {
  const wsRef          = useRef<WebSocket | null>(null)
  const attemptRef     = useRef(0)
  const lastEventIdRef = useRef<string | null>(null)
  const timerRef       = useRef<ReturnType<typeof setTimeout> | null>(null)
  const onMessageRef = useRef(onMessage)
  const [isConnected, setIsConnected] = useState(false)

  useEffect(() => {
    onMessageRef.current = onMessage
  })

  useEffect(() => {
    function connect() {
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
        onMessageRef.current(msg)
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
        timerRef.current = setTimeout(connect, delay)
      }

      ws.onerror = () => ws.close()
    }

    connect()

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      wsRef.current?.close()
    }
  }, [])

  return { isConnected }
}
