<template>
  <!-- 世界菜单（自由大世界：世界公告/今日头条/街头传闻/与你有关 收进常驻菜单，红点亮起） -->
  <!-- embedded：主菜单页嵌入模式，不渲染 toggle 按钮与固定外壳，内容区由菜单 tab 容器流式布局 -->
  <div class="world-menu">
    <!-- 常驻开关：天下事 + 红点（有未读世界事件；embedded 时由主菜单 tab 承担） -->
    <button v-if="!embedded" class="menu-toggle" :class="{ 'menu-toggle-open': open }" @click="toggle">
      <span class="menu-toggle-icon">☰</span>
      <span>天下事</span>
      <span v-if="unseenCount > 0" class="menu-badge">{{ unseenCount > 9 ? '9+' : unseenCount }}</span>
    </button>

    <!-- 面板抽屉 -->
    <transition name="menu-fade">
      <div v-if="embedded || open" class="menu-drawer" :class="{ 'wm-embedded': embedded }" @click.stop>
        <div class="menu-header">
          <span class="menu-title">天 下 事</span>
          <span class="menu-date">{{ worldDateLabel }}</span>
        </div>

        <!-- 与你有关（红点优先展示） -->
        <div v-if="aboutYou.length" class="menu-section">
          <div class="menu-section-title">
            与你有关
            <span v-if="aboutYouUnseen" class="section-badge">{{ aboutYouUnseen }}</span>
          </div>
          <div v-for="e in aboutYou" :key="e.event_id" class="menu-item menu-strong" @click="markRead">
            <span class="menu-date-sm">{{ e.date }}</span>
            <span class="menu-text">{{ e.event }}</span>
          </div>
        </div>

        <!-- 今日头条（近期时间线大事件） -->
        <div v-if="headlines.length" class="menu-section">
          <div class="menu-section-title">今日头条</div>
          <div v-for="e in headlines" :key="e.event_id" class="menu-item" @click="markRead">
            <span class="menu-date-sm">{{ e.date }}</span>
            <span class="menu-text">{{ e.event }}</span>
          </div>
        </div>

        <!-- 世界公告（远方大事，LLM 合成简报 + 事件） -->
        <div v-if="announcements.length" class="menu-section">
          <div class="menu-section-title">
            世界公告
            <span v-if="announceUnseen" class="section-badge">{{ announceUnseen }}</span>
          </div>
          <p v-if="briefing" class="menu-briefing">{{ briefing }}</p>
          <div v-for="e in announcements" :key="e.event_id" class="menu-item" @click="markRead">
            <span class="menu-date-sm">{{ e.date }}</span>
            <span class="menu-text">{{ e.event }}</span>
          </div>
        </div>

        <!-- 街头传闻（NPC 传的、未证实的话） -->
        <div v-if="street.length" class="menu-section">
          <div class="menu-section-title">街头传闻</div>
          <div v-for="(r, i) in street" :key="i" class="menu-item menu-rumor">
            <span class="menu-rumor-mark">・</span>
            <span class="menu-text">{{ r }}</span>
          </div>
        </div>

        <div v-if="!hasAny" class="menu-empty">天下尚无大事，岁月静好。</div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
// WorldMenu —— 世界菜单面板（自由大世界）
// 数据源：gameState.world_events（含 source/related_to_player/seen）、world_rumors、briefing。
// 红点 = 未读 world_events；点读复用父组件 markBriefingRead（置 seen + savePlayer 落盘）。
import { ref, computed } from 'vue'
import type { WorldEvent } from '../types/play'

const props = defineProps<{
  world_events?: WorldEvent[]
  world_rumors?: string[]
  briefing?: string
  world_date?: { year: number; month: number; day: number }
  embedded?: boolean   // 主菜单页嵌入模式：不渲染 toggle 按钮与固定外壳，内容区由菜单 tab 容器布局
}>()
const emit = defineEmits<{ (e: 'read'): void }>()

const open = ref(false)

function toggle() {
  open.value = !open.value
  // 打开时标记已读（通知父组件置 seen + 落盘）
  if (open.value) emit('read')
}

function markRead() { emit('read') }

const worldDateLabel = computed(() => {
  const wd = props.world_date
  if (!wd) return ''
  const months = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二']
  return `${wd.year}年${months[wd.month] || wd.month}月`
})

const events = computed(() => props.world_events ?? [])

// 与你有关：related_to_player === 'strong'（未读优先）
const aboutYou = computed(() => {
  const es = events.value.filter(e => e.related_to_player === 'strong')
  return [...es.filter(e => !e.seen), ...es.filter(e => e.seen)].slice(0, 5)
})
const aboutYouUnseen = computed(() => events.value.filter(e => e.related_to_player === 'strong' && !e.seen).length)

// 今日头条：近期时间线大事件（timeline/period source，最近日期）
const headlines = computed(() => {
  const es = events.value
    .filter(e => e.source === 'timeline' || e.source === 'period')
    .sort((a, b) => (b.date || '').localeCompare(a.date || ''))
  return [...es.filter(e => !e.seen), ...es.filter(e => e.seen)].slice(0, 5)
})

// 世界公告：所有事件（含简报文本）
const announcements = computed(() => {
  const es = events.value.slice().reverse().slice(0, 5)
  return es
})
const announceUnseen = computed(() => events.value.filter(e => !e.seen).length)

// 街头传闻：world_rumors + 地点传闻
const street = computed(() => props.world_rumors ?? [])

const unseenCount = computed(() => events.value.filter(e => !e.seen).length)
const hasAny = computed(() =>
  aboutYou.value.length || headlines.value.length || announcements.value.length || street.value.length
)
</script>

<style scoped>
.world-menu {
  position: fixed;
  top: 14px;
  right: 80px;
  z-index: 50;
}
.menu-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: "Noto Serif SC", "STKaiti", serif;
  font-size: 0.85rem;
  letter-spacing: 0.15em;
  color: rgba(232, 200, 140, 0.9);
  background: rgba(10, 10, 18, 0.72);
  border: 1px solid rgba(210, 180, 120, 0.25);
  border-radius: 999px;
  padding: 7px 16px;
  cursor: pointer;
  transition: all 0.25s;
  backdrop-filter: blur(8px);
}
.menu-toggle:hover {
  border-color: rgba(232, 200, 140, 0.5);
  color: #e8c88c;
}
.menu-toggle-open {
  border-color: rgba(232, 200, 140, 0.5);
  background: rgba(10, 10, 18, 0.9);
}
.menu-toggle-icon { font-size: 0.75rem; }
.menu-badge {
  min-width: 17px;
  height: 17px;
  line-height: 17px;
  padding: 0 5px;
  border-radius: 9px;
  background: #b5372a;
  color: #fff;
  font-size: 0.68rem;
  text-align: center;
  letter-spacing: 0;
}
.menu-drawer {
  position: fixed;
  top: 52px;
  right: 20px;
  width: min(380px, 88vw);
  max-height: 66vh;
  overflow-y: auto;
  background: rgba(12, 12, 18, 0.94);
  border: 1px solid rgba(210, 180, 120, 0.3);
  border-radius: 14px;
  padding: 18px 20px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(16px);
}
/* 主菜单页嵌入：中和 fixed 四角定位，由菜单 tab 容器流式布局 */
.menu-drawer.wm-embedded {
  position: static;
  width: 100%;
  max-width: none;
  max-height: none;
  overflow-y: visible;
  background: transparent;
  border: none;
  box-shadow: none;
  backdrop-filter: none;
  padding: 0;
}
.menu-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(202, 138, 4, 0.12);
}
.menu-title {
  font-family: "Noto Serif SC", "STKaiti", serif;
  font-size: 1.05rem;
  letter-spacing: 0.35em;
  color: #e8c88c;
}
.menu-date {
  font-size: 0.75rem;
  color: rgba(148, 163, 184, 0.6);
}
.menu-section { margin-bottom: 16px; }
.menu-section-title {
  font-size: 0.8rem;
  letter-spacing: 0.12em;
  color: rgba(232, 200, 140, 0.7);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.section-badge {
  min-width: 15px;
  height: 15px;
  line-height: 15px;
  padding: 0 4px;
  border-radius: 8px;
  background: #b5372a;
  color: #fff;
  font-size: 0.62rem;
  text-align: center;
}
.menu-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 0.82rem;
  line-height: 1.6;
  color: rgba(226, 232, 240, 0.85);
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}
.menu-item:hover { background: rgba(255, 255, 255, 0.04); }
.menu-strong { border-left: 3px solid #e8c88c; background: rgba(232, 200, 140, 0.06); }
.menu-rumor { border-left: 3px solid rgba(148, 163, 184, 0.3); }
.menu-rumor-mark { color: rgba(148, 163, 184, 0.5); flex-shrink: 0; }
.menu-date-sm {
  font-size: 0.7rem;
  color: rgba(148, 163, 184, 0.6);
  flex-shrink: 0;
  padding-top: 2px;
}
.menu-text { flex: 1; }
.menu-briefing {
  font-size: 0.85rem;
  line-height: 1.7;
  color: rgba(240, 220, 174, 0.9);
  background: rgba(255, 255, 255, 0.04);
  border-left: 3px solid rgba(232, 200, 140, 0.45);
  border-radius: 0 8px 8px 0;
  padding: 10px 12px;
  margin: 0 0 10px;
}
.menu-empty {
  text-align: center;
  color: rgba(148, 163, 184, 0.5);
  font-size: 0.8rem;
  padding: 30px 0;
  letter-spacing: 0.1em;
}
.menu-fade-enter-active, .menu-fade-leave-active { transition: opacity 0.25s ease, transform 0.25s ease; }
.menu-fade-enter-from, .menu-fade-leave-to { opacity: 0; transform: translateY(-6px); }

/* ── 移动端适配（<768px）：抽屉全宽 + 避开安全区与顶部铭牌 ── */
@media (max-width: 768px) {
  .world-menu { top: max(10px, env(safe-area-inset-top)); right: 12px; }
  .menu-toggle { padding: 8px 14px; font-size: 0.8rem; }
  .menu-drawer {
    top: max(56px, calc(env(safe-area-inset-top) + 48px));
    right: 12px;
    width: calc(100vw - 24px);
    max-height: calc(100vh - 76px - env(safe-area-inset-bottom));
    padding: 14px 16px calc(18px + env(safe-area-inset-bottom));
  }
  .menu-section { margin-bottom: 14px; }
}
</style>
