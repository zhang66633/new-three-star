<template>
  <!-- 玩家档案面板（右下可折叠抽屉）：资产 / 金钱·声望 / 状态 / 称号 / 已解锁成就 -->
  <button class="panel-toggle" :class="{ 'panel-toggle-open': open }" @click="open = !open">
    {{ open ? '收起档案 ▼' : '行者档案' }}
    <span v-if="!open" class="pt-badge">{{ player.coins }}钱</span>
  </button>

  <transition name="panel-slide">
    <div v-if="open" class="player-panel">
      <div class="pp-header">
        行者档案
        <span class="pp-identity">{{ player.identity }}</span>
      </div>

      <!-- 金钱 · 声望 -->
      <div class="pp-row">
        <span class="pp-label">金钱</span>
        <span class="pp-val pp-coins">{{ player.coins }} 钱</span>
      </div>
      <div class="pp-row">
        <span class="pp-label">声望</span>
        <span class="pp-val pp-rep">{{ player.reputation }}/100</span>
      </div>

      <!-- 状态三栏：体力 / 饥饿 / 伤势（0-100） -->
      <div class="pp-stats">
        <div v-for="s in STAT_KEYS" :key="s.key" class="pp-stat">
          <span class="pp-stat-name">{{ s.label }}</span>
          <div class="pp-bar"><div class="pp-fill" :class="s.cls" :style="{ width: statVal(s.key) + '%' }"></div></div>
          <span class="pp-stat-num">{{ statVal(s.key) }}</span>
        </div>
      </div>

      <!-- 资产 -->
      <div class="pp-row pp-chips-row">
        <span class="pp-label">资产</span>
        <div class="pp-chips">
          <span v-if="!player.assets.length" class="pp-empty">身无长物</span>
          <span v-for="(a, i) in player.assets" :key="i" class="pp-chip">{{ a }}</span>
        </div>
      </div>

      <!-- 称号 -->
      <div class="pp-row pp-chips-row" v-if="player.titles.length">
        <span class="pp-label">称号</span>
        <div class="pp-chips">
          <span v-for="(t, i) in player.titles" :key="'t' + i" class="pp-chip pp-title">「{{ t }}」</span>
        </div>
      </div>

      <!-- 成就（只显示已解锁） -->
      <div class="pp-row pp-chips-row pp-ach-row">
        <span class="pp-label">成就</span>
        <div class="pp-chips">
          <span v-if="!player.achievements.length" class="pp-empty">尚无成就</span>
          <span v-for="(a, i) in player.achievements" :key="'a' + i" class="pp-chip pp-ach">✓ {{ ACH_NAMES[a] ?? a }}</span>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
// PlayerPanel —— 玩家档案面板（PlayPage 抽离补充）
// 展示自由沙盒玩家数据（state.player）：资产/金钱/声望/状态/称号/已解锁成就。
// 纯展示；成就 id→名称映射见 utils/achievements.ts。
import { ref } from 'vue'
import type { PlayerState } from '../types/play'
import { ACH_NAMES } from '../utils/achievements'

const props = defineProps<{ player: PlayerState }>()

const open = ref(false)

// 状态三栏定义（0-100；伤势越高越糟，色相反）
const STAT_KEYS = [
  { key: 'stamina', label: '体力', cls: 'st-stamina' },
  { key: 'hunger', label: '饥饿', cls: 'st-hunger' },
  { key: 'wound', label: '伤势', cls: 'st-wound' },
] as const

function statVal(key: string): number {
  return (props.player.stats as Record<string, number>)[key] ?? 0
}
</script>

<style scoped>
.panel-toggle {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 35;
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(10, 10, 18, 0.82);
  border: 1px solid rgba(202, 138, 4, 0.25);
  color: #ca8a04;
  border-radius: 20px;
  padding: 7px 16px;
  font-size: 0.75rem;
  cursor: pointer;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  transition: all 0.3s ease;
  letter-spacing: 0.05em;
}
.panel-toggle:hover {
  background: rgba(202, 138, 4, 0.12);
  border-color: rgba(202, 138, 4, 0.5);
}
.panel-toggle-open {
  border-color: rgba(202, 138, 4, 0.5);
  background: rgba(202, 138, 4, 0.12);
}
.pt-badge {
  font-size: 0.62rem;
  color: rgba(202, 168, 100, 0.8);
  border: 1px solid rgba(202, 168, 100, 0.3);
  border-radius: 10px;
  padding: 1px 8px;
}

.player-panel {
  position: fixed;
  right: 20px;
  bottom: 62px;
  z-index: 35;
  width: 300px;
  max-width: calc(100vw - 40px);
  max-height: 66vh;
  overflow-y: auto;
  background: rgba(10, 10, 18, 0.94);
  border: 1px solid rgba(202, 138, 4, 0.2);
  border-radius: 14px;
  padding: 14px 18px;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.player-panel::-webkit-scrollbar { width: 3px; }
.player-panel::-webkit-scrollbar-thumb { background: rgba(202, 138, 4, 0.15); border-radius: 3px; }

.pp-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 0.78rem;
  letter-spacing: 0.25em;
  color: rgba(202, 138, 4, 0.9);
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(202, 138, 4, 0.12);
  margin-bottom: 2px;
}
.pp-identity {
  font-size: 0.62rem;
  letter-spacing: 0.08em;
  color: rgba(148, 163, 184, 0.6);
}

.pp-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 0.78rem;
  line-height: 1.5;
}
.pp-label {
  color: rgba(148, 163, 184, 0.55);
  min-width: 34px;
  flex-shrink: 0;
  letter-spacing: 0.1em;
}
.pp-val { color: rgba(226, 232, 240, 0.85); }
.pp-coins { color: #e8c88c; font-weight: 500; }
.pp-rep { color: rgba(74, 158, 160, 0.9); }

/* 状态三栏 */
.pp-stats { display: flex; flex-direction: column; gap: 4px; }
.pp-stat {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.7rem;
}
.pp-stat-name {
  color: rgba(148, 163, 184, 0.6);
  min-width: 30px;
  flex-shrink: 0;
}
.pp-bar {
  flex: 1;
  height: 4px;
  background: rgba(148, 163, 184, 0.12);
  border-radius: 2px;
  overflow: hidden;
}
.pp-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}
.st-stamina { background: linear-gradient(90deg, #4a9ea0, #7ec8a0); }
.st-hunger  { background: linear-gradient(90deg, #e8a838, #f0c060); }
.st-wound   { background: linear-gradient(90deg, #c04030, #e06050); }
.pp-stat-num {
  color: rgba(226, 232, 240, 0.7);
  min-width: 22px;
  text-align: right;
  font-size: 0.62rem;
}

/* 资产/称号/成就标签 */
.pp-chips-row { align-items: flex-start; }
.pp-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.pp-chip {
  font-size: 0.68rem;
  color: rgba(226, 232, 240, 0.8);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 8px;
  padding: 1px 8px;
}
.pp-title {
  color: rgba(232, 200, 140, 0.85);
  border-color: rgba(202, 138, 4, 0.3);
}
.pp-ach {
  color: #7ec8a0;
  border-color: rgba(74, 158, 160, 0.25);
}
.pp-empty {
  font-size: 0.68rem;
  color: rgba(148, 163, 184, 0.3);
  font-style: italic;
}
.pp-ach-row { padding-top: 6px; border-top: 1px dashed rgba(148, 163, 184, 0.1); }

.panel-slide-enter-active { transition: opacity 0.25s ease, transform 0.25s cubic-bezier(0.16, 1, 0.3, 1); }
.panel-slide-leave-active { transition: opacity 0.2s ease, transform 0.2s ease; }
.panel-slide-enter-from, .panel-slide-leave-to { opacity: 0; transform: translateY(8px); }
</style>
