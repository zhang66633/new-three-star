// 成就 id → 中文名映射（展示层）
// 后端 player.achievements 存的是成就 id（见 backend/engine/player_data.py _ACHIEVEMENTS），
// 前端展示需名称映射。新增成就时两端同步（id 与 name 必须一致）。
export const ACH_NAMES: Record<string, string> = {
  'first_step': '迈出第一步',
  'survivor': '活下来了',
  'wealth_100': '小有积蓄',
  'witness_huangjin': '亲历黄金军',
  'reputation_30': '小有名声',
}
