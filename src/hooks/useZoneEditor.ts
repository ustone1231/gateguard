import { useCallback, useRef, useState } from 'react'
import type { Point, Zone } from '../types'

const CLOSE_RADIUS = 12
const VERTEX_RADIUS = 7

function distance(a: Point, b: Point) {
  return Math.hypot(a.x - b.x, a.y - b.y)
}

function hitTestVertex(vertices: Point[], p: Point): number {
  for (let i = vertices.length - 1; i >= 0; i--) {
    if (distance(vertices[i], p) <= VERTEX_RADIUS + 2) return i
  }
  return -1
}

export function useZoneEditor() {
  const [zone, setZone] = useState<Zone>({ id: 'zone-1', vertices: [], closed: false })
  const draggingIndex = useRef<number | null>(null)
  const dragOffset = useRef<Point>({ x: 0, y: 0 })

  const handleMouseDown = useCallback((p: Point, button: number) => {
    if (button === 2) return // handled in contextmenu

    if (zone.closed) {
      // allow dragging vertices of a closed zone
      const idx = hitTestVertex(zone.vertices, p)
      if (idx !== -1) {
        draggingIndex.current = idx
        dragOffset.current = { x: p.x - zone.vertices[idx].x, y: p.y - zone.vertices[idx].y }
      }
      return
    }

    // check drag on existing vertices
    const idx = hitTestVertex(zone.vertices, p)
    if (idx !== -1) {
      draggingIndex.current = idx
      dragOffset.current = { x: p.x - zone.vertices[idx].x, y: p.y - zone.vertices[idx].y }
    }
  }, [zone])

  const handleMouseMove = useCallback((p: Point) => {
    if (draggingIndex.current === null) return
    const idx = draggingIndex.current
    setZone(prev => {
      const next = [...prev.vertices]
      next[idx] = { x: p.x - dragOffset.current.x, y: p.y - dragOffset.current.y }
      return { ...prev, vertices: next }
    })
  }, [])

  const handleMouseUp = useCallback(() => {
    draggingIndex.current = null
  }, [])

  const handleClick = useCallback((p: Point) => {
    if (draggingIndex.current !== null) return
    if (zone.closed) return

    const { vertices } = zone

    // close polygon when clicking near the first vertex
    if (vertices.length >= 3 && distance(p, vertices[0]) <= CLOSE_RADIUS) {
      const closed = { ...zone, closed: true }
      setZone(closed)
      console.log('[ZoneEditor] Polygon closed. Coordinates:', closed.vertices)
      return
    }

    setZone(prev => ({ ...prev, vertices: [...prev.vertices, p] }))
  }, [zone])

  const handleContextMenu = useCallback((p: Point) => {
    if (zone.closed) return
    const idx = hitTestVertex(zone.vertices, p)
    if (idx === -1) return
    setZone(prev => ({
      ...prev,
      vertices: prev.vertices.filter((_, i) => i !== idx),
    }))
  }, [zone])

  const reset = useCallback(() => {
    setZone({ id: 'zone-1', vertices: [], closed: false })
  }, [])

  return {
    zone,
    closeRadius: CLOSE_RADIUS,
    vertexRadius: VERTEX_RADIUS,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    handleClick,
    handleContextMenu,
    reset,
  }
}
