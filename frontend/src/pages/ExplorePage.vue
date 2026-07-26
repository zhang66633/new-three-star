<template>
  <div class="explore">
    <button class="back-btn" @click="goBack">←</button>

    <!-- 加载状态 -->
    <div v-if="pageLoading" class="page-status">
      <div class="status-spinner"></div>
      <p>证据浮现中……</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="pageError" class="page-status">
      <p class="error-text">世界线断裂，无法加载此世界</p>
      <button class="retry-btn" @click="goBack">返回星图</button>
    </div>

    <!-- 证据墙 -->
    <div v-else class="evidence-wall" ref="wallRef">
      <!-- SVG连线层 -->
      <svg class="connections-layer" :viewBox="`0 0 100 100`" preserveAspectRatio="none">
        <line
          v-for="(line, i) in connectionLines"
          :key="i"
          :x1="line.x1" :y1="line.y1"
          :x2="line.x2" :y2="line.y2"
          class="conn-line"
          :class="{ lit: linesLit }"
          :style="{ transitionDelay: `${i * 30}ms` }"
        />
      </svg>

      <!-- 证据卡片 -->
      <div
        v-for="(card, i) in evidence"
        :key="card.id"
        class="evidence-card"
        :class="{ visible: card.visible, active: activeCard?.id === card.id, dimmed: activeCard && activeCard.id !== card.id }"
        :style="{ left: card.x + '%', top: card.y + '%', transitionDelay: card.visible ? '0ms' : `${i * 120}ms` }"
        @click="openCard(card)"
      >
        <span class="card-type" :class="card.type">{{ typeLabel(card.type) }}</span>
        <h3 class="card-title">{{ card.title }}</h3>
        <p class="card-summary">{{ card.summary }}</p>
      </div>

      <!-- 核心结论 -->
      <transition name="conclusion-fade">
        <div v-if="showConclusion" class="conclusion">
          <p>{{ conclusion }}</p>
        </div>
      </transition>
    </div>

    <!-- 卡片展开：AI解读 -->
    <transition name="interpret-fade">
      <div v-if="activeCard" class="interpret-overlay" @click.self="closeCard">
        <div class="interpret-panel">
          <button class="interpret-close" @click="closeCard">✕</button>
          <span class="card-type" :class="activeCard.type">{{ typeLabel(activeCard.type) }}</span>
          <h2 class="interpret-title">{{ activeCard.title }}</h2>
          <p class="interpret-summary">{{ activeCard.summary }}</p>
          <div class="interpret-divider"></div>
          <div v-if="interpretContent" class="interpret-content" :class="{ streaming: isInterpreting }" v-html="renderMd(interpretContent)"></div>
          <div v-else-if="isInterpreting" class="interpret-loading">天意推演中……</div>
          <button v-else class="interpret-btn" @click="startInterpret">深度解读</button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE || ''

const pageLoading = ref(true)
const pageError = ref(false)
const wallRef = ref<HTMLElement>()

interface EvidenceCard {
  id: string
  type: 'mechanism' | 'character' | 'event'
  title: string
  summary: string
  connects: string[]
  x: number
  y: number
  visible: boolean
}

const evidence = ref<EvidenceCard[]>([])
const conclusion = ref('')
const linesLit = ref(false)
const showConclusion = ref(false)
const activeCard = ref<EvidenceCard | null>(null)
const interpretContent = ref('')
const isInterpreting = ref(false)

let revealTimers: number[] = []

const connectionLines = computed(() => {
  const lines: { x1: number; y1: number; x2: number; y2: number }[] = []
  const seen = new Set<string>()
  for (const card of evidence.value) {
    for (const targetId of card.connects) {
      const key = [card.id, targetId].sort().join('-')
      if (seen.has(key)) continue
      seen.add(key)
      const target = evidence.value.find(c => c.id === targetId)
      if (target) {
        lines.push({ x1: card.x, y1: card.y, x2: target.x, y2: target.y })
      }
    }
  }
  return lines
})

function typeLabel(type: string) {
  const map: Record<string, string> = { mechanism: '机制', character: '角色', event: '事件' }
  return map[type] || type
}

function goBack() {
  router.push('/')
}

async function loadEvidence() {
  const worldId = route.params.id as string
  try {
    const resp = await fetch(`${API_BASE}/data/evidence/${worldId}.json`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    conclusion.value = data.conclusion
    evidence.value = data.evidence.map((e: any) => ({ ...e, visible: false }))
    pageLoading.value = false
    startRevealSequence()
  } catch (e) {
    console.error('Failed to load evidence:', e)
    pageLoading.value = false
    pageError.value = true
  }
}

function startRevealSequence() {
  const cards = evidence.value
  // 逐张浮现
  cards.forEach((card, i) => {
    const timer = window.setTimeout(() => {
      card.visible = true
    }, 400 + i * 150)
    revealTimers.push(timer)
  })
  // 全部浮现后，连线亮起
  const linesTimer = window.setTimeout(() => {
    linesLit.value = true
  }, 400 + cards.length * 150 + 500)
  revealTimers.push(linesTimer)
  // 连线亮起后，结论浮现
  const conclusionTimer = window.setTimeout(() => {
    showConclusion.value = true
  }, 400 + cards.length * 150 + 1500)
  revealTimers.push(conclusionTimer)
}

function openCard(card: EvidenceCard) {
  activeCard.value = card
  interpretContent.value = ''
  isInterpreting.value = false
}

function closeCard() {
  activeCard.value = null
  interpretContent.value = ''
  isInterpreting.value = false
}

async function startInterpret() {
  if (!activeCard.value) return
  isInterpreting.value = true
  interpretContent.value = ''
  try {
    const resp = await fetch(`${API_BASE}/api/worldview/node-dive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        framework_id: route.params.id,
        node_name: activeCard.value.title,
        node_summary: activeCard.value.summary,
        node_type: activeCard.value.type,
      }),
    })
    const reader = resp.body?.getReader()
    if (!reader) return
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const msg = JSON.parse(line.slice(6))
          if (msg.type === 'chunk') {
            interpretContent.value += msg.content
          } else if (msg.type === 'done') {
            isInterpreting.value = false
          }
        } catch {}
      }
    }
  } catch (e) {
    interpretContent.value = '（天意推演失败，请稍后再试）'
  }
  isInterpreting.value = false
}

function renderMd(text: string) {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

onMounted(() => {
  loadEvidence()
})

onBeforeUnmount(() => {
  revealTimers.forEach(t => clearTimeout(t))
})
</script>

<style scoped>
.explore {
  width: 100%;
  height: 100vh;
  position: relative;
  overflow: hidden;
  background: #050508;
}

.back-btn {
  position: fixed;
  top: 24px;
  left: 24px;
  z-index: 200;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.15);
  color: #aaa;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  font-size: 1.2rem;
  cursor: pointer;
  transition: all 0.2s;
}
.back-btn:hover { color: #fff; border-color: rgba(255,255,255,0.4); }

.page-status {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #8888aa;
}
.status-spinner {
  width: 32px; height: 32px;
  border: 2px solid rgba(136,136,170,0.2);
  border-top-color: #8888aa;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.error-text { color: #e05545; }
.retry-btn {
  background: transparent; border: 1px solid #555; color: #aaa;
  padding: 8px 24px; border-radius: 4px; cursor: pointer;
}
.retry-btn:hover { border-color: #aaa; color: #fff; }

/* 证据墙 */
.evidence-wall {
  position: absolute;
  inset: 0;
  overflow: auto;
}

.connections-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 1;
}
.conn-line {
  stroke: rgba(100, 120, 255, 0);
  stroke-width: 0.15;
  transition: stroke 0.8s ease;
}
.conn-line.lit {
  stroke: rgba(100, 140, 255, 0.4);
  filter: drop-shadow(0 0 2px rgba(100, 140, 255, 0.6));
}

/* 证据卡片 */
.evidence-card {
  position: absolute;
  transform: translate(-50%, -50%) scale(0.8);
  width: clamp(160px, 18vw, 240px);
  padding: 14px 16px;
  background: rgba(15, 15, 25, 0.75);
  border: 1px solid rgba(100, 120, 255, 0.15);
  border-radius: 8px;
  backdrop-filter: blur(8px);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.5s ease, transform 0.5s ease, border-color 0.3s, box-shadow 0.3s;
  z-index: 10;
}
.evidence-card.visible {
  opacity: 1;
  transform: translate(-50%, -50%) scale(1);
}
.evidence-card:hover {
  border-color: rgba(100, 140, 255, 0.5);
  box-shadow: 0 0 20px rgba(100, 140, 255, 0.15);
}
.evidence-card.dimmed {
  opacity: 0.2;
  pointer-events: none;
}
.evidence-card.active {
  border-color: rgba(100, 180, 255, 0.7);
  box-shadow: 0 0 30px rgba(100, 140, 255, 0.3);
}

.card-type {
  display: inline-block;
  font-size: 0.6rem;
  padding: 2px 6px;
  border-radius: 3px;
  margin-bottom: 6px;
  letter-spacing: 0.1em;
}
.card-type.mechanism { color: #4a9eff; border: 1px solid rgba(74,158,255,0.3); }
.card-type.character { color: #e8a838; border: 1px solid rgba(232,168,56,0.3); }
.card-type.event { color: #e05545; border: 1px solid rgba(224,85,69,0.3); }

.card-title {
  font-size: 0.85rem;
  color: #e8e8f0;
  margin: 0 0 6px;
  font-weight: 600;
  line-height: 1.3;
}
.card-summary {
  font-size: 0.7rem;
  color: #8888aa;
  margin: 0;
  line-height: 1.5;
}

/* 结论 */
.conclusion {
  position: fixed;
  bottom: 5%;
  left: 50%;
  transform: translateX(-50%);
  z-index: 50;
  text-align: center;
  max-width: 600px;
  padding: 20px 32px;
  background: rgba(5, 5, 8, 0.85);
  border: 1px solid rgba(255, 215, 0, 0.2);
  border-radius: 8px;
  backdrop-filter: blur(12px);
}
.conclusion p {
  font-size: 0.95rem;
  color: #ffd700;
  line-height: 1.8;
  margin: 0;
  letter-spacing: 0.05em;
}
.conclusion-fade-enter-active { transition: opacity 1.2s ease; }
.conclusion-fade-enter-from { opacity: 0; }

/* AI解读浮层 */
.interpret-overlay {
  position: fixed;
  inset: 0;
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(3, 3, 6, 0.85);
  backdrop-filter: blur(4px);
}
.interpret-panel {
  position: relative;
  width: min(560px, 85vw);
  max-height: 75vh;
  overflow-y: auto;
  padding: 32px;
  background: rgba(12, 12, 20, 0.95);
  border: 1px solid rgba(100, 140, 255, 0.2);
  border-radius: 12px;
}
.interpret-close {
  position: absolute;
  top: 16px; right: 20px;
  background: none; border: none;
  color: #666; font-size: 1.3rem; cursor: pointer;
}
.interpret-close:hover { color: #fff; }
.interpret-title {
  font-size: 1.4rem;
  color: #f0f0f8;
  margin: 8px 0 8px;
}
.interpret-summary {
  font-size: 0.85rem;
  color: #8888aa;
  margin: 0 0 16px;
  line-height: 1.6;
}
.interpret-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(100,140,255,0.3), transparent);
  margin-bottom: 16px;
}
.interpret-content {
  font-size: 0.9rem;
  color: #c8c8dd;
  line-height: 1.9;
}
.interpret-content.streaming {
  border-right: 2px solid rgba(100,180,255,0.6);
  animation: blink-cursor 0.8s step-end infinite;
}
@keyframes blink-cursor { 50% { border-color: transparent; } }
.interpret-loading {
  color: #6666aa;
  font-size: 0.85rem;
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse { 0%,100% { opacity: 0.5; } 50% { opacity: 1; } }
.interpret-btn {
  background: transparent;
  border: 1px solid rgba(100,140,255,0.4);
  color: #88aaff;
  padding: 10px 28px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  letter-spacing: 0.1em;
  transition: all 0.2s;
}
.interpret-btn:hover {
  background: rgba(100,140,255,0.1);
  border-color: rgba(100,140,255,0.7);
}

.interpret-fade-enter-active { transition: opacity 0.3s ease; }
.interpret-fade-leave-active { transition: opacity 0.2s ease; }
.interpret-fade-enter-from, .interpret-fade-leave-to { opacity: 0; }
</style>
