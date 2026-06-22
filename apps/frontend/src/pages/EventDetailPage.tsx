import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../lib/api'
import { getAccessToken } from '../lib/auth'
import type { GateGuardEvent } from '../types/event'
import styles from './EventDetailPage.module.css'

const EVENT_LABELS: Record<string, string> = {
  jump:             '점프',
  crawling:         '기어가기',
  tailgating:       '꼬리물기',
  unpaid:           '우회/역방향',
  gate_passage:     '통과',
  confirmed_unpaid: '무임승차 확정',
  confirmed_misuse: '우대카드 부정사용',
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

const MATCH_STATUS_LABELS: Record<string, string> = {
  confirmed_misuse: '우대카드 부정 사용 의심',
  confirmed_unpaid: '결제 없음 의심',
  gate_passage:     '정상 매칭',
}

function confidenceText(value: number | null | undefined): string {
  if (value == null) return ''
  const pct = Math.round(value * 100)
  return value >= 0.8 ? `${pct}%` : `${pct}% (검토 필요)`
}

function formatTime(ts: string) {
  return new Date(ts).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })
}

export default function EventDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [lastId, setLastId]   = useState(id)
  const [event, setEvent]     = useState<GateGuardEvent | null>(null)
  const [clipUrl, setClipUrl] = useState<string | null>(null)
  const [error, setError]     = useState('')

  // id가 바뀌면 렌더 단계에서 상태 초기화 (effect 내 직접 setState 방지)
  if (lastId !== id) {
    setLastId(id)
    setEvent(null)
    setClipUrl(null)
    setError('')
  }

  // event=null이고 error=''이면 로딩 중
  const loading = !event && !error

  useEffect(() => {
    if (!id) return

    api.get(`/events/${id}`)
      .then(({ data }) => setEvent(data))
      .catch(() => setError('이벤트를 불러올 수 없습니다.'))
  }, [id])

  useEffect(() => {
    if (!id) return

    const base  = import.meta.env.VITE_API_BASE_URL
    const token = getAccessToken()
    fetch(`${base}/events/${id}/video-clip`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((res) => {
      if (res.ok || res.redirected) setClipUrl(res.url)
    }).catch(() => {})
  }, [id])

  if (loading) return <p className={styles.state}>불러오는 중...</p>
  if (error)   return <p className={styles.state}>{error}</p>
  if (!event)  return null

  return (
    <div className={styles.page}>
      <button className={styles.back} onClick={() => navigate(-1)}>
        ← 목록으로
      </button>

      <div className={styles.layout}>
        {/* 영상 클립 */}
        <div className={styles.videoWrap}>
          {clipUrl ? (
            <video
              src={clipUrl}
              controls
              className={styles.video}
            />
          ) : (
            <div className={styles.noVideo}>영상 클립 없음</div>
          )}
        </div>

        {/* 메타 정보 */}
        <div className={styles.meta}>

          {/* 기본 정보 */}
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>이벤트 정보</h3>
            <dl className={styles.dl}>
              <dt>타입</dt>
              <dd>{EVENT_LABELS[event.event_type] ?? event.event_type}</dd>
              <dt>게이트</dt>
              <dd>{event.gate_section_id}</dd>
              <dt>카메라</dt>
              <dd>{event.camera_id}</dd>
              <dt>신뢰도</dt>
              <dd>{event.confidence != null ? `${Math.round(event.confidence * 100)}%` : '-'}</dd>
              <dt>시각 (KST)</dt>
              <dd>{formatTime(event.timestamp)}</dd>
              {event.severity && (
                <>
                  <dt>심각도</dt>
                  <dd>
                    <span className={`${styles.badge} ${styles[`badge_${event.severity}`]}`}>
                      {event.severity.toUpperCase()}
                    </span>
                  </dd>
                </>
              )}
              {event.reliability && (
                <>
                  <dt>신뢰 등급</dt>
                  <dd>{event.reliability.toUpperCase()}</dd>
                </>
              )}
            </dl>
          </section>

          {/* signals */}
          {event.signals && (
            <section className={styles.section}>
              <h3 className={styles.sectionTitle}>AI 신호 (signals)</h3>
              <dl className={styles.dl}>
                {event.signals.senior_probability != null && (
                  <>
                    <dt>노인 확률</dt>
                    <dd>{Math.round(event.signals.senior_probability * 100)}%</dd>
                  </>
                )}
                {event.signals.child_probability != null && (
                  <>
                    <dt>어린이 확률</dt>
                    <dd>{Math.round(event.signals.child_probability * 100)}%</dd>
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
                  <>
                    <dt>추정 나이</dt>
                    <dd>{event.signals.face_age_estimate}세</dd>
                  </>
                )}
                {event.signals.assistive_device_detected != null && (
                  <>
                    <dt>보조기구</dt>
                    <dd>{event.signals.assistive_device_detected ? '감지됨' : '없음'}</dd>
                  </>
                )}
              </dl>
            </section>
          )}

          {/* afc_match */}
          {event.afc_match && (
            <section className={styles.section}>
              <h3 className={styles.sectionTitle}>카드 태그 기록</h3>
              <dl className={styles.dl}>
                <dt>판단 상태</dt>
                <dd>{MATCH_STATUS_LABELS[event.event_type] ?? '확인 필요'}</dd>
                <dt>fare tap ID</dt>
                <dd>{event.afc_match.fare_tap_id}</dd>
                <dt>카드 종류</dt>
                <dd>{CARD_LABELS[event.afc_match.card_category] ?? event.afc_match.card_category}</dd>
                <dt>카드 등록 성별</dt>
                <dd>{GENDER_LABELS[event.afc_match.holder_gender] ?? event.afc_match.holder_gender}</dd>
                <dt>태그 시각</dt>
                <dd>{formatTime(event.afc_match.tap_timestamp)}</dd>
                {event.afc_match.time_delta_ms != null && (
                  <>
                    <dt>시간 차이</dt>
                    <dd>{event.afc_match.time_delta_ms}ms</dd>
                  </>
                )}
              </dl>
            </section>
          )}

        </div>
      </div>
    </div>
  )
}
