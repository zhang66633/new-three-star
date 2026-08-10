<template>
  <!-- 地点导航（左侧抽屉）：已知地点往返 + 下站推进（自由沙盒 §5.2） -->
  <!-- embedded：主菜单页嵌入模式，不渲染 toggle 按钮与固定外壳，内容区由菜单 tab 容器流式布局 -->
  <button v-if="!embedded" class="map-toggle" :class="{ 'map-toggle-open': open }" @click="open = !open">
    {{ open ? '收起地图 ▼' : '地图' }}
  </button>

  <transition name="map-slide">
    <div v-if="embedded || open" class="location-panel" :class="{ 'lp-embedded': embedded }">
      <div class="lp-header">天下舆图</div>
      <div class="lp-sub">去过的地方可往返，下站指引前路</div>

      <div class="lp-list">
        <div
          v-for="loc in LOCATION_ORDER"
          :key="loc"
          class="lp-row"
          :class="rowClass(loc)"
          @click="onRowClick(loc)"
        >
          <div class="lp-main">
            <span class="lp-name">{{ loc }}</span>
            <span v-if="rumorHint(loc)" class="lp-hint-text">{{ rumorHint(loc) }}</span>
          </div>
          <span class="lp-tag" v-if="isCurrent(loc)">在处</span>
          <span class="lp-tag lp-next" v-else-if="isNext(loc)">下站 →</span>
          <span class="lp-tag lp-go" v-else-if="isUnlocked(loc)">可前往</span>
          <span class="lp-tag lp-rumor" v-else-if="isRumored(loc)">传闻 · 打听可去</span>
          <span class="lp-tag lp-lock" v-else>未知</span>
        </div>
      </div>

      <div class="lp-hint">点选地点赶路 · 传闻点选打听解锁 · 或直接输入「前往X」</div>
    </div>
  </transition>
</template>

<script setup lang="ts">
// LocationPanel —— 地点导航面板（PlayPage 抽离补充）
// 地点列表对齐后端 worlddata.LOCATIONS（新增地点两端同步）。
// current=在处 / unlocked=可往返 / next_station=下站（推进目标）/ 其余未知灰显。
// 点选 → emit travel(name)，页面发「前往name」走 director 导航。
import { ref, computed } from 'vue'
import type { LocationState } from '../types/play'

const props = defineProps<{
  locationState: LocationState
  embedded?: boolean   // 主菜单页嵌入模式：不渲染 toggle 按钮与固定外壳，内容区由菜单 tab 容器布局
}>()
const emit = defineEmits<{
  (e: 'travel', name: string): void
  (e: 'ask', name: string): void
}>()

const open = ref(false)

// 剧情顺序展示：优先后端动态下发的全量地点列表（防前端硬编码与 LOCATIONS 失步）；
// 旧存档缺失 locations 字段时回退本地 P1 兜底列表
const LOCATION_ORDER = computed(() => {
  const dynamic = props.locationState?.locations
  return dynamic && dynamic.length ? dynamic : ['颍川', '洛阳', '中牟', '成皋', '陈留']
})

const unlockedSet = computed(() => new Set(props.locationState?.unlocked ?? []))
const rumoredMap = computed(() => {
  const m: Record<string, string> = {}
  for (const r of props.locationState?.rumored ?? []) m[r.name] = r.hint
  return m
})

function isCurrent(loc: string) {
  return props.locationState?.current === loc
}
function isNext(loc: string) {
  return props.locationState?.next_station === loc
}
function isUnlocked(loc: string) {
  return unlockedSet.value.has(loc)
}
function isRumored(loc: string) {
  return loc in rumoredMap.value
}
function rumorHint(loc: string): string {
  return rumoredMap.value[loc] ?? ''
}
function rowClass(loc: string): string {
  if (isCurrent(loc)) return 'lp-current'
  if (isNext(loc)) return 'lp-next'
  if (isUnlocked(loc)) return 'lp-unlocked'
  if (isRumored(loc)) return 'lp-rumor'
  return 'lp-unknown'
}
/** 行点击：在处/未知不可点；传闻行 → 打听（解锁后可前往）；其余 → 前往 */
function onRowClick(loc: string) {
  if (isCurrent(loc) || rowClass(loc) === 'lp-unknown') return
  if (isRumored(loc)) emit('ask', loc)
  else emit('travel', loc)
}
</script>

<style scoped>
.map-toggle {
  position: fixed;
  left: 20px;
  bottom: 20px;
  z-index: 35;
  background: rgba(10, 10, 18, 0.82);
  border: 1px solid rgba(202, 138, 4, 0.25);
  color: #ca8a04;
  border-radius: 20px;
  padding: 7px 18px;
  font-size: 0.75rem;
  cursor: pointer;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  transition: all 0.3s ease;
  letter-spacing: 0.12em;
}
.map-toggle:hover {
  background: rgba(202, 138, 4, 0.12);
  border-color: rgba(202, 138, 4, 0.5);
}
.map-toggle-open {
  border-color: rgba(202, 138, 4, 0.5);
  background: rgba(202, 138, 4, 0.12);
}

.location-panel {
  position: fixed;
  left: 20px;
  bottom: 62px;
  z-index: 35;
  width: 220px;
  max-width: calc(100vw - 40px);
  max-height: 60vh;
  overflow-y: auto;
  background: rgba(10, 10, 18, 0.94);
  border: 1px solid rgba(202, 138, 4, 0.2);
  border-radius: 14px;
  padding: 14px 16px;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
}
/* 主菜单页嵌入：中和 fixed 四角定位，由菜单 tab 容器流式布局 */
.location-panel.lp-embedded {
  position: static;
  width: 100%;
  max-width: none;
  max-height: none;
  background: transparent;
  border: none;
  box-shadow: none;
  backdrop-filter: none;
  padding: 0;
}
.location-panel::-webkit-scrollbar { width: 3px; }
.location-panel::-webkit-scrollbar-thumb { background: rgba(202, 138, 4, 0.15); border-radius: 3px; }

.lp-header {
  font-size: 0.8rem;
  letter-spacing: 0.3em;
  color: rgba(202, 138, 4, 0.9);
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(202, 138, 4, 0.12);
}
.lp-sub {
  font-size: 0.62rem;
  color: rgba(148, 163, 184, 0.5);
  letter-spacing: 0.03em;
  margin: 6px 0 10px;
}
.lp-list { display: flex; flex-direction: column; gap: 6px; }
.lp-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 10px;
  font-size: 0.8rem;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.lp-row.lp-current {
  color: #e8c88c;
  border-color: rgba(232, 200, 140, 0.4);
  background: rgba(232, 200, 140, 0.07);
  cursor: default;
}
.lp-row.lp-unlocked {
  color: rgba(226, 232, 240, 0.85);
  background: rgba(255, 255, 255, 0.03);
}
.lp-row.lp-unlocked:hover {
  background: rgba(202, 138, 4, 0.1);
  border-color: rgba(202, 138, 4, 0.4);
  transform: translateX(2px);
}
.lp-row.lp-next {
  color: #f0dcae;
  border-color: rgba(202, 138, 4, 0.5);
  background: rgba(202, 138, 4, 0.08);
}
.lp-row.lp-next:hover {
  background: rgba(202, 138, 4, 0.16);
  transform: translateX(2px);
}
.lp-row.lp-rumor {
  color: rgba(202, 168, 100, 0.78);
  border-color: rgba(202, 168, 100, 0.22);
  background: rgba(202, 168, 100, 0.05);
  border-left: 2px solid rgba(202, 168, 100, 0.35);
  cursor: pointer;
}
.lp-row.lp-rumor:hover {
  background: rgba(202, 138, 4, 0.12);
  border-color: rgba(202, 138, 4, 0.45);
  transform: translateX(2px);
}
.lp-row.lp-unknown {
  color: rgba(148, 163, 184, 0.35);
  cursor: default;
  opacity: 0.6;
}
.lp-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}
.lp-hint-text {
  font-size: 0.58rem;
  color: rgba(148, 163, 184, 0.45);
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.lp-tag {
  font-size: 0.6rem;
  flex-shrink: 0;
  letter-spacing: 0.05em;
}
.lp-next .lp-tag { color: #e8c88c; }
.lp-go { color: rgba(74, 158, 160, 0.8); }
.lp-rumor .lp-tag.lp-rumor { color: rgba(202, 168, 100, 0.85); }
.lp-lock { color: rgba(148, 163, 184, 0.4); }
.lp-hint {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed rgba(148, 163, 184, 0.1);
  font-size: 0.6rem;
  color: rgba(148, 163, 184, 0.35);
  letter-spacing: 0.03em;
}

.map-slide-enter-active { transition: opacity 0.25s ease, transform 0.25s cubic-bezier(0.16, 1, 0.3, 1); }
.map-slide-leave-active { transition: opacity 0.2s ease, transform 0.2s ease; }
.map-slide-enter-from, .map-slide-leave-to { opacity: 0; transform: translateY(8px); }
</style>
