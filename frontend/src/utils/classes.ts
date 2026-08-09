// 情绪/张力类名工具（PlayPage 各子组件共用，单一来源）
// 关系/信任值 0-100 → 三档类名；张力 0-100 → 三色（青=顺历史 / 鎏金=局部 / 赤铁=硬干预）

export function relClass(v: number) {
  if (v >= 60) return 'rel-high'
  if (v >= 30) return 'rel-mid'
  return 'rel-low'
}

export function trustClass(v: number) {
  if (v >= 60) return 'trust-high'
  if (v >= 30) return 'trust-mid'
  return 'trust-low'
}

export function tensionClass(t: number) {
  if (t <= 30) return 'tension-low'
  if (t <= 70) return 'tension-mid'
  return 'tension-high'
}
