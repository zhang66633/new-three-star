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
  locations?: string[]          // 全量地点顺序（后端动态下发；旧存档缺失时前端回退本地兜底）
}

// 世界事件（事实层，见 docs/自由沙盒重构设计.md §二）
export interface WorldEvent {
  event_id: string
  date: string
  event: string
  related_to_player: 'strong' | 'weak'
  seen?: boolean
  source?: 'timeline' | 'daily' | 'period' | 'player' | 'timeskip'
}

// 角色世界状态档案（自由大世界·决策8）：引擎管事实，LLM 管软状态
export interface CharacterState {
  name: string
  location: string          // 事实：当前所在（引擎按 timeline 更新）
  activity: string          // 软状态：在做什么（LLM 更新为主）
  goal: string              // 软状态：当前目标
  attitude: number          // 对玩家态度 0-100
  alive: boolean            // 事实：是否在世
  dies_on?: string | null   // 事实：退场年月（引擎按点置 alive=false）
  known: boolean            // 事实：玩家是否认识
  last_seen: string         // 事实：上次接触日期
  seen_at: string           // 事实：上次见面地点
  tags: string[]            // 软状态标签（≤4）
  notes: string[]           // 软状态备注（≤3）
}

// 世界简报事件（B-⑧：先出简报，后进场景叙事；SSE 在 chunk 前发送）
export interface BriefingEvent {
  briefing: string          // LLM 合成简报（A3），可空
  events: WorldEvent[]      // 本拍新事件（含 weak，前端折叠展示 B-⑦）
}

export interface GameState {
  player: PlayerState
  era: EraState
  relations: Record<string, number>
  trust: Record<string, number>
  stances?: Record<string, string>
  encountered?: string[]
  flags: string[]
  knowledge: KnowledgeState
  memory: MemoryState
  skeleton_pos: string
  tension: number
  corrected: string[]
  foreshadowing: string[]
  briefing?: string               // 本拍 LLM 合成世界简报（A3 §3.3）
  world_rumors: string[]
  world_events: WorldEvent[]       // 事实层：世界事件队列（自由沙盒）
  world_date: { year: number; month: number; day: number }   // 世界具体日期
  new_achievements?: string[]      // 本轮新解锁成就 id（后端 check_achievements 产出，SSE state 快照携带）
  dead?: boolean                   // 死亡（三属性同时极端，alive=False）——前端读档最近快照
  vitals_alarm?: string            // 濒死标记（stamina/hunger/wound，下拍 writer 演后果；已脱离则为 ''）
  location_state?: LocationState   // 地点面板状态（director 每拍写入）
  character_states?: Record<string, CharacterState>   // 角色世界状态档案（自由大世界·决策8）
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
  | { type: 'scene'; scene: { scene_id: string; chapter_label: string; title: string; location: string; year: number; season?: string; world_date?: { year: number; month: number; day: number }; music?: string; atmo?: string } }
  | { type: 'chunk'; content: string }
  | { type: 'player'; content: string }
  | { type: 'briefing'; briefing: string; events: WorldEvent[] }
  | { type: 'state'; state: GameState }
  | { type: 'options'; options: OptionSpec[] }
  | { type: 'phase'; report: PhaseReport }
  | { type: 'done' }
  | { type: 'err'; content: string }
