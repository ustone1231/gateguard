import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../lib/api'
import type { GateGuardEvent } from '../types/event'
import styles from './EventListPage.module.css'

const EVENT_TYPES = [
  'gate_passage', 'jump', 'crawling', 'tailgating',
  'unpaid', 'confirmed_unpaid', 'confirmed_misuse',
]
const SEVERITIES = ['info', 'warning', 'critical']

const EVENT_LABELS: Record<string, string> = {
  jump:             '점프',
  crawling:         '기어가기',
  tailgating:       '꼬리물기',
  unpaid:           '우회/역방향',
  gate_passage:     '통과',
  confirmed_unpaid: '무임승차 확정',
  confirmed_misuse: '우대카드 부정사용',
}

function formatTime(ts: string) {
  return new Date(ts).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })
}

interface Filters {
  from:            string
  to:              string
  event_type:      string
  gate_section_id: string
  severity:        string
}

export default function EventListPage() {
  const navigate = useNavigate()

  const [filters, setFilters] = useState<Filters>({
    from: '', to: '', event_type: '', gate_section_id: '', severity: '',
  })
  const [events, setEvents]         = useState<GateGuardEvent[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [total, setTotal]           = useState<number>(0)
  const [loading, setLoading]         = useState(false)
  const [fetchError, setFetchError]   = useState('')
  const [cursorStack, setCursorStack] = useState<string[]>([])

  async function fetchEvents(cursor?: string) {
    setLoading(true)
    setFetchError('')
    try {
      const params: Record<string, string> = { limit: '50' }
      if (filters.from)            params.from             = filters.from
      if (filters.to)              params.to               = filters.to
      if (filters.event_type)      params.event_type       = filters.event_type
      if (filters.gate_section_id) params.gate_section_id  = filters.gate_section_id
      if (filters.severity)        params.severity         = filters.severity
      if (cursor)                  params.cursor           = cursor

      const { data } = await api.get('/events', { params })
      setEvents(data.data)
      setNextCursor(data.next_cursor)
      setTotal(data.total)
    } catch {
      setFetchError('이벤트를 불러올 수 없습니다.')
      setEvents([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setCursorStack([])
    fetchEvents()
  }, [filters])

  function handleNext() {
    if (!nextCursor) return
    setCursorStack((s) => [...s, nextCursor])
    fetchEvents(nextCursor)
  }

  function handlePrev() {
    const stack = [...cursorStack]
    stack.pop()
    const prev = stack[stack.length - 1]
    setCursorStack(stack)
    fetchEvents(prev)
  }

  function setFilter(key: keyof Filters, value: string) {
    setFilters((f) => ({ ...f, [key]: value }))
  }

  return (
    <div className={styles.page}>
      <h2 className={styles.title}>이벤트 목록</h2>

      {/* 필터 */}
      <div className={styles.filters}>
        <input
          type="datetime-local"
          value={filters.from}
          onChange={(e) => setFilter('from', e.target.value)}
          className={styles.input}
          placeholder="시작 시각"
        />
        <input
          type="datetime-local"
          value={filters.to}
          onChange={(e) => setFilter('to', e.target.value)}
          className={styles.input}
          placeholder="종료 시각"
        />
        <select
          value={filters.event_type}
          onChange={(e) => setFilter('event_type', e.target.value)}
          className={styles.input}
        >
          <option value="">이벤트 타입 전체</option>
          {EVENT_TYPES.map((t) => (
            <option key={t} value={t}>{EVENT_LABELS[t] ?? t}</option>
          ))}
        </select>
        <input
          type="text"
          value={filters.gate_section_id}
          onChange={(e) => setFilter('gate_section_id', e.target.value)}
          className={styles.input}
          placeholder="게이트 ID"
        />
        <select
          value={filters.severity}
          onChange={(e) => setFilter('severity', e.target.value)}
          className={styles.input}
        >
          <option value="">심각도 전체</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>{s.toUpperCase()}</option>
          ))}
        </select>
      </div>

      {/* 테이블 */}
      <div className={styles.tableWrap}>
        {loading ? (
          <p className={styles.empty}>불러오는 중...</p>
        ) : fetchError ? (
          <p className={styles.empty}>{fetchError}</p>
        ) : events.length === 0 ? (
          <p className={styles.empty}>이벤트가 없습니다.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>시각 (KST)</th>
                <th>이벤트 타입</th>
                <th>게이트</th>
                <th>카메라</th>
                <th>신뢰도</th>
                <th>심각도</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr
                  key={event.event_id}
                  onClick={() => navigate(`/events/${event.event_id}`)}
                  className={`${styles.row} ${styles[event.severity ?? 'info']}`}
                >
                  <td>{formatTime(event.timestamp)}</td>
                  <td>{EVENT_LABELS[event.event_type] ?? event.event_type}</td>
                  <td>{event.gate_section_id}</td>
                  <td>{event.camera_id}</td>
                  <td>{event.confidence != null ? `${Math.round(event.confidence * 100)}%` : '-'}</td>
                  <td>
                    <span className={`${styles.badge} ${styles[`badge_${event.severity ?? 'info'}`]}`}>
                      {(event.severity ?? 'info').toUpperCase()}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* 페이지네이션 */}
      <div className={styles.pagination}>
        <span className={styles.total}>총 {total}건</span>
        <button
          onClick={handlePrev}
          disabled={cursorStack.length === 0 || loading}
          className={styles.pageBtn}
        >
          이전
        </button>
        <button
          onClick={handleNext}
          disabled={!nextCursor || loading}
          className={styles.pageBtn}
        >
          다음
        </button>
      </div>
    </div>
  )
}
