import { useEffect, useRef } from 'react'
import type { Point, Zone } from '../types'

interface Props {
  zone: Zone
  bgImage: HTMLImageElement | null
  vertexRadius: number
  closeRadius: number
  mousePos: Point | null
  onMouseDown: (p: Point, button: number) => void
  onMouseMove: (p: Point) => void
  onMouseUp: () => void
  onClick: (p: Point) => void
  onContextMenu: (p: Point) => void
}

const COLORS = {
  fill: 'rgba(99,179,237,0.25)',
  stroke: '#3b82f6',
  vertex: '#ffffff',
  vertexStroke: '#3b82f6',
  firstVertex: '#f59e0b',
  guide: 'rgba(59,130,246,0.5)',
  closeHint: 'rgba(245,158,11,0.4)',
}

function getCanvasPoint(canvas: HTMLCanvasElement, e: MouseEvent | React.MouseEvent): Point {
  const rect = canvas.getBoundingClientRect()
  return { x: e.clientX - rect.left, y: e.clientY - rect.top }
}

export function ZoneCanvas({
  zone, bgImage, vertexRadius, closeRadius,
  mousePos, onMouseDown, onMouseMove, onMouseUp, onClick, onContextMenu,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  // track whether a drag happened to suppress click
  const didDrag = useRef(false)
  const mouseDownPos = useRef<Point | null>(null)

  // draw
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // background
    if (bgImage) {
      ctx.drawImage(bgImage, 0, 0, canvas.width, canvas.height)
    } else {
      ctx.fillStyle = '#374151'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
    }

    const { vertices, closed } = zone
    if (vertices.length === 0) return

    // polygon fill + stroke
    ctx.beginPath()
    ctx.moveTo(vertices[0].x, vertices[0].y)
    for (let i = 1; i < vertices.length; i++) ctx.lineTo(vertices[i].x, vertices[i].y)
    if (closed) {
      ctx.closePath()
      ctx.fillStyle = COLORS.fill
      ctx.fill()
    } else if (mousePos) {
      // guide line to cursor
      ctx.save()
      ctx.setLineDash([5, 5])
      ctx.strokeStyle = COLORS.guide
      ctx.lineWidth = 1.5
      ctx.lineTo(mousePos.x, mousePos.y)
      ctx.stroke()
      ctx.restore()
      ctx.beginPath()
      ctx.moveTo(vertices[0].x, vertices[0].y)
      for (let i = 1; i < vertices.length; i++) ctx.lineTo(vertices[i].x, vertices[i].y)
    }
    ctx.strokeStyle = COLORS.stroke
    ctx.lineWidth = 2
    ctx.stroke()

    // close-snap hint ring around first vertex
    if (!closed && vertices.length >= 3 && mousePos) {
      const d = Math.hypot(mousePos.x - vertices[0].x, mousePos.y - vertices[0].y)
      if (d <= closeRadius) {
        ctx.beginPath()
        ctx.arc(vertices[0].x, vertices[0].y, closeRadius, 0, Math.PI * 2)
        ctx.fillStyle = COLORS.closeHint
        ctx.fill()
      }
    }

    // vertices
    vertices.forEach((v, i) => {
      ctx.beginPath()
      ctx.arc(v.x, v.y, vertexRadius, 0, Math.PI * 2)
      ctx.fillStyle = i === 0 && !closed ? COLORS.firstVertex : COLORS.vertex
      ctx.fill()
      ctx.strokeStyle = COLORS.vertexStroke
      ctx.lineWidth = 2
      ctx.stroke()
    })
  }, [zone, bgImage, mousePos, vertexRadius, closeRadius])

  function toPoint(e: React.MouseEvent): Point {
    return getCanvasPoint(canvasRef.current!, e)
  }

  return (
    <canvas
      ref={canvasRef}
      width={900}
      height={600}
      style={{ cursor: zone.closed ? 'default' : 'crosshair', display: 'block' }}
      onMouseDown={e => {
        const p = toPoint(e)
        mouseDownPos.current = p
        didDrag.current = false
        onMouseDown(p, e.button)
      }}
      onMouseMove={e => {
        const p = toPoint(e)
        if (mouseDownPos.current) {
          const dx = Math.abs(p.x - mouseDownPos.current.x)
          const dy = Math.abs(p.y - mouseDownPos.current.y)
          if (dx > 3 || dy > 3) didDrag.current = true
        }
        onMouseMove(p)
      }}
      onMouseUp={() => onMouseUp()}
      onClick={e => {
        if (didDrag.current) return
        onClick(toPoint(e))
      }}
      onContextMenu={e => {
        e.preventDefault()
        onContextMenu(toPoint(e))
      }}
      onMouseLeave={() => onMouseUp()}
    />
  )
}
