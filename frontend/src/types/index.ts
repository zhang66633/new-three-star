export interface GraphNode {
  id: string
  name: string
  type: 'character' | 'tianyi' | 'spacetime' | 'military' | 'social' | 'item' | 'creature'
  summary: string
  color: string
  size: number
  keywords?: string[]
}

export interface GraphLink {
  source: string
  target: string
  relation: string
}

export interface GraphData {
  nodes: GraphNode[]
  links: GraphLink[]
}

export interface WorldviewMeta {
  id: string
  name: string
  tagline: string
  color: string
  suitable_scenes?: string[]
}
