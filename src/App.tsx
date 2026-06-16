import { useCallback, useRef, useState } from 'react'
import { ZoneCanvas } from './components/ZoneCanvas'
import { useZoneEditor } from './hooks/useZoneEditor'
import type { Point } from './types'

export default function App() {
  const {
    zone, closeRadius, vertexRadius,
    handleMouseDown, handleMouseMove, handleMouseUp, handleClick, handleContextMenu,
    reset,
  } = useZoneEditor()

  const [bgImage, setBgImage] = useState<HTMLImageElement | null>(null)
  const [mousePos, setMousePos] = useState<Point | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadImage = useCallback((file: File) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => setBgImage(img)
    img.src = url
  }, [])

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) loadImage(file)
  }

  const onMouseMoveWrapper = (p: Point) => {
    setMousePos(p)
    handleMouseMove(p)
  }

  const statusText = zone.closed
    ? `완성 (${zone.vertices.length}개 꼭짓점) — 콘솔에서 좌표 확인`
    : zone.vertices.length === 0
    ? '캔버스를 클릭해 꼭짓점을 추가하세요'
    : zone.vertices.length < 3
    ? `꼭짓점 ${zone.vertices.length}개 — 최소 3개 필요`
    : '첫 번째 점 근처를 클릭해 닫기 (또는 계속 추가)'

  return (
    <div style={styles.root}>
      <header style={styles.header}>
        <h1 style={styles.title}>Zone Editor</h1>
        <div style={styles.toolbar}>
          <button style={styles.btn} onClick={() => fileInputRef.current?.click()}>
            이미지 불러오기
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={onFileChange}
          />
          <button style={{ ...styles.btn, ...styles.btnDanger }} onClick={reset}>
            초기화
          </button>
        </div>
      </header>

      <main style={styles.main}>
        <div style={styles.canvasWrapper}>
          <ZoneCanvas
            zone={zone}
            bgImage={bgImage}
            vertexRadius={vertexRadius}
            closeRadius={closeRadius}
            mousePos={zone.closed ? null : mousePos}
            onMouseDown={handleMouseDown}
            onMouseMove={onMouseMoveWrapper}
            onMouseUp={handleMouseUp}
            onClick={handleClick}
            onContextMenu={handleContextMenu}
          />
        </div>

        <aside style={styles.sidebar}>
          <section style={styles.section}>
            <h2 style={styles.sectionTitle}>상태</h2>
            <p style={styles.status}>{statusText}</p>
            <div style={styles.badge(zone.closed)}>
              {zone.closed ? '완성됨' : '그리는 중'}
            </div>
          </section>

          <section style={styles.section}>
            <h2 style={styles.sectionTitle}>꼭짓점 목록</h2>
            {zone.vertices.length === 0 ? (
              <p style={styles.empty}>없음</p>
            ) : (
              <ul style={styles.list}>
                {zone.vertices.map((v, i) => (
                  <li key={i} style={styles.listItem}>
                    <span style={styles.idx}>{i}</span>
                    ({Math.round(v.x)}, {Math.round(v.y)})
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section style={styles.section}>
            <h2 style={styles.sectionTitle}>사용법</h2>
            <ul style={styles.helpList}>
              <li><b>클릭</b> — 꼭짓점 추가</li>
              <li><b>드래그</b> — 꼭짓점 이동</li>
              <li><b>우클릭</b> — 꼭짓점 삭제</li>
              <li><b>첫 점 클릭</b> — 도형 닫기</li>
            </ul>
          </section>
        </aside>
      </main>
    </div>
  )
}

const styles = {
  root: {
    fontFamily: 'system-ui, sans-serif',
    background: '#111827',
    minHeight: '100vh',
    color: '#f9fafb',
    display: 'flex',
    flexDirection: 'column' as const,
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 24px',
    background: '#1f2937',
    borderBottom: '1px solid #374151',
  },
  title: { margin: 0, fontSize: 20, fontWeight: 700, color: '#60a5fa' },
  toolbar: { display: 'flex', gap: 8 },
  btn: {
    padding: '6px 14px',
    borderRadius: 6,
    border: '1px solid #4b5563',
    background: '#374151',
    color: '#f9fafb',
    cursor: 'pointer',
    fontSize: 13,
  },
  btnDanger: { borderColor: '#ef4444', color: '#fca5a5' },
  main: {
    display: 'flex',
    flex: 1,
    padding: 20,
    gap: 20,
    alignItems: 'flex-start',
  },
  canvasWrapper: {
    border: '2px solid #374151',
    borderRadius: 8,
    overflow: 'hidden',
    flexShrink: 0,
  },
  sidebar: {
    width: 220,
    flexShrink: 0,
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 16,
  },
  section: {
    background: '#1f2937',
    borderRadius: 8,
    padding: '12px 14px',
    border: '1px solid #374151',
  },
  sectionTitle: { margin: '0 0 8px', fontSize: 13, color: '#9ca3af', fontWeight: 600 },
  status: { margin: '0 0 8px', fontSize: 13, lineHeight: 1.5 },
  badge: (closed: boolean) => ({
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: 12,
    fontSize: 12,
    background: closed ? '#065f46' : '#1e3a5f',
    color: closed ? '#6ee7b7' : '#93c5fd',
  }),
  empty: { margin: 0, fontSize: 13, color: '#6b7280' },
  list: { margin: 0, padding: 0, listStyle: 'none', maxHeight: 300, overflowY: 'auto' as const },
  listItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '3px 0',
    fontSize: 12,
    fontFamily: 'monospace',
    color: '#d1d5db',
    borderBottom: '1px solid #374151',
  },
  idx: {
    minWidth: 20,
    textAlign: 'right' as const,
    color: '#6b7280',
    fontSize: 11,
  },
  helpList: {
    margin: 0,
    padding: '0 0 0 16px',
    fontSize: 12,
    color: '#9ca3af',
    lineHeight: 1.9,
  },
}
