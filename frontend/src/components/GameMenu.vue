<template>
  <!-- 主菜单页（全屏）：一个入口 → 菜单页 → 页内 tab 切换 地图/档案/在场/天下事/记忆 -->
  <!-- 菜单入口按钮（右下角，避开叙事区） -->
  <button v-if="!open" class="gm-toggle" @click="open = true">
    <span class="gm-toggle-icon">☰</span>
    <span>菜单</span>
    <!-- 汇总红点：天下事未读 + 记忆 PIN -->
    <span v-if="totalUnseen > 0" class="gm-badge">{{ totalUnseen > 9 ? '9+' : totalUnseen }}</span>
  </button>

  <!-- 全屏菜单页 -->
  <transition name="gm-fade">
    <div v-if="open" class="gm-overlay" @click.self="close">
      <div class="gm-panel">
        <!-- 头部：标题 + 世界日期 + 关闭 -->
        <div class="gm-header">
          <span class="gm-title">行 者 之 间</span>
          <span class="gm-date">{{ worldDateLabel }}</span>
          <button class="gm-close" @click="close">×</button>
        </div>

        <!-- Tab 栏 -->
        <div class="gm-tabs">
          <button
            v-for="t in TABS"
            :key="t.key"
            class="gm-tab"
            :class="{ 'gm-tab-active': activeTab === t.key }"
            @click="switchTab(t.key)"
          >
            <span>{{ t.label }}</span>
            <span v-if="tabBadge(t.key)" class="gm-tab-badge">{{ tabBadge(t.key) }}</span>
          </button>
        </div>

        <!-- 内容区（tab 切换） -->
        <div class="gm-content">
          <!-- 地图 -->
          <div v-if="activeTab === 'map'" class="gm-section">
            <LocationPanel
              embedded
              :location-state="locationState ?? { current: null, unlocked: [], next_station: null, rumored: [] }"
              @travel="(n) => emit('travel', n)"
              @ask="(n) => emit('ask', n)"
            />
          </div>

          <!-- 档案 -->
          <div v-else-if="activeTab === 'archive'" class="gm-section">
            <PlayerPanel v-if="player" embedded :player="player" />
          </div>

          <!-- 在场 -->
          <div v-else-if="activeTab === 'present'" class="gm-section">
            <CharacterPanel
              embedded
              :rels="rels"
              :trust="trust"
              :stances="stances"
              :character-states="characterStates"
              :reveal="reveal"
            />
          </div>

          <!-- 天下事 -->
          <div v-else-if="activeTab === 'world'" class="gm-section">
            <WorldMenu
              embedded
              :world-events="worldEvents"
              :world-rumors="worldRumors"
              :briefing="briefing"
              :world-date="worldDate"
              @read="() => emit('read')"
            />
          </div>

          <!-- 记忆 -->
          <div v-else-if="activeTab === 'memory'" class="gm-section">
            <MemoryDrawer
              embedded
              :stm-list="stmList"
              :ltm-list="ltmList"
              :pin-items="pinItems"
              :pins="pins"
              :pinned-count="pinnedCount"
              :total-mem-count="totalMemCount"
              :reveal="reveal"
              @toggle-pin="(id) => emit('togglePin', id)"
            />
          </div>

          <!-- 关系网 -->
          <div v-else-if="activeTab === 'relnet'" class="gm-section">
            <RelationshipPanel :rels="rels" :trust="trust" :stances="stances" />
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
// GameMenu —— 主菜单页（全屏 tab 切换 5 板块）
// 一个入口（右下"菜单"按钮）→ 全屏菜单页 → tab 切换 地图/档案/在场/天下事/记忆。
// 5 个面板组件以 embedded 模式嵌入（不渲染各自固定抽屉外壳），内容由本页 tab 容器流式布局。
// 红点汇总：天下事未读世界事件 + 记忆 PIN 数 + 在场角色数。
import { ref, computed } from 'vue'
import type { LocationState, MemoryItem, WorldEvent, PlayerState, CharacterState } from '../types/play'
import LocationPanel from './LocationPanel.vue'
import PlayerPanel from './PlayerPanel.vue'
import CharacterPanel from './CharacterPanel.vue'
import WorldMenu from './WorldMenu.vue'
import MemoryDrawer from './MemoryDrawer.vue'
import RelationshipPanel from './RelationshipPanel.vue'

const props = withDefaults(defineProps<{
  locationState?: LocationState | null
  player?: PlayerState | null
  rels?: Record<string, number>
  trust?: Record<string, number>
  stances?: Record<string, string>
  characterStates?: Record<string, CharacterState>
  worldEvents?: WorldEvent[]
  worldRumors?: string[]
  briefing?: string
  worldDate?: { year: number; month: number; day: number }
  stmList?: MemoryItem[]
  ltmList?: MemoryItem[]
  pinItems?: MemoryItem[]
  pins?: string[]
  pinnedCount?: number
  totalMemCount?: number
  reveal?: boolean
}>(), {
  locationState: () => ({ current: null, unlocked: [], next_station: null, rumored: [] }),
  player: null,
  rels: () => ({}),
  trust: () => ({}),
  stances: () => ({}),
  characterStates: () => ({}),
  worldEvents: () => [],
  worldRumors: () => [],
  briefing: '',
  worldDate: undefined,
  stmList: () => [],
  ltmList: () => [],
  pinItems: () => [],
  pins: () => [],
  pinnedCount: 0,
  totalMemCount: 0,
  reveal: false,
})
const emit = defineEmits<{
  (e: 'travel', name: string): void
  (e: 'ask', name: string): void
  (e: 'togglePin', id: string): void
  (e: 'read'): void
}>()

const open = ref(false)

const activeTab = ref('map')

const TABS = [
  { key: 'map', label: '地图' },
  { key: 'archive', label: '档案' },
  { key: 'present', label: '在场' },
  { key: 'world', label: '天下事' },
  { key: 'memory', label: '记忆' },
  { key: 'relnet', label: '关系网' },
]

function close() {
  open.value = false
}
function switchTab(key: string) {
  activeTab.value = key
  // 切到"天下事"tab：触发已读（置 seen + 落盘，与 WorldMenu toggle 打开时同机制）
  if (key === 'world') emit('read')
}

const worldDateLabel = computed(() => {
  const wd = props.worldDate
  if (!wd) return ''
  const months = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二']
  return `${wd.year}年${months[wd.month] || wd.month}月`
})

// 天下事未读
const worldUnseen = computed(() => (props.worldEvents ?? []).filter(e => !e.seen).length)
// 记忆 PIN 数
const memoryPinCount = computed(() => props.pinnedCount ?? (props.pins ?? []).length)
// 在场角色数（只算已登记/相识的角色——关系网预填的 30 人仅"闻其名"，不算在场）
const presentCount = computed(() => {
  const csMap = props.characterStates ?? {}
  const rels = props.rels ?? {}
  return Object.keys(csMap).filter(n => csMap[n]?.known === true || rels[n] !== undefined).length
})

// Tab 红点：天下事→未读；记忆→PIN 数；在场→在场人数
function tabBadge(key: string): number | '' {
  if (key === 'world') return worldUnseen.value > 0 ? worldUnseen.value : ''
  if (key === 'memory') return memoryPinCount.value > 0 ? memoryPinCount.value : ''
  if (key === 'present') return presentCount.value > 0 ? presentCount.value : ''
  return ''
}

// 汇总红点（菜单入口按钮）
const totalUnseen = computed(() => worldUnseen.value)
</script>

<style scoped>
/* 菜单入口按钮 */
.gm-toggle {
  position: fixed;
  right: 20px;
  top: 14px;
  z-index: 45;
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: "Noto Serif SC", "STKaiti", serif;
  font-size: 0.85rem;
  letter-spacing: 0.15em;
  color: rgba(232, 200, 140, 0.9);
  background: rgba(10, 10, 18, 0.82);
  border: 1px solid rgba(210, 180, 120, 0.25);
  border-radius: 999px;
  padding: 8px 18px;
  cursor: pointer;
  backdrop-filter: blur(8px);
  transition: all 0.25s;
}
.gm-toggle:hover { border-color: rgba(232, 200, 140, 0.5); color: #e8c88c; }
.gm-toggle-icon { font-size: 0.75rem; }
.gm-badge {
  min-width: 17px; height: 17px; line-height: 17px; padding: 0 5px;
  border-radius: 9px; background: #b5372a; color: #fff;
  font-size: 0.68rem; text-align: center; letter-spacing: 0;
}

/* 全屏菜单页：面板顶部固定到屏幕最上方（水平居中，垂直贴顶） */
.gm-overlay {
  position: fixed;
  inset: 0;
  z-index: 400;
  background: rgba(4, 4, 6, 0.78);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: flex-start;
  justify-content: center;
}
.gm-panel {
  width: min(680px, 94vw);
  max-height: 86vh;
  margin-top: 14px;              /* 顶部贴屏留一点呼吸，不贴死 */
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: rgba(12, 12, 18, 0.96);
  border: 1px solid rgba(210, 180, 120, 0.3);
  border-radius: 16px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.7);
}
.gm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px 12px;
  border-bottom: 1px solid rgba(202, 138, 4, 0.12);
}
.gm-title {
  font-family: "Noto Serif SC", "STKaiti", serif;
  font-size: 1.2rem;
  letter-spacing: 0.3em;
  color: #e8c88c;
}
.gm-date { font-size: 0.78rem; color: rgba(148, 163, 184, 0.6); }
.gm-close {
  background: none; border: none;
  color: rgba(148, 163, 184, 0.7);
  font-size: 1.4rem; cursor: pointer;
  line-height: 1; padding: 4px 8px;
}
.gm-close:hover { color: #e8c88c; }

/* Tab 栏 */
.gm-tabs {
  display: flex;
  gap: 4px;
  padding: 10px 24px 0;
  border-bottom: 1px solid rgba(202, 138, 4, 0.1);
}
.gm-tab {
  position: relative;
  background: none; border: none;
  font-family: "Noto Serif SC", "STKaiti", serif;
  font-size: 0.85rem;
  letter-spacing: 0.15em;
  color: rgba(148, 163, 184, 0.7);
  padding: 10px 16px;
  cursor: pointer;
  transition: all 0.25s;
  display: flex; align-items: center; gap: 6px;
}
.gm-tab:hover { color: rgba(232, 200, 140, 0.9); }
.gm-tab-active {
  color: #e8c88c;
  border-bottom: 2px solid #e8c88c;
}
.gm-tab-badge {
  min-width: 15px; height: 15px; line-height: 15px; padding: 0 4px;
  border-radius: 8px; background: #b5372a; color: #fff;
  font-size: 0.62rem; text-align: center;
}

/* 内容区：flex 子项需 min-height:0 才能在超高内容时内部滚动（否则撑破 gm-panel 溢屏） */
.gm-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px 24px;
}
.gm-section { min-height: 100%; }
.gm-fade-enter-active, .gm-fade-leave-active { transition: opacity 0.3s ease, transform 0.3s ease; }
.gm-fade-enter-from, .gm-fade-leave-to { opacity: 0; transform: scale(0.97); }
</style>
