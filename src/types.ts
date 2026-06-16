export interface Point {
  x: number
  y: number
}

export interface Zone {
  id: string
  vertices: Point[]
  closed: boolean
}
