// 新三国 星空 · 游戏状态类型（与 backend/engine/state.py 对齐）

export interface PlayerState {
  identity: string
  alive: boolean
  location: string
  reputation: number
  notes: string[]
}

export interface EraState {
  chapter: string
  year: number
  season: string
  location: string
  world_facts: string[]
}

export interface KnowledgeState {
  public: string[]
  hidden: string[]
  player: string[]
}

export interface MemoryItem {
  id: string
  text: string
  ts: number
}

export interface MemoryState {
  stm: MemoryItem[]
  ltm: MemoryItem[]
  pins: string[]
}

export interface OptionSpec {
  text: string
  type: 'major' | 'minor'
  tension: number
  effect: string
}

export interface NarrativeOutput {
  narrative: string
  options: OptionSpec[]
  state_updates: Record<string, unknown>
  validated: boolean
  phase_report: Record<string, unknown>
  retry_reasons: string[]
}

export interface GameState {
  player: PlayerState
  era: EraState
  relations: Record<string, number>
  trust: Record<string, number>
  flags: string[]
  knowledge: KnowledgeState
  memory: MemoryState
  skeleton_pos: string
  tension: number
  corrected: string[]
  turn: number
  retry_count: number
  history: { user?: string; assistant?: string }[]
  last_output: NarrativeOutput | null
  last_trace: string
  meta: Record<string, unknown>
}

// SSE 事件类型（Phase 4 协议）
export type StreamEvent =
  | { type: 'scene'; scene: { scene_id: string; chapter_label: string; title: string; location: string } }
  | { type: 'chunk'; content: string }
  | { type: 'player'; content: string }
  | { type: 'state'; state: GameState }
  | { type: 'options'; options: OptionSpec[] }
  | { type: 'phase'; report: Record<string, unknown> }
  | { type: 'done' }
  | { type: 'err'; content: string }
