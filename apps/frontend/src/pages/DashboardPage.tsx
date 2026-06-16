import { useEffect, useState } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import api from '../lib/api'
import type { GateGuardEvent } from '../types/event'
import { playAlert } from '../lib/sound'
import styles from './DashboardPage.module.css'

interface KpiData {
  totalToday:    number
  pending:       number
  falsePositive: number
  health:        'ok' | 'degraded' | 'unknown'
  byGate:        Record<string, number>
}

const EVENT_LABELS: Record<string, string> = {
  jump:              '점프',
  crawling:          '기어가기',
  tailgating:        '꼬리물기',
  unpaid:            '우회/역방향',
  gate_passage:      '통과',
  confirmed_unpaid:  '무임승차 확정',
  confirmed_misuse:  '우대카드 부정사용',
}

const SEVERITY_COLOR: Record<string, string> = {
  info:     styles.info,
  warning:  styles.warning,
  critical: styles.critical,
}

function formatTime(ts: string) {
  return new Date(ts).toLocaleTimeString('ko-KR', { timeZone: 'Asia/Seoul' })
}

export default function DashboardPage() {
  const { isConnected, lastMessage } = useWebSocket()
  const [events, setEvents] = useState<GateGuardEvent[]>([])
  const [kpi, setKpi] = useState<KpiData>({ totalToday: 0, pending: 0, falsePositive: 0, health: 'unknown', byGate: {} })

  useEffect(() => {
    async function fetchKpi() {
      const [statsRes, pendingRes, fpRes, healthRes] = await Promise.allSettled([
        api.get('/stats', { params: { period: 'day' } }),
        api.get('/review-queue', { params: { status: 'pending', limit: 200 } }),
        api.get('/review-queue', { params: { status: 'false_positive', limit: 200 } }),
        api.get('/health'),
      ])

      setKpi({
        totalToday: statsRes.status === 'fulfilled'
          ? Object.values(statsRes.value.data.by_type as Record<string, number>).reduce((a, b) => a + b, 0)
          : 0,
        byGate: statsRes.status === 'fulfilled'
          ? (statsRes.value.data.by_gate as Record<string, number>) ?? {}
          : {},
        pending: pendingRes.status === 'fulfilled'
          ? (pendingRes.value.data.total ?? pendingRes.value.data.data.length)
          : 0,
        falsePositive: fpRes.status === 'fulfilled'
          ? (fpRes.value.data.total ?? fpRes.value.data.data.length)
          : 0,
        health: healthRes.status === 'fulfilled'
          ? healthRes.value.data.status
          : 'unknown',
      })
    }
    fetchKpi()
  }, [])

  // 브라우저 알림 권한 요청
  useEffect(() => {
    if (Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }, [])

  // 새 이벤트 수신 시 처리
  useEffect(() => {
    if (!lastMessage) return

    if (lastMessage.type === 'event_new') {
      const event = lastMessage.data
      setEvents((prev) => [event, ...prev].slice(0, 50))

      const severity = event.severity ?? 'info'
      playAlert(severity)

      if (Notification.permission === 'granted') {
        new Notification(`GateGuard — ${EVENT_LABELS[event.event_type] ?? event.event_type}`, {
          body: `게이트 ${event.gate_section_id} · ${formatTime(event.timestamp)}`,
        })
      }
    }

    if (lastMessage.type === 'event_updated') {
      const updated = lastMessage.data
      setEvents((prev) =>
        prev.map((e) => (e.event_id === updated.event_id ? updated : e))
      )
    }
  }, [lastMessage])

  return (
    <div className={styles.page}>

      {/* KPI 카드 */}
      <div className={styles.kpiRow}>
        <div className={styles.kpiCard}>
          <span className={styles.kpiLabel}>오늘 이벤트</span>
          <span className={styles.kpiValue}>{kpi.totalToday}</span>
        </div>
        <div className={styles.kpiCard}>
          <span className={styles.kpiLabel}>미처리</span>
          <span className={`${styles.kpiValue} ${kpi.pending > 0 ? styles.kpiWarn : ''}`}>
            {kpi.pending}
          </span>
        </div>
        <div className={styles.kpiCard}>
          <span className={styles.kpiLabel}>오탐</span>
          <span className={styles.kpiValue}>{kpi.falsePositive}</span>
        </div>
        <div className={styles.kpiCard}>
          <span className={styles.kpiLabel}>시스템 상태</span>
          <span className={`${styles.kpiValue} ${kpi.health === 'ok' ? styles.kpiOk : kpi.health === 'degraded' ? styles.kpiCrit : styles.kpiUnknown}`}>
            {kpi.health === 'ok' ? '정상' : kpi.health === 'degraded' ? '주의' : '-'}
          </span>
        </div>
      </div>

      {/* 개찰구별 상태 그리드 (api-contract.md §2-4 by_gate) */}
      {Object.keys(kpi.byGate).length > 0 && (
        <div>
          <p className={styles.gridTitle}>개찰구별 오늘 이벤트</p>
          <div className={styles.gateGrid}>
            {Object.entries(kpi.byGate)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([gateId, count]) => (
                <div
                  key={gateId}
                  className={`${styles.gateCard} ${count > 0 ? styles.gateActive : styles.gateIdle}`}
                >
                  <span className={styles.gateId}>{gateId}</span>
                  <span className={styles.gateCount}>{count}</span>
                  <span className={styles.gateStatus}>{count > 0 ? '활성' : '없음'}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      <div className={styles.header}>
        <h2 className={styles.title}>실시간 알림</h2>
        <span className={isConnected ? styles.connected : styles.disconnected}>
          {isConnected ? '● 연결됨' : '● 연결 끊김'}
        </span>
      </div>

      <div className={styles.stream}>
        {events.length === 0 && (
          <p className={styles.empty}>이벤트를 기다리는 중...</p>
        )}
        {events.map((event) => (
          <div
            key={event.event_id}
            className={`${styles.card} ${SEVERITY_COLOR[event.severity ?? 'info']}`}
          >
            <div className={styles.cardTop}>
              <span className={styles.type}>
                {EVENT_LABELS[event.event_type] ?? event.event_type}
              </span>
              <span className={styles.gate}>{event.gate_section_id}</span>
              <span className={styles.time}>{formatTime(event.timestamp)}</span>
            </div>
            <div className={styles.cardBottom}>
              <span>카메라 {event.camera_id}</span>
              {event.confidence != null && (
                <span>신뢰도 {Math.round(event.confidence * 100)}%</span>
              )}
              {event.severity && (
                <span className={styles.badge}>{event.severity.toUpperCase()}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
