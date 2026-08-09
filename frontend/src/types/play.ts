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
  // 自由沙盒（见 docs/自由沙盒重构设计.md §三）
  assets: string[]
  coins: number
  stats: { stamina: number; hunger: number; wound: number }
  titles: string[]
  achievements: string[]
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
  category?: '打探' | '赶路' | '停留' | '互动'   // 地点行动分类（自由沙盒 §5.4，writer 归一化）
}

export interface NarrativeOutput {
  narrative: string
  options: OptionSpec[]
  state_updates: Record<string, unknown>
  validated: boolean
  phase_report: Record<string, unknown>
  retry_reasons: string[]
}

// 地点导航状态（director 每拍写入，见 docs/自由沙盒重构设计.md §5.2）
export interface LocationState {
  current: string | null        // 当前所在地点
  unlocked: string[]            // 已解锁地点（去过 ∪ 传闻解锁，可往返/可赶路）
  next_station: string | null   // 下站（推进目标地点，未解锁）
  rumored: { name: string; hint: string }[]   // 传闻地点（未解锁但听过传闻，可「打听X」解锁）
}

// 世界事件（事实层，见 docs/自由沙盒重构设计.md §二）
export interface WorldEvent {
  event_id: string
  date: string
  event: string
  related_to_player: 'strong' | 'weak'
  seen?: boolean
  source?: 'timeline' | 'daily'
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
  world_events: WorldEvent[]       // 事实层：世界事件队列（自由沙盒）
  world_date: { year: number; month: number; day: number }   // 世界具体日期
  new_achievements?: string[]      // 本轮新解锁成就 id（后端 check_achievements 产出，SSE state 快照携带）
  dead?: boolean                   // 死亡（三属性同时极端，alive=False）——前端读档最近快照
  vitals_alarm?: string            // 濒死标记（stamina/hunger/wound，下拍 writer 演后果；已脱离则为 ''）
  location_state?: LocationState   // 地点面板状态（director 每拍写入）
  turn: number
  retry_count: number
  history: { user?: string; assistant?: string }[]
  scene_state: { scene_id?: string; qualifications?: string[] } | null
  last_output: NarrativeOutput | null
  last_trace: string
  meta: Record<string, unknown>
}

// SSE 事件类型（Phase 4 协议）
export type StreamEvent =
  | { type: 'scene'; scene: { scene_id: string; chapter_label: string; title: string; location: string; music?: string; atmo?: string } }
  | { type: 'chunk'; content: string }
  | { type: 'player'; content: string }
  | { type: 'state'; state: GameState }
  | { type: 'options'; options: OptionSpec[] }
  | { type: 'phase'; report: PhaseReport }
  | { type: 'done' }
  | { type: 'err'; content: string }
