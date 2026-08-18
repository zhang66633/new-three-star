<template>
  <div class="atmo-layer" aria-hidden="true">
    <!-- 当前氛围图 -->
    <img
      v-show="currentSrc"
      :src="currentSrc"
      class="atmo-img"
      :class="{ fading: transitioning }"
      alt=""
    />
    <!-- 下一张（crossfade 目标） -->
    <img
      v-if="nextSrc"
      :src="nextSrc"
      class="atmo-img atmo-next"
      :class="{ active: transitioning }"
      alt=""
    />

    <!-- 慢速漂移光晕 blob（Cinema Mobile 规范：animated ambient light blobs） -->
    <div class="atmo-blob"></div>
    <div class="atmo-blob blob-2"></div>

    <!-- 毛玻璃叠加层（Glassmorphism：backdrop-filter blur + 半透明深色） -->
    <div class="atmo-glass"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import atmoMap from '../assets/atmo/atmo_map.json'

const props = withDefaults(defineProps<{
  atmoTag?: string    // 情绪标签，如 "雨夜沉静"、"荒野苍茫"
}>(), {
  atmoTag: '雨夜沉静',
})

const CROSSFADE_MS = 3000  // 3s crossfade（匹配 Cinema Mobile expo.inOut）

const currentSrc = ref('')
const nextSrc = ref('')
const transitioning = ref(false)
let fadeTimer: number | null = null
let reqSeq = 0   // 单调递增请求序号：crossfade 期间连续切换时「最新请求为准」

// atmo 标签 → 图片文件名
function resolveImage(tag: string): string | null {
  let id = (atmoMap as Record<string, string>)[tag]
  if (!id) id = (atmoMap as Record<string, string>)['荒野苍茫']  // 未知标签兜底，防黑屏/背景不换
  if (!id) return null
  // Vite 静态资源：相对路径引用
  return new URL(`../assets/atmo/${id}.png`, import.meta.url).href
}

// 预加载图片（防 crossfade 时空白）
function preload(src: string): Promise<void> {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => resolve()
    img.onerror = () => resolve()  // 加载失败也继续，不阻塞
    img.src = src
  })
}

async function switchTo(tag: string) {
  const src = resolveImage(tag)
  if (!src || src === currentSrc.value) return

  const mySeq = ++reqSeq   // 本请求序号（作废更旧的在途请求）

  // 预加载新图
  await preload(src)

  // 预加载期间已触发更新的切换（A→B→A / A→B→C）→ 本次作废，以最新为准
  if (mySeq !== reqSeq) return

  // 清除旧定时器（旧图切换作废，防止旧回调落地覆盖新图）
  if (fadeTimer) clearTimeout(fadeTimer)

  // 设置新图，触发 crossfade
  nextSrc.value = src
  transitioning.value = true

  // crossfade 完成后：新图变当前，清理旧图（触发时再校验仍是最新请求）
  fadeTimer = window.setTimeout(() => {
    if (mySeq !== reqSeq) return   // 已有更新的在途 → 本次不落地
    currentSrc.value = src
    nextSrc.value = ''
    transitioning.value = false
    fadeTimer = null
  }, CROSSFADE_MS)
}

// 初始加载（无 crossfade，直接显示）
async function initImage(tag: string) {
  const src = resolveImage(tag)
  if (!src) return
  await preload(src)
  currentSrc.value = src
}

watch(() => props.atmoTag, (tag) => {
  if (currentSrc.value) {
    switchTo(tag)
  } else {
    initImage(tag)
  }
}, { immediate: true })
</script>

<style scoped>
.atmo-layer {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  background: #020203;  /* Cinema Mobile 最深底色（不用纯黑 #000，避免 OLED smear） */
}

/* ── 氛围图 ── */
.atmo-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.75;         /* 水墨纹理清晰可见 */
  transition: none;
  will-change: opacity;
}
/* crossfade：当前图淡出 */
.atmo-img.fading {
  transition: opacity 3s cubic-bezier(0.16, 1, 0.3, 1);  /* expo.inOut */
  opacity: 0;
}
/* 新图：从 0 淡入 */
.atmo-next {
  opacity: 0;
  transition: none;
}
.atmo-next.active {
  transition: opacity 3s cubic-bezier(0.16, 1, 0.3, 1);
  opacity: 0.75;  /* 与 .atmo-img 对齐 */
}

/* ── 慢速漂移光晕 blob ── */
.atmo-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.05;
  pointer-events: none;
}
.atmo-blob:not(.blob-2) {
  width: 60%;
  height: 50%;
  top: 10%;
  left: 5%;
  background: radial-gradient(circle, rgba(202, 138, 4, 0.4) 0%, transparent 70%);
  animation: blob-drift-1 45s ease-in-out infinite;
}
.atmo-blob.blob-2 {
  width: 50%;
  height: 40%;
  bottom: 5%;
  right: 5%;
  background: radial-gradient(circle, rgba(148, 163, 184, 0.3) 0%, transparent 70%);
  animation: blob-drift-2 55s ease-in-out infinite;
}

@keyframes blob-drift-1 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  25%  { transform: translate(12%, 8%) scale(1.15); }
  50%  { transform: translate(6%, 18%) scale(0.9); }
  75%  { transform: translate(-8%, 4%) scale(1.08); }
}
@keyframes blob-drift-2 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33%  { transform: translate(-10%, -5%) scale(1.12); }
  66%  { transform: translate(4%, -15%) scale(0.88); }
}

/* ── 毛玻璃 overlay ── */
.atmo-glass {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at center, transparent 40%, rgba(2, 2, 3, 0.25) 100%);
}

/* ── 响应式：移动端降模糊 ── */
@media (max-width: 768px) {
  .atmo-blob {
    filter: blur(60px);
    opacity: 0.03;
  }
}

/* ── prefers-reduced-motion ── */
@media (prefers-reduced-motion: reduce) {
  .atmo-blob {
    animation: none !important;
  }
  .atmo-img.fading,
  .atmo-next.active {
    transition: opacity 0.5s ease !important;
  }
}
</style>
