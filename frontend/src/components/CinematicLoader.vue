<template>
  <div class="cinematic-loader" :class="{ visible: show }" aria-live="polite">
    <!-- 聚光灯暗场背景 -->
    <div class="spotlight"></div>
    <div class="darkness"></div>

    <!-- 中央内容 -->
    <div class="loader-content">
      <!-- 章节标题（渐进显影） -->
      <transition name="title-reveal">
        <div v-if="title" class="loader-title" :key="title">
          <span class="title-chapter">{{ chapterLabel }}</span>
          <span class="title-main">{{ title }}</span>
          <span class="title-goldline"></span>
        </div>
      </transition>

      <!-- 台词轮播（随机初始位置） -->
      <div class="quote-stage">
        <transition name="quote-cycle" mode="out-in">
          <div class="quote-block" :key="quoteIndex">
            <p class="quote-text">{{ currentQuote.text }}</p>
            <p v-if="currentQuote.speaker" class="quote-speaker">—— {{ currentQuote.speaker }}</p>
          </div>
        </transition>
      </div>

      <!-- 加载指示：金箔呼吸 -->
      <div class="loader-indicator">
        <span class="ember"></span>
        <span class="ember" style="animation-delay: 0.4s"></span>
        <span class="ember" style="animation-delay: 0.8s"></span>
      </div>
    </div>

    <!-- 底部流式状态（可插槽） -->
    <div v-if="statusText" class="loader-status">{{ statusText }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'

interface Quote {
  text: string
  speaker?: string
}

const props = withDefaults(defineProps<{
  show: boolean
  title?: string          // 章节标题（如「三国」）
  chapterLabel?: string   // 章节铭牌（如「建安三年 · 许都」）
  quotes?: Quote[]        // 自定义台词池（默认用新三台词）
  interval?: number       // 轮换间隔 ms
  statusText?: string     // 底部状态文字
}>(), {
  title: '',
  chapterLabel: '',
  interval: 2500,
  statusText: '',
})

// 默认台词池：已确认归属的新三台词（含用户更正）
const DEFAULT_QUOTES: Quote[] = [
  { text: '只有这厕所才是最安全的地方，你看见这个地方了吗，它才是朕真正的帝位。', speaker: '汉献帝' },
  { text: '我挥剑只有一次，可我磨剑磨了十几年哪。', speaker: '司马懿' },
  { text: '孔明何等人物，只要有钱粮在手他马上会变出十万精兵来！', speaker: '曹操' },
  { text: '一帮吃货，混账！你们是来打仗的还是来调情的！', speaker: '许攸' },
  { text: '好方略，不过我想稍作修改。', speaker: '曹操' },
  { text: '不可能！我二弟天下无敌！', speaker: '刘备' },
  { text: '接着奏乐接着舞。', speaker: '刘备' },
  { text: '叉出去！', speaker: '袁术' },
  { text: '死是凉爽的夏夜，可供人无忧地安眠。', speaker: '曹操' },
  { text: '自刎归天。', speaker: '刘备' },
  { text: '大凡正人君子，其肉都太酸。酒酸？咱家说了，不怕酸！', speaker: '董卓' },
  { text: '我部悍将刘三刀，三刀之内必斩吕布于马下！', speaker: '诸侯' },
  { text: '我堂堂吕布，为何成了三姓家奴？', speaker: '吕布' },
  { text: '你把我骂得惊天动地、山呼海啸、狗血淋头，叫我听得好享受啊！', speaker: '曹操' },
]

const quotes = computed(() => (props.quotes && props.quotes.length ? props.quotes : DEFAULT_QUOTES))
const quoteIndex = ref(0)
let timer: number | null = null

// 每次显示时随机初始位置
watch(() => props.show, (val) => {
  if (val) startCycle()
  else stopCycle()
})

onMounted(() => {
  if (props.show) startCycle()
})
onBeforeUnmount(() => stopCycle())

function startCycle() {
  stopCycle()
  quoteIndex.value = Math.floor(Math.random() * quotes.value.length)
  timer = window.setInterval(() => {
    quoteIndex.value = (quoteIndex.value + 1) % quotes.value.length
  }, props.interval)
}
function stopCycle() {
  if (timer) { clearInterval(timer); timer = null }
}

const currentQuote = computed(() => quotes.value[quoteIndex.value] || { text: '', speaker: '' })
</script>

<style scoped>
/* ═════════ 聚光灯暗场 ═════════ */
.cinematic-loader {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.5s ease;
}
.cinematic-loader.visible {
  opacity: 1;
  pointer-events: auto;
}

.darkness {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at 50% 45%, rgba(15, 15, 35, 0.98) 0%, rgba(2, 2, 3, 1) 70%);
}

/* 聚光灯：中央一道金箔光柱 */
.spotlight {
  position: absolute;
  top: -20%;
  left: 50%;
  transform: translateX(-50%);
  width: 520px;
  height: 140%;
  background: linear-gradient(
    to bottom,
    rgba(202, 138, 4, 0.10) 0%,
    rgba(202, 138, 4, 0.05) 40%,
    rgba(202, 138, 4, 0.02) 70%,
    transparent 100%
  );
  filter: blur(30px);
  animation: spotlight-breathe 3.2s ease-in-out infinite;
  pointer-events: none;
}
@keyframes spotlight-breathe {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}

/* ═════════ 内容布局 ═════════ */
.loader-content {
  position: relative;
  z-index: 2;
  text-align: center;
  max-width: 720px;
  padding: 0 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 36px;
}

/* ═════════ 章节标题 ═════════ */
.loader-title {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}
.title-chapter {
  font-size: 0.85rem;
  letter-spacing: 0.5em;
  color: rgba(202, 138, 4, 0.7);
  font-family: var(--font-body);
  text-transform: uppercase;
}
.title-main {
  font-family: var(--font-display);
  font-weight: 900;
  font-size: clamp(2.2rem, 5vw, 3.4rem);
  letter-spacing: 0.28em;
  color: #f8fafc;
  text-shadow: 0 0 24px rgba(202, 138, 4, 0.35);
  /* 逐字点亮 */
  background: linear-gradient(180deg, #ffffff 0%, #e2d8b0 45%, #ca8a04 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.title-goldline {
  width: 180px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(202, 138, 4, 0.8), transparent);
  margin-top: 6px;
}
.title-reveal-enter-active { transition: all 0.9s cubic-bezier(0.16, 1, 0.3, 1); }
.title-reveal-enter-from { opacity: 0; transform: translateY(16px); filter: blur(8px); }
.title-reveal-leave-active { transition: all 0.4s ease; }
.title-reveal-leave-to { opacity: 0; }

/* ═════════ 台词轮播 ═════════ */
.quote-stage {
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.quote-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
}
.quote-text {
  font-family: var(--font-body);
  font-size: clamp(1.05rem, 2.2vw, 1.35rem);
  line-height: 1.9;
  letter-spacing: 0.06em;
  color: rgba(248, 250, 252, 0.88);
  max-width: 620px;
}
.quote-speaker {
  font-size: 0.8rem;
  letter-spacing: 0.35em;
  color: rgba(202, 138, 4, 0.65);
}
.quote-cycle-enter-active { transition: all 0.6s ease; }
.quote-cycle-leave-active { transition: all 0.4s ease; }
.quote-cycle-enter-from { opacity: 0; transform: translateY(12px); filter: blur(4px); }
.quote-cycle-leave-to { opacity: 0; transform: translateY(-8px); }

/* ═════════ 金箔呼吸指示 ═════════ */
.loader-indicator {
  display: flex;
  gap: 14px;
}
.ember {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #ca8a04;
  box-shadow: 0 0 12px rgba(202, 138, 4, 0.8);
  animation: ember-pulse 1.2s ease-in-out infinite;
}
@keyframes ember-pulse {
  0%, 100% { opacity: 0.25; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.15); }
}

/* ═════════ 底部状态 ═════════ */
.loader-status {
  position: absolute;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 0.75rem;
  letter-spacing: 0.3em;
  color: rgba(148, 163, 184, 0.6);
  font-family: var(--font-body);
}
</style>
