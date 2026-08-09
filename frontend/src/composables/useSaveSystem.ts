// useSaveSystem —— 自由沙盒自动存档 / 断点续玩
// 玩家标识：前端首次进 Play 生成 uuid 存 localStorage，服务端按 pid 存 players 表。
// 每拍引擎跑完后 savePlayer（完整 GameState 快照覆盖），重进 loadPlayer 恢复。
import type { GameState } from '../types/play'

const API_BASE = import.meta.env.VITE_API_BASE || ''
const PLAYER_ID_KEY = 'sg3d_player_id'

/** 取当前玩家 id；无则生成并持久化（首次进游戏） */
export function getOrCreatePlayerId(): string {
  let pid = localStorage.getItem(PLAYER_ID_KEY)
  if (!pid) {
    pid = crypto.randomUUID()
    localStorage.setItem(PLAYER_ID_KEY, pid)
  }
  return pid
}

/** 只读当前玩家 id（无则不生成）——新开历险删旧档用 */
export function getPlayerId(): string | null {
  return localStorage.getItem(PLAYER_ID_KEY)
}

/** 新开历险：清当前 id 换新档 */
export function clearPlayerId(): void {
  localStorage.removeItem(PLAYER_ID_KEY)
}

/** 删除服务端玩家档案（新开历险放弃旧档，防孤儿档累积）；失败静默 */
export async function deletePlayer(pid: string): Promise<void> {
  if (!pid) return
  try {
    await fetch(`${API_BASE}/api/play/delete_player`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pid }),
    })
  } catch {
    // 删除失败不影响新开（旧档残留，后续清理）
  }
}

/** 自动快照：完整 GameState → players 表（每拍 onDone 后调用；失败静默，不打断游玩） */
export async function savePlayer(state: GameState | null): Promise<void> {
  if (!state) return
  try {
    await fetch(`${API_BASE}/api/play/save_player`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pid: getOrCreatePlayerId(), game_state: state }),
    })
  } catch {
    // 存档失败不影响当前游玩（下次快照会再试）
  }
}

/** 断点续玩：读当前玩家档案（无存档返回 hasSave=false） */
export async function loadPlayer(): Promise<{ hasSave: boolean; state: GameState | null }> {
  const pid = localStorage.getItem(PLAYER_ID_KEY)
  if (!pid) return { hasSave: false, state: null }
  try {
    const resp = await fetch(`${API_BASE}/api/play/load_player`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pid }),
    })
    const data = await resp.json()
    return { hasSave: data?.has_save === true, state: data?.state ?? null }
  } catch {
    return { hasSave: false, state: null }
  }
}
