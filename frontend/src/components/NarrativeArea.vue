<template>
  <!-- 叙事区（唯一滚动容器）：思维链阶段 + 叙事块 + 流式指示 -->
  <main class="narrative-area" ref="mainEl">
    <!-- ① 思维链阶段：AI 正在推演当前局势 -->
    <ThinkingPhase
      v-if="showThinking"
      :chapter-label="thinkingChapter"
      :title="thinkingTitle"
      :npc-list="npcList"
      :stm-count="stmCount"
      :ltm-count="ltmCount"
      :pin-count="pinCount"
      :foreshadow-count="foreshadowCount"
      :tension="tension"
    />

    <!-- ②-④ 剧情流式 / 记忆 / 人物 → 叙事文本 -->
    <div v-for="(block, i) in blocks" :key="i" class="narrative-block">
      <!-- 场景分隔（新场景标题） -->
      <div v-if="block.isScene" class="scene-divider">
        <span class="scene-divider-line"></span>
        <span class="scene-divider-text">{{ block.sceneTitle }}</span>
        <span class="scene-divider-line"></span>
      </div>
      <!-- 叙事文本（三种态：streaming 直出+光标 / reveal 打字机揭示一次 / 静态） -->
      <template v-if="!block.isScene">
        <p v-if="block.streaming"
           class="narrative-text" :class="{ playerPov: block.isPlayerPov }">
          <StreamText :text="block.text" :chunk-size="5" :speed="6" />
          <span v-if="block.isPlayerPov" class="pov-mark">·思绪</span>
        </p>
        <p v-else-if="block.text"
           class="narrative-text" :class="{ playerPov: block.isPlayerPov }">
          <StreamText v-if="block.reveal" :text="block.text" :chunk-size="3" :speed="12" />
          <template v-else>{{ block.text }}</template>
          <span v-if="block.isPlayerPov" class="pov-mark">·思绪</span>
        </p>
      </template>
    </div>
    <div v-if="isStreaming && !currentStreamText" class="streaming-indicator">
      <span class="gold-dot"></span>
      <span class="streaming-text">世界在低语……</span>
    </div>
  </main>
</template>

<script setup lang="ts">
// NarrativeArea —— 叙事区（PlayPage 抽离）
// 唯一滚动容器：内部集成 ThinkingPhase（思维链）+ 叙事块渲染 + 流式指示。
// 自滚动：仅在用户已接近底部时自动滚底，避免打断回读（不加 scroll-behavior:smooth，
// 逐 chunk 自动滚底会反复重启动画导致抖动）。
import { ref, watch, nextTick } from 'vue'
import ThinkingPhase from './ThinkingPhase.vue'
import StreamText from './StreamText.vue'
import type { NarrativeBlock } from '../composables/useNarrativeBlocks'

const props = defineProps<{
  showThinking: boolean
  thinkingChapter: string
  thinkingTitle: string
  npcList: Array<[string, number]>
  stmCount: number
  ltmCount: number
  pinCount: number
  foreshadowCount: number
  tension: number
  blocks: NarrativeBlock[]
  isStreaming: boolean
  currentStreamText: string
}>()

const mainEl = ref<HTMLElement | null>(null)

function scrollToBottom() {
  nextTick(() => {
    const el = mainEl.value
    if (!el) return
    // 仅在用户已接近底部时自动滚底，避免打断回读
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 120) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'auto' })
    }
  })
}

// 流式文本/新块到达 → 滚底（块内 text 被 useNarrativeBlocks 原地变更，需 deep 监听）
watch(() => props.currentStreamText, () => scrollToBottom())
watch(() => props.blocks, () => scrollToBottom(), { deep: true })
</script>

<style scoped>
.narrative-area {
  flex: 1;
  min-height: 0;  /* 允许收缩，配合 overflow-y:auto 产生滚动 */
  overflow-y: auto;
  padding: 24px 10%;
  max-width: 860px;        /* 舒适阅读宽度（~75 字/行） */
  margin: 0 auto;          /* 居中文本列 */
  width: 100%;
}
.narrative-area::-webkit-scrollbar {
  width: 4px;
}
.narrative-area::-webkit-scrollbar-track {
  background: transparent;
}
.narrative-area::-webkit-scrollbar-thumb {
  background: rgba(202, 138, 4, 0.25);
  border-radius: 2px;
}
.narrative-area::-webkit-scrollbar-thumb:hover {
  background: rgba(202, 138, 4, 0.5);
}
.narrative-block {
  margin-bottom: 18px;
  /* 新段落淡入（scroll-reveal 替代：opacity + translateY） */
  animation: block-enter 0.45s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes block-enter {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
.scene-divider {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 30px 0;
}
.scene-divider-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(202, 138, 4, 0.4), transparent);
}
.scene-divider-text {
  font-size: 0.85rem;
  letter-spacing: 0.3em;
  color: rgba(202, 138, 4, 0.8);
  white-space: nowrap;
}
.narrative-text {
  font-family: var(--font-body);
  font-size: 1.05rem;
  line-height: 2;
  letter-spacing: 0.03em;
  color: rgba(248, 250, 252, 0.92);
  text-align: justify;
  white-space: pre-line;        /* 保留 LLM 叙事换行（\n 渲染为换行） */
  overflow-wrap: break-word;    /* 长行安全折行 */
}
.narrative-text.playerPov {
  color: rgba(202, 138, 4, 0.75);
  font-style: italic;
}
.pov-mark {
  font-size: 0.7rem;
  color: rgba(202, 138, 4, 0.5);
  margin-left: 6px;
  letter-spacing: 0.2em;
}
/* 流式指示 */
.streaming-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
  color: rgba(148, 163, 184, 0.6);
  font-size: 0.8rem;
  letter-spacing: 0.2em;
}
.gold-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #ca8a04;
  box-shadow: 0 0 10px rgba(202, 138, 4, 0.8);
  animation: gold-pulse 1.2s ease-in-out infinite;
}
@keyframes gold-pulse {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}
/* 响应式 */
@media (max-width: 768px) {
  .narrative-area { padding: 16px 5%; }
}
/* prefers-reduced-motion：关闭所有动画 */
@media (prefers-reduced-motion: reduce) {
  .narrative-block {
    animation: none !important;
  }
}
</style>
