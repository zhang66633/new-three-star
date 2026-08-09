<template>
  <!-- 章节铭牌：时代标签 + 章节 + 世界日期 + 8 PHASE 指示灯 + 天意修正徽章 -->
  <header class="era-banner">
    <span class="era-label">{{ eraLabel }}</span>
    <span class="era-chapter">{{ eraChapter }}</span>
    <span v-if="worldDateLabel" class="era-clock" title="世界日期（自由沙盒）">{{ worldDateLabel }}</span>
    <span class="era-goldline"></span>
    <!-- 8 PHASE 质量指示灯 -->
    <button
      v-if="phaseReport"
      class="phase-indicator"
      :class="{ 'phase-warn': hasPhaseWarnings }"
      @click="showPhaseDetail = !showPhaseDetail"
      aria-label="校验报告"
    >◈</button>
    <!-- 天意修正指示器 -->
    <span v-if="correctedCount > 0" class="corrected-badge" :title="lastCorrected">
      修正×{{ correctedCount }}
    </span>
    <!-- PHASE 详情面板 -->
    <div v-if="showPhaseDetail && phaseReport" class="phase-detail">
      <div class="pd-title">8 PHASE 校验</div>
      <div v-for="(v, k) in phaseReport.llm" :key="k" class="pd-row">
        <span class="pd-phase">{{ k.toUpperCase() }}</span>
        <span class="pd-status" :class="v.pass ? 'pd-pass' : 'pd-fail'">{{ v.pass ? '✓' : '✗' }}</span>
        <span class="pd-reason">{{ v.reason }}</span>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
// EraBanner —— 章节铭牌 + 校验/修正指示（PlayPage 抽离，纯展示）
import { ref, computed } from 'vue'
import type { PhaseReport } from '../types/play'

const props = defineProps<{
  eraLabel: string
  eraChapter: string
  worldDateLabel: string
  phaseReport: PhaseReport | null
  correctedCount: number
  lastCorrected: string
}>()

const showPhaseDetail = ref(false)

// PHASE 质量报告：是否有硬校验未通过
const hasPhaseWarnings = computed(() => {
  const llm = props.phaseReport?.llm
  if (!llm) return false
  const hardPhases = ['p0', 'p1', 'p2', 'p3', 'p4', 'p5']
  return hardPhases.some(p => llm[p] && !llm[p].pass)
})
</script>

<style scoped>
.era-banner {
  padding: 30px 24px 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  position: relative;
}
.era-banner::after {
  content: '';
  position: absolute;
  bottom: 0; left: 50%; transform: translateX(-50%);
  width: 60px; height: 1px;
  background: radial-gradient(circle, rgba(202, 138, 4, 0.25), transparent);
}
.era-label {
  font-size: 0.75rem;
  letter-spacing: 0.45em;
  color: rgba(202, 138, 4, 0.6);
  text-transform: uppercase;
}
.era-chapter {
  font-family: var(--font-display);
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: 0.3em;
  color: #f1f5f9;
  text-shadow: 0 0 30px rgba(202, 138, 4, 0.15);
}
.era-goldline {
  width: 120px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(202, 138, 4, 0.4), transparent);
}
.era-clock {
  font-size: 0.7rem;
  letter-spacing: 0.2em;
  color: rgba(226, 232, 240, 0.6);
  border: 1px solid rgba(202, 138, 4, 0.35);
  border-radius: 999px;
  padding: 2px 10px;
  white-space: nowrap;
}
/* 8 PHASE 质量指示灯 */
.phase-indicator {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: rgba(90, 122, 106, 0.5);    /* 青铜绿 */
  font-size: 0.6rem;
  cursor: pointer;
  padding: 4px 6px;
  transition: color 0.3s, text-shadow 0.3s;
}
.phase-indicator:hover {
  color: rgba(90, 122, 106, 0.85);
  text-shadow: 0 0 6px rgba(90, 122, 106, 0.3);
}
.phase-indicator.phase-warn {
  color: rgba(192, 64, 48, 0.7);     /* 校验未过→赤铁色 */
}
/* 天意修正徽章 */
.corrected-badge {
  position: absolute;
  right: 10px;
  top: calc(50% - 14px);
  font-size: 0.55rem;
  letter-spacing: 0.1em;
  color: rgba(192, 64, 48, 0.55);
  background: rgba(192, 64, 48, 0.08);
  border: 1px solid rgba(192, 64, 48, 0.15);
  border-radius: 8px;
  padding: 1px 8px;
  cursor: help;
}
/* PHASE 详情面板 */
.phase-detail {
  position: absolute;
  right: 10px;
  top: 100%;
  width: 260px;
  background: rgba(10, 10, 18, 0.96);
  border: 1px solid rgba(90, 122, 106, 0.2);
  border-radius: 10px;
  padding: 10px 12px;
  z-index: 25;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.5);
  animation: phase-in 0.25s ease both;
}
@keyframes phase-in {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}
.pd-title {
  font-size: 0.6rem;
  letter-spacing: 0.25em;
  text-transform: uppercase;
  color: rgba(90, 122, 106, 0.55);
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.06);
}
.pd-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.68rem;
  padding: 2px 0;
}
.pd-phase {
  color: rgba(202, 138, 4, 0.5);
  font-weight: 500;
  min-width: 24px;
}
.pd-status {
  font-size: 0.6rem;
  min-width: 16px;
}
.pd-pass { color: #4a9ea0; }
.pd-fail { color: #c04030; }
.pd-reason {
  color: rgba(148, 163, 184, 0.5);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
