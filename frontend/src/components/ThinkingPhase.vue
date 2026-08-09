<template>
  <!-- 思维链阶段：AI 正在推演当前局势 -->
  <div class="thinking-phase">
    <div class="think-header">
      <span class="think-icon">◈</span>
      <span class="think-title">天意正在推演此局……</span>
    </div>
    <div class="think-detail">
      <div class="think-row">
        <span class="think-label">场景</span>
        <span class="think-val">{{ chapterLabel }} · {{ title }}</span>
      </div>
      <div class="think-row" v-if="npcList.length">
        <span class="think-label">在场</span>
        <span class="think-val">
          <span v-for="(n, i) in npcList" :key="n[0]" class="think-npc">
            {{ n[0] }}<span class="think-npc-rel" :class="relClass(n[1])">感{{ n[1] }}</span>
            <span v-if="i < npcList.length - 1"> · </span>
          </span>
        </span>
      </div>
      <div class="think-row">
        <span class="think-label">记忆</span>
        <span class="think-val">STM {{ stmCount }} 条 · LTM {{ ltmCount }} 条 · PIN {{ pinCount }} 条</span>
      </div>
      <div class="think-row" v-if="foreshadowCount">
        <span class="think-label">伏笔</span>
        <span class="think-val think-foreshadow">{{ foreshadowCount }} 条未解</span>
      </div>
      <div class="think-row">
        <span class="think-label">天意</span>
        <span class="think-val" :class="tensionClass(tension)">{{ tension }}/100</span>
      </div>
    </div>
    <div class="think-pulse">
      <span class="think-ember"></span>
      <span class="think-ember" style="animation-delay:0.4s"></span>
      <span class="think-ember" style="animation-delay:0.8s"></span>
    </div>
  </div>
</template>

<script setup lang="ts">
// ThinkingPhase —— 思维链推演面板（PlayPage 抽离，纯展示）
import { relClass, tensionClass } from '../utils/classes'

defineProps<{
  chapterLabel: string
  title: string
  npcList: Array<[string, number]>
  stmCount: number
  ltmCount: number
  pinCount: number
  foreshadowCount: number
  tension: number
}>()
</script>

<style scoped>
.thinking-phase {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  padding: 40px 0 50px;
  animation: think-enter 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes think-enter {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}
.think-header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.think-icon {
  font-size: 1.1rem;
  color: rgba(202, 138, 4, 0.6);
  animation: think-rotate 3s linear infinite;
}
@keyframes think-rotate {
  to { transform: rotate(360deg); }
}
.think-title {
  font-family: var(--font-display);
  font-size: 1.1rem;
  letter-spacing: 0.25em;
  color: rgba(202, 138, 4, 0.7);
}
.think-detail {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  max-width: 480px;
  padding: 16px 20px;
  background: rgba(10, 10, 18, 0.5);
  border: 1px solid rgba(202, 138, 4, 0.12);
  border-radius: 12px;
}
.think-row {
  display: flex;
  gap: 12px;
  font-size: 0.82rem;
  line-height: 1.5;
}
.think-label {
  color: rgba(202, 138, 4, 0.45);
  min-width: 36px;
  letter-spacing: 0.08em;
  flex-shrink: 0;
}
.think-val {
  color: rgba(226, 232, 240, 0.75);
}
.think-npc {
  white-space: nowrap;
}
.think-npc-rel {
  font-size: 0.62rem;
  margin-left: 2px;
}
.think-foreshadow {
  color: rgba(192, 64, 48, 0.55);
}
.think-pulse {
  display: flex;
  gap: 12px;
  margin-top: 4px;
}
.think-ember {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: rgba(202, 138, 4, 0.5);
  animation: think-ember-pulse 1.4s ease-in-out infinite;
}
@keyframes think-ember-pulse {
  0%, 100% { opacity: 0.2; transform: scale(0.7); }
  50%      { opacity: 1;   transform: scale(1.2); }
}
</style>
