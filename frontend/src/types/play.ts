// 新三国 星空 · 游戏状态类型（与 backend/engine/state.py 对齐）

export interface PlayerState {
  identity: string
  alive: boolean
  location: string
  reputation: number
  personality: string
  goal: string
  inner_voice: string
  notes: string[]
}

export interface EraState {
  chapter: string
  year: number
  season: string
  location: string
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
  scene?: string   // 场景标记（如 "颍川·雨夜荒野"）
  time?: string    // 可读时间（如 "184年·春"）
}

/** 8 PHASE 校验报告（对齐后端 phase_report） */
export interface PhaseReport {
  deterministic?: { phase: string; pass: boolean; reason: string }[]
  llm?: Record<string, { pass: boolean; reason: string }>
  summary?: string
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
  // 准备期行动盘（P6 名场面目标机制）：由后端硬注入，玩家可选，grants 精确匹配累积就位条件
  is_prep?: boolean
  grants?: string[]
  cost_turns?: number
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
  foreshadowing: string[]
  world_rumors: string[]
  turn: number
  retry_count: number
  history: { user?: string; assistant?: string }[]
  scene_state: { scene_id?: string; qualifications?: string[] } | null
  world_clock: { chapter: string; season: string; turns_left: number } | null
  last_output: NarrativeOutput | null
  last_trace: string
  meta: Record<string, unknown>
}

// 名场面目标（名场面前置场景时由 scene 事件附带，前端目标面板展示）
export interface FameGoal {
  scene_id: string
  title: string
  season: string
  entry_conditions: string[]
  current_qualifications: string[]
}

// SSE 事件类型（Phase 4 协议）
export type StreamEvent =
  | { type: 'scene'; scene: { scene_id: string; chapter_label: string; title: string; location: string; music?: string; atmo?: string; fame_goal?: FameGoal | null } }
  | { type: 'chunk'; content: string }
  | { type: 'player'; content: string }
  | { type: 'state'; state: GameState }
  | { type: 'options'; options: OptionSpec[] }
  | { type: 'phase'; report: PhaseReport }
  | { type: 'done' }
  | { type: 'err'; content: string }
  | { type: 'fail'; content: string }
