<template>
  <!-- 记忆抽屉（三段式：PIN / LTM / STM） -->
  <button class="memory-toggle" :class="{ 'mem-reveal': reveal }" @click="showMemory = !showMemory">
    {{ showMemory ? '收起记忆 ▲' : '记忆' }}
    <span v-if="totalMemCount > 0" class="mt-counts">
      STM [{{ stmList.length }}/6]｜LTM [{{ ltmList.length }}]｜PIN {{ pinnedCount }}
    </span>
  </button>
  <div v-if="showMemory" class="memory-drawer">
    <!-- 计数头 -->
    <div class="md-header">STM [{{ stmList.length }}/6]｜LTM [{{ ltmList.length }}]｜PIN {{ pinnedCount }}条</div>

    <!-- 📌 PIN 钉选记忆 -->
    <div class="md-section">
      <div class="md-section-title">📌 PIN 钉选记忆</div>
      <div v-if="pinItems.length === 0" class="md-empty-row">— 暂无 —</div>
      <div v-for="(m, i) in pinItems" :key="m.id" class="memory-row">
        <span class="mr-num">{{ i + 1 }}</span>
        <span class="mr-time">{{ m.time || '—' }}</span>
        <span class="mr-scene">{{ m.scene || '—' }}</span>
        <span class="mr-text">{{ m.text }}</span>
        <button class="mi-pin pinned" @click="emit('togglePin', m.id)" aria-label="取消钉选">📌</button>
      </div>
    </div>

    <!-- 📚 LTM 长期记忆 -->
    <div class="md-section">
      <div class="md-section-title">📚 LTM 长期记忆</div>
      <div v-if="ltmList.length === 0" class="md-empty-row">— 暂无 —</div>
      <div v-for="(m, i) in ltmList" :key="m.id" class="memory-row">
        <span class="mr-num">{{ i + 1 }}</span>
        <span class="mr-time">{{ m.time || '—' }}</span>
        <span class="mr-scene">{{ m.scene || '—' }}</span>
        <span class="mr-text">{{ m.text }}</span>
        <button
          class="mi-pin"
          :class="{ pinned: isPinned(m.id) }"
          @click="emit('togglePin', m.id)"
          :aria-label="isPinned(m.id) ? '取消钉选' : '钉选'"
        >{{ isPinned(m.id) ? '📌' : '📍' }}</button>
      </div>
    </div>

    <!-- 📝 STM 短期记忆 -->
    <div class="md-section">
      <div class="md-section-title">📝 STM 短期记忆</div>
      <div v-if="stmList.length === 0" class="md-empty-row">— 暂无 —</div>
      <div v-for="(m, i) in stmList" :key="m.id" class="memory-row">
        <span class="mr-num">{{ i + 1 }}</span>
        <span class="mr-time">{{ m.time || '—' }}</span>
        <span class="mr-scene">{{ m.scene || '—' }}</span>
        <span class="mr-text">{{ m.text }}</span>
        <button
          class="mi-pin"
          :class="{ pinned: isPinned(m.id) }"
          @click="emit('togglePin', m.id)"
          :aria-label="isPinned(m.id) ? '取消钉选' : '钉选'"
        >{{ isPinned(m.id) ? '📌' : '📍' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// MemoryDrawer —— 记忆抽屉（PlayPage 抽离）
// PIN/LTM/STM 三段展示；钉选状态由父组件维护（emit togglePin），抽屉开合为内部态。
import { ref } from 'vue'
import type { MemoryItem } from '../types/play'

const props = defineProps<{
  stmList: MemoryItem[]
  ltmList: MemoryItem[]
  pinItems: MemoryItem[]
  pins: string[]
  pinnedCount: number
  totalMemCount: number
  reveal: boolean   // 记忆阶段高亮（loadPhase === 'memory'）
}>()
const emit = defineEmits<{ (e: 'togglePin', id: string): void }>()

const showMemory = ref(false)

function isPinned(id: string) {
  return props.pins.includes(id)
}
</script>

<style scoped>
.memory-toggle {
  position: fixed;
  right: 20px;
  top: 14px;
  background: rgba(10, 10, 18, 0.82);
  border: 1px solid rgba(202, 138, 4, 0.25);
  color: #ca8a04;
  border-radius: 20px;
  padding: 7px 16px;
  font-size: 0.75rem;
  cursor: pointer;
  z-index: 30;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  transition: all 0.3s ease;
  letter-spacing: 0.05em;
  display: flex;
  align-items: center;
  gap: 8px;
}
.mt-counts {
  font-size: 0.62rem;
  color: rgba(202, 168, 100, 0.6);
  letter-spacing: 0.03em;
}
.memory-toggle:hover {
  background: rgba(202, 138, 4, 0.12);
  border-color: rgba(202, 138, 4, 0.5);
}
.memory-drawer {
  position: fixed;
  right: 20px;
  top: 50px;
  width: 420px;
  max-width: calc(100vw - 40px);
  height: 70vh;
  max-height: calc(100vh - 70px);
  background: rgba(10, 10, 18, 0.94);
  border: 1px solid rgba(202, 138, 4, 0.2);
  border-radius: 14px;
  padding: 16px 18px;
  z-index: 30;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
  animation: drawer-slide-down 0.3s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes drawer-slide-down {
  from { opacity: 0; transform: translateY(-8px) scale(0.97); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
.md-header {
  font-size: 0.62rem;
  letter-spacing: 0.25em;
  color: rgba(202, 138, 4, 0.5);
  text-align: center;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(202, 138, 4, 0.12);
  flex-shrink: 0;
}
.md-section {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
  margin-bottom: 10px;
  padding-right: 4px;
}
.md-section:last-child { margin-bottom: 0; }
.md-section::-webkit-scrollbar { width: 3px; }
.md-section::-webkit-scrollbar-thumb { background: rgba(202, 138, 4, 0.15); border-radius: 3px; }
.md-section-title {
  font-size: 0.62rem;
  letter-spacing: 0.2em;
  color: rgba(202, 168, 100, 0.55);
  margin-bottom: 6px;
  padding-left: 2px;
}
.md-empty-row {
  font-size: 0.7rem;
  color: rgba(148, 163, 184, 0.25);
  padding: 4px 8px;
  font-style: italic;
}
.memory-row {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 5px 4px;
  font-size: 0.78rem;
  color: rgba(226, 232, 240, 0.85);
  line-height: 1.5;
  border-bottom: 1px solid rgba(148, 163, 184, 0.04);
  animation: mem-row-enter 0.25s ease both;
}
.memory-row:nth-child(2) { animation-delay: 0.03s; }
.memory-row:nth-child(3) { animation-delay: 0.06s; }
.memory-row:nth-child(4) { animation-delay: 0.09s; }
.memory-row:nth-child(5) { animation-delay: 0.12s; }
.memory-row:nth-child(6) { animation-delay: 0.15s; }
@keyframes mem-row-enter {
  from { opacity: 0; transform: translateX(4px); }
  to   { opacity: 1; transform: translateX(0); }
}
.mr-num {
  font-size: 0.55rem;
  color: rgba(202, 168, 100, 0.3);
  min-width: 14px;
  flex-shrink: 0;
  text-align: right;
  padding-top: 1px;
}
.mr-time {
  font-size: 0.58rem;
  color: rgba(90, 122, 106, 0.4);
  white-space: nowrap;
  flex-shrink: 0;
  min-width: 52px;
  max-width: 64px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mr-scene {
  font-size: 0.58rem;
  color: rgba(90, 122, 106, 0.35);
  white-space: nowrap;
  flex-shrink: 0;
  min-width: 48px;
  max-width: 72px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mr-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.mi-pin {
  background: none;
  border: none;
  font-size: 0.72rem;
  cursor: pointer;
  opacity: 0.3;
  flex-shrink: 0;
  transition: opacity 0.2s;
  padding: 1px 2px;
}
.mi-pin:hover { opacity: 0.7; }
.mi-pin.pinned { opacity: 1; }
/* 记忆浮现高亮 */
.memory-toggle.mem-reveal {
  animation: mem-glow 0.8s ease-in-out;
  border-color: rgba(202, 138, 4, 0.65) !important;
  box-shadow: 0 0 18px rgba(202, 138, 4, 0.2);
}
@keyframes mem-glow {
  0%   { box-shadow: 0 0 0px rgba(202, 138, 4, 0); }
  50%  { box-shadow: 0 0 24px rgba(202, 138, 4, 0.35); }
  100% { box-shadow: 0 0 8px rgba(202, 138, 4, 0.12); }
}
</style>
