import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import axios from 'axios'
import api from '../lib/api'
import { getAccessToken } from '../lib/auth'
import type { GateGuardEvent } from '../types/event'
import styles from './ReviewQueuePage.module.css'

interface ReviewQueueItem {
  queue_id:    string
  event_id:    string
  event:       GateGuardEvent
  status:      'pending' | 'confirmed' | 'false_positive'
  added_at:    string
  reviewer_id: string | null
  reviewed_at: string | null
  feedback:    string | null
}

type StatusFilter = 'pending' | 'confirmed' | 'false_positive' | 'all'

const STATUS_LABELS: Record<string, string> = {
  pending:        '미처리',
  confirmed:      '정탐 확인',
  false_positive: '오탐',
  all:            '전체',
}

const CARD_LABELS: Record<string, string> = {
  regular:       '일반',
  senior:        '노인',
  child:         '어린이',
  disabled:      '장애인',
  national_merit:'국가유공자',
}

const GENDER_LABELS: Record<string, string> = {
  male:    '남성',
  female:  '여성',
  unknown: '미확인',
}

const AGE_GROUP_LABELS: Record<string, string> = {
  child:   '어린이',
  youth:   '청소년',
  adult:   '성인',
  senior:  '노인',
  unknown: '미확인',
}

function confidenceText(value: number | null | undefined): string {
  if (value == null) return ''
  const pct = Math.round(value * 100)
  return value >= 0.8 ? `${pct}%` : `${pct}% (검토 필요)`
}

const EVENT_LABELS: Record<string, string> = {
  confirmed_misuse:  '우대카드 부정사용',
  confirmed_unpaid:  '무임승차 확정',
  gate_passage:      '통과',
  jump:              '점프',
  crawling:          '기어가기',
  tailgating:        '꼬리물기',
  unpaid:            '우회/역방향',
}

const MATCH_STATUS_LABELS: Record<string, string> = {
  confirmed_misuse:  '우대카드 부정 사용 의심',
  confirmed_unpaid:  '결제 없음 의심',
  gate_passage:      '정상 매칭',
}

function matchStatus(event: GateGuardEvent): string {
  return MATCH_STATUS_LABELS[event.event_type] ?? '확인 필요'
}

function formatTime(ts: string) {
  return new Date(ts).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })
}

function ProbBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const cls = value < 0.2 ? styles.low : value < 0.5 ? styles.mid : styles.high
  return (
    <div className={styles.probWrap}>
      <div className={styles.probBar}>
        <div className={`${styles.probFill} ${cls}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={styles.probLabel}>{pct}%</span>
    </div>
  )
}

/* ─────────────────────────── 상세 뷰 ─────────────────────────── */
function DetailView({ queueId }: { queueId: string }) {
  const navigate  = useNavigate()
  const location  = useLocation()

  const [item, setItem]       = useState<ReviewQueueItem | null>(location.state?.item ?? null)
  const [clipUrl, setClipUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(!item)
  const [submitting, setSubmitting] = useState(false)
  const [notes, setNotes]     = useState('')
  const [toast, setToast]     = useState<{ msg: string; type: 'success' | 'error' } | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  function showToast(msg: string, type: 'success' | 'error') {
    setToast({ msg, type })
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setToast(null), 3000)
  }

  // 직접 URL 진입 시 목록에서 항목 찾기 (api-contract.md §2-3)
  useEffect(() => {
    if (item) return
    api.get('/review-queue', { params: { status: 'all', limit: 200 } })
      .then(({ data }) => {
        const found = (data.data as ReviewQueueItem[]).find((i) => i.queue_id === queueId)
        if (found) setItem(found)
      })
      .finally(() => setLoading(false))
  }, [queueId, item])

  // 영상 클립 (api-contract.md §2-2)
  useEffect(() => {
    if (!item) return
    const base  = import.meta.env.VITE_API_BASE_URL
    const token = getAccessToken()
    fetch(`${base}/events/${item.event_id}/video-clip`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((res) => {
      if (res.ok || res.redirected) setClipUrl(res.url)
    }).catch(() => {})
  }, [item])

  // 정탐/오탐 피드백 제출 (api-contract.md §2-3)
  async function submitFeedback(decision: 'confirmed' | 'false_positive') {
    if (!item) return
    setSubmitting(true)
    try {
      await api.post(`/review-queue/${item.queue_id}/feedback`, {
        decision,
        notes: notes.trim() || undefined,
      })
      setItem((prev) => prev ? { ...prev, status: decision } : prev)
      showToast(decision === 'confirmed' ? '✅ 정탐으로 확인했습니다.' : '✅ 오탐으로 처리했습니다.', 'success')
    } catch (e: unknown) {
      if (axios.isAxiosError(e) && e.response?.status === 409) {
        showToast('이미 다른 역무원이 처리했습니다.', 'error')
      } else {
        showToast('처리 중 오류가 발생했습니다.', 'error')
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <p className={styles.state}>불러오는 중...</p>
  if (!item)   return <p className={styles.state}>항목을 찾을 수 없습니다.</p>

  const { event } = item
  const prob = event.signals?.senior_probability

  return (
    <div className={styles.page}>
      <button className={styles.back} onClick={() => navigate('/review-queue')}>
        ← 목록으로
      </button>

      <div className={styles.layout}>
        {/* 영상 클립 */}
        <div className={styles.videoWrap}>
          {clipUrl
            ? <video src={clipUrl} controls className={styles.video} />
            : <span className={styles.noVideo}>영상 클립 없음</span>
          }
        </div>

        <div className={styles.meta}>
          {/* 이벤트 정보 */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>이벤트 정보</h3>
            <dl className={styles.dl}>
              <dt>타입</dt>      <dd>{EVENT_LABELS[event.event_type] ?? event.event_type}</dd>
              <dt>게이트</dt>    <dd>{event.gate_section_id}</dd>
              <dt>카메라</dt>    <dd>{event.camera_id}</dd>
              <dt>시각 (KST)</dt><dd>{formatTime(event.timestamp)}</dd>
              {event.severity && <><dt>심각도</dt><dd>{event.severity.toUpperCase()}</dd></>}
            </dl>
          </section>

          {/* AFC 매칭 (api-contract.md §2-2, schema afc_match) */}
          {event.afc_match && (
            <section className={styles.section}>
              <h3 className={styles.sectionTitle}>카드 태그 기록</h3>
              <dl className={styles.dl}>
                <dt>판단 상태</dt>
                <dd>{matchStatus(event)}</dd>
                <dt>fare tap ID</dt>
                <dd>{event.afc_match.fare_tap_id}</dd>
                <dt>카드 종류</dt>
                <dd>{CARD_LABELS[event.afc_match.card_category] ?? event.afc_match.card_category}</dd>
                <dt>카드 등록 성별</dt>
                <dd>{GENDER_LABELS[event.afc_match.holder_gender] ?? event.afc_match.holder_gender}</dd>
                <dt>태그 시각</dt>
                <dd>{formatTime(event.afc_match.tap_timestamp)}</dd>
                {event.afc_match.time_delta_ms != null && (
                  <><dt>시간 차이</dt><dd>{event.afc_match.time_delta_ms}ms</dd></>
                )}
              </dl>
            </section>
          )}

          {/* AI 신호 — senior_probability 시각화 (mvp-features.md §4-C-2) */}
          {event.signals && (
            <section className={styles.section}>
              <h3 className={styles.sectionTitle}>AI 신호</h3>
              <dl className={styles.dl}>
                {prob != null && (
                  <>
                    <dt>노인 확률</dt>
                    <dd><ProbBar value={prob} /></dd>
                  </>
                )}
                {event.signals.child_probability != null && (
                  <>
                    <dt>어린이 확률</dt>
                    <dd><ProbBar value={event.signals.child_probability} /></dd>
                  </>
                )}
                {event.signals.perceived_gender != null && (
                  <>
                    <dt>AI 추정 성별</dt>
                    <dd>
                      {GENDER_LABELS[event.signals.perceived_gender] ?? event.signals.perceived_gender}
                      {event.signals.gender_confidence != null && ` · ${confidenceText(event.signals.gender_confidence)}`}
                    </dd>
                  </>
                )}
                {event.signals.estimated_age_group != null && (
                  <>
                    <dt>AI 추정 연령대</dt>
                    <dd>
                      {AGE_GROUP_LABELS[event.signals.estimated_age_group] ?? event.signals.estimated_age_group}
                      {event.signals.age_group_confidence != null && ` · ${confidenceText(event.signals.age_group_confidence)}`}
                    </dd>
                  </>
                )}
                {event.signals.face_age_estimate != null && (
                  <><dt>추정 나이</dt><dd>{event.signals.face_age_estimate}세</dd></>
                )}
                {event.signals.assistive_device_detected != null && (
                  <><dt>보조기구</dt><dd>{event.signals.assistive_device_detected ? `감지됨${event.signals.assistive_device_type ? ` (${event.signals.assistive_device_type})` : ''}` : '없음'}</dd></>
                )}
                {event.reliability && (
                  <><dt>신뢰 등급</dt><dd>{event.reliability.toUpperCase()}</dd></>
                )}
              </dl>
            </section>
          )}

          {/* 정탐/오탐 버튼 (api-contract.md §2-3, §6-5) */}
          <div className={styles.feedbackSection}>
            <h3 className={styles.sectionTitle}>검토 결정</h3>
            {item.status !== 'pending' ? (
              <p className={styles.reviewed}>
                {item.status === 'confirmed' ? '✅ 정탐으로 확인됨' : '✅ 오탐으로 처리됨'}
                {item.reviewed_at && ` · ${formatTime(item.reviewed_at)}`}
              </p>
            ) : (
              <>
                <textarea
                  className={styles.notes}
                  placeholder="메모 (선택, 최대 500자)"
                  maxLength={500}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
                <div className={styles.btnRow}>
                  <button
                    className={styles.btnConfirm}
                    onClick={() => submitFeedback('confirmed')}
                    disabled={submitting}
                  >
                    정탐 확인
                  </button>
                  <button
                    className={styles.btnFp}
                    onClick={() => submitFeedback('false_positive')}
                    disabled={submitting}
                  >
                    오탐 신고
                  </button>
                  <button
                    className={styles.btnHold}
                    onClick={() => { showToast('확인 보류로 처리했습니다.', 'success'); navigate('/review-queue') }}
                    disabled={submitting}
                  >
                    확인 보류
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* 토스트 */}
      {toast && (
        <div className={`${styles.toast} ${styles[toast.type]}`}>
          {toast.msg}
        </div>
      )}
    </div>
  )
}

/* ─────────────────────────── 목록 뷰 ─────────────────────────── */
function ListView() {
  const navigate = useNavigate()

  const [status, setStatus]           = useState<StatusFilter>('pending')
  const [items, setItems]             = useState<ReviewQueueItem[]>([])
  const [nextCursor, setNextCursor]   = useState<string | null>(null)
  const [cursorStack, setCursorStack] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')

  // promise 체인 방식 — setState는 항상 비동기 콜백에서만 호출 (effect 내 cascading render 방지)
  const fetchQueue = useCallback((cursor?: string) => {
    const params: Record<string, string> = { status, limit: '50' }
    if (cursor) params.cursor = cursor

    api.get('/review-queue', { params })
      .then(({ data }) => {
        setItems(data.data)
        setNextCursor(data.next_cursor ?? null)
        setError('')
        setLoading(false)
      })
      .catch(() => {
        setError('의심 큐를 불러올 수 없습니다.')
        setLoading(false)
      })
  }, [status])

  useEffect(() => {
    fetchQueue()
  }, [fetchQueue])

  // setLoading/setError 초기화는 이벤트 핸들러에서 처리 (effect 내 직접 setState 방지)
  function handleStatusChange(s: StatusFilter) {
    setCursorStack([])
    setLoading(true)
    setError('')
    setStatus(s)
  }

  function handleNext() {
    if (!nextCursor) return
    setLoading(true)
    setCursorStack((s) => [...s, nextCursor])
    fetchQueue(nextCursor)
  }

  function handlePrev() {
    const stack = [...cursorStack]
    stack.pop()
    const prev = stack[stack.length - 1]
    setLoading(true)
    setCursorStack(stack)
    fetchQueue(prev)
  }

  return (
    <div className={styles.page}>
      <h2 className={styles.title}>의심 큐</h2>

      {/* 상태 필터 탭 */}
      <div className={styles.tabs}>
        {(['pending', 'confirmed', 'false_positive', 'all'] as StatusFilter[]).map((s) => (
          <button
            key={s}
            className={`${styles.tab} ${status === s ? styles.active : ''}`}
            onClick={() => handleStatusChange(s)}
          >
            {STATUS_LABELS[s]}
          </button>
        ))}
      </div>

      {/* 테이블 */}
      <div className={styles.tableWrap}>
        {loading ? (
          <p className={styles.empty}>불러오는 중...</p>
        ) : error ? (
          <p className={styles.empty}>{error}</p>
        ) : items.length === 0 ? (
          <p className={styles.empty}>항목이 없습니다.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>시각 (KST)</th>
                <th>이벤트 타입</th>
                <th>게이트</th>
                <th>카드 종류</th>
                <th>노인 확률</th>
                <th>상태</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.queue_id}
                  className={styles.row}
                  onClick={() => navigate(`/review-queue/${item.queue_id}`, { state: { item } })}
                >
                  <td>{formatTime(item.added_at)}</td>
                  <td>{EVENT_LABELS[item.event.event_type] ?? item.event.event_type}</td>
                  <td>{item.event.gate_section_id}</td>
                  <td>
                    {item.event.afc_match
                      ? CARD_LABELS[item.event.afc_match.card_category] ?? item.event.afc_match.card_category
                      : '-'}
                  </td>
                  <td>
                    {item.event.signals?.senior_probability != null
                      ? `${Math.round(item.event.signals.senior_probability * 100)}%`
                      : '-'}
                  </td>
                  <td>
                    <span className={`${styles.badge} ${styles[`badge_${item.status}`]}`}>
                      {STATUS_LABELS[item.status]}
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
        <button onClick={handlePrev} disabled={cursorStack.length === 0 || loading} className={styles.pageBtn}>이전</button>
        <button onClick={handleNext} disabled={!nextCursor || loading} className={styles.pageBtn}>다음</button>
      </div>
    </div>
  )
}

/* ─────────────────────────── 진입점 ─────────────────────────── */
export default function ReviewQueuePage() {
  const { queue_id } = useParams<{ queue_id: string }>()
  return queue_id ? <DetailView queueId={queue_id} /> : <ListView />
}
