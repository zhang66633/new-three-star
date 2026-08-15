<template>
  <div class="create">
    <button class="back-btn" @click="goBack">←</button>

    <!-- 输入阶段 -->
    <div v-if="phase === 'input'" class="input-phase">
      <div class="nebula-core">
        <div class="nebula-ring"></div>
        <div class="nebula-ring ring-2"></div>
        <div class="nebula-glow"></div>
      </div>

      <h1 class="create-title">创造新世界</h1>
      <p class="create-sub">输入一个概念、一段设定、或你对某个世界的核心理解</p>

      <div class="input-ritual">
        <textarea
          v-model="concept"
          class="concept-input"
          rows="3"
          @keydown.ctrl.enter="generate"
        ></textarea>
        <div class="input-glow"></div>
      </div>

      <button class="forge-btn" :class="{ ready: concept.trim() }" :disabled="!concept.trim()" @click="generate">
        <span class="forge-text">凝 聚</span>
        <span class="forge-pulse"></span>
      </button>

      <div class="verified-hints">
        <button v-for="kw in verifiedKeywords" :key="kw" class="hint-chip" @click="concept = kw">{{ kw }}</button>
      </div>
    </div>

    <!-- 生成阶段：节点逐个生长 -->
    <div v-else class="grow-phase">
      <div ref="graphRef" class="graph-container"></div>
      <div class="grow-status" v-if="phase === 'growing'">
        <span class="grow-text">世界凝聚中…… {{ grownCount }} 个节点已生成</span>
      </div>
      <div class="grow-done" v-if="phase === 'done'">
        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
        <button class="share-btn" @click="goBack">在星图中查看</button>
        <button class="back-star-btn" @click="generateShareCard">生成分享卡片</button>
      </div>
    </div>

    <!-- 世界宣言预览浮层 -->
    <transition name="card-fade">
      <div v-if="showCard" class="card-overlay" @click.self="showCard = false">
        <div class="card-preview">
          <img :src="cardDataUrl" class="card-img" />
          <div class="card-actions">
            <a :href="cardDataUrl" :download="`世界宣言_${concept}.png`" class="card-dl-btn">保存宣言</a>
            <button class="card-close-btn" @click="showCard = false">关闭</button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onBeforeUnmount, inject } from 'vue'
import { useRouter } from 'vue-router'
import ForceGraph3D from '3d-force-graph'
import { apiKeyHeaders } from '../apiKey'
const ForceGraph3DAny = ForceGraph3D as any

const router = useRouter()
const graphRef = ref<HTMLElement>()
const concept = ref('')
const phase = ref<'input' | 'growing' | 'done'>('input')
const grownCount = ref(0)
const playGuanyu = inject<() => void>('playGuanyu', () => {})

const showCard = ref(false)
const errorMsg = ref('')
const cardDataUrl = ref('')

const verifiedKeywords = [
  '曹操是穿越者',
  '赤壁是核战争',
  '三国是一场梦境',
  '时间循环',
  '克苏鲁神话',
  '量子力学',
]

const API_BASE = import.meta.env.VITE_API_BASE || ''

let graphInstance: any = null
let currentNodes: any[] = []
let currentLinks: any[] = []

onMounted(() => {
  playGuanyu()
})

function goBack() {
  router.push('/')
}

async function saveWorld() {
  if (currentNodes.length === 0) return
  try {
    await fetch(`${API_BASE}/api/worlds`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: concept.value.trim().slice(0, 12) || '新世界',
        tagline: `由"${concept.value.trim()}"诞生`,
        concept: concept.value.trim(),
        graph: { nodes: currentNodes, links: currentLinks },
      }),
    })
  } catch (e) {
    console.warn('Save world failed:', e)
  }
}

async function generate() {
  if (!concept.value.trim()) return
  phase.value = 'growing'
  grownCount.value = 0
  currentNodes = []
  currentLinks = []

  await nextTick()
  initGrowGraph()

  try {
    const resp = await fetch(`${API_BASE}/api/worldview/custom-graph`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...apiKeyHeaders() },
      body: JSON.stringify({ concept: concept.value.trim() }),
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
          if (msg.type === 'node') {
            currentNodes.push(msg.node)
            grownCount.value++
            graphInstance.graphData({ nodes: [...currentNodes], links: [...currentLinks] })
          } else if (msg.type === 'link') {
            currentLinks.push(msg.link)
            graphInstance.graphData({ nodes: [...currentNodes], links: [...currentLinks] })
          } else if (msg.type === 'done') {
            phase.value = 'done'
            saveWorld()
          }
        } catch {}
      }
    }
  } catch (e) {
    console.error('Generation failed:', e)
    phase.value = 'done'
    errorMsg.value = '世界凝聚失败，请检查网络后重试'
  }
}

function initGrowGraph() {
  if (!graphRef.value) return
  const colorMap: Record<string, string> = {
    character: '#e8a838', tianyi: '#ffd700', spacetime: '#4a9eff',
    military: '#e05545', social: '#45c48a', item: '#38c8c8', creature: '#a878e8',
  }

  graphInstance = ForceGraph3DAny()(graphRef.value)
    .graphData({ nodes: [], links: [] })
    .backgroundColor('#030306')
    .showNavInfo(false)
    .autoRotate(true)
    .autoRotateSpeed(0.4)
    .nodeRelSize(4)
    .nodeVal((n: any) => n.type === 'character' ? 14 : 7)
    .nodeColor((n: any) => colorMap[n.type] || '#888')
    .nodeOpacity(0.85)
    .linkColor(() => 'rgba(160, 160, 200, 0.12)')
    .linkWidth(0.8)
    .linkDirectionalParticles(2)
    .linkDirectionalParticleWidth(1.5)
    .linkDirectionalParticleColor(() => 'rgba(232, 168, 56, 0.3)')
    .nodeLabel((n: any) => `<div style="font-family:'Noto Serif SC',serif;padding:6px 10px;background:rgba(3,3,6,0.92);border-radius:4px;color:#f0f0f8;">${n.name}</div>`)

  const resize = () => {
    if (graphInstance && graphRef.value) {
      graphInstance.width(graphRef.value.clientWidth)
      graphInstance.height(graphRef.value.clientHeight)
    }
  }
  window.addEventListener('resize', resize)
  resize()
}

function generateShareCard() {
  const W = 1080, H = 1920
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')!

  // 深空背景
  const bg = ctx.createLinearGradient(0, 0, 0, H)
  bg.addColorStop(0, '#050510')
  bg.addColorStop(0.5, '#0a0a1e')
  bg.addColorStop(1, '#030308')
  ctx.fillStyle = bg
  ctx.fillRect(0, 0, W, H)

  // 星点
  for (let i = 0; i < 200; i++) {
    const x = Math.random() * W
    const y = Math.random() * H
    const r = Math.random() * 1.2 + 0.3
    const alpha = Math.random() * 0.5 + 0.1
    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(200, 200, 230, ${alpha})`
    ctx.fill()
  }

  // 中心光晕
  const glow = ctx.createRadialGradient(W / 2, H * 0.32, 0, W / 2, H * 0.32, 400)
  glow.addColorStop(0, 'rgba(140, 120, 255, 0.06)')
  glow.addColorStop(1, 'transparent')
  ctx.fillStyle = glow
  ctx.fillRect(0, 0, W, H)

  // 顶部标签
  ctx.textAlign = 'center'
  ctx.font = '28px "Noto Serif SC", serif'
  ctx.fillStyle = 'rgba(160, 150, 200, 0.6)'
  ctx.letterSpacing = '8px'
  ctx.fillText('世 界 宣 言', W / 2, 160)

  // 分隔线
  ctx.strokeStyle = 'rgba(140, 120, 255, 0.2)'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(W / 2 - 120, 195)
  ctx.lineTo(W / 2 + 120, 195)
  ctx.stroke()

  // 世界名（概念）
  ctx.font = '72px "Ma Shan Zheng", "Noto Serif SC", serif'
  ctx.fillStyle = '#f0f0f8'
  ctx.shadowColor = 'rgba(140, 120, 255, 0.3)'
  ctx.shadowBlur = 30
  ctx.fillText(concept.value.trim(), W / 2, 320)
  ctx.shadowBlur = 0

  // 天意节点 — 核心宣言
  const tianyiNode = currentNodes.find(n => n.type === 'tianyi')
  if (tianyiNode) {
    ctx.font = '30px "Noto Serif SC", serif'
    ctx.fillStyle = '#ffd700'
    ctx.fillText(`天意 · ${tianyiNode.name}`, W / 2, 440)

    if (tianyiNode.summary) {
      ctx.font = '26px "Noto Serif SC", serif'
      ctx.fillStyle = 'rgba(240, 240, 248, 0.7)'
      wrapText(ctx, tianyiNode.summary, W / 2, 500, W - 160, 38)
    }
  }

  // 节点列表
  const colorMap: Record<string, string> = {
    character: '#e8a838', tianyi: '#ffd700', spacetime: '#4a9eff',
    military: '#e05545', social: '#45c48a', item: '#38c8c8', creature: '#a878e8',
  }
  const typeLabels: Record<string, string> = {
    character: '角色', spacetime: '时空', military: '军事',
    social: '社会', item: '器物', creature: '生灵',
  }

  const listNodes = currentNodes.filter(n => n.type !== 'tianyi').slice(0, 10)
  let listY = tianyiNode ? 640 : 480

  ctx.textAlign = 'left'
  for (const node of listNodes) {
    const color = colorMap[node.type] || '#888'
    // 色点
    ctx.beginPath()
    ctx.arc(140, listY - 6, 6, 0, Math.PI * 2)
    ctx.fillStyle = color
    ctx.fill()
    // 类型标签
    ctx.font = '22px "Noto Serif SC", serif'
    ctx.fillStyle = 'rgba(160, 160, 190, 0.6)'
    ctx.fillText(typeLabels[node.type] || node.type, 165, listY)
    // 名称
    ctx.font = '30px "Noto Serif SC", serif'
    ctx.fillStyle = '#e8e8f0'
    ctx.fillText(node.name, 280, listY)
    // 摘要（截断）
    if (node.summary) {
      ctx.font = '22px "Noto Serif SC", serif'
      ctx.fillStyle = 'rgba(200, 200, 220, 0.5)'
      const summary = node.summary.length > 28 ? node.summary.slice(0, 28) + '…' : node.summary
      ctx.fillText(summary, 280, listY + 36)
    }
    listY += node.summary ? 90 : 60
  }

  // 底部水印
  ctx.textAlign = 'center'
  ctx.font = '36px "Ma Shan Zheng", "Noto Serif SC", serif'
  ctx.fillStyle = 'rgba(200, 190, 230, 0.4)'
  ctx.fillText('新三国 · 星图', W / 2, H - 120)

  ctx.font = '20px "Noto Serif SC", serif'
  ctx.fillStyle = 'rgba(140, 140, 170, 0.3)'
  ctx.fillText('以机制重构经典 · 用假说点燃想象', W / 2, H - 75)

  cardDataUrl.value = canvas.toDataURL('image/png')
  showCard.value = true
}

function wrapText(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, maxWidth: number, lineHeight: number) {
  let line = ''
  let curY = y
  for (const char of text) {
    const testLine = line + char
    if (ctx.measureText(testLine).width > maxWidth && line) {
      ctx.fillText(line, x, curY)
      line = char
      curY += lineHeight
    } else {
      line = testLine
    }
  }
  if (line) ctx.fillText(line, x, curY)
}

onBeforeUnmount(() => {
  graphInstance?._destructor?.()
})
</script>

<style scoped>
.create {
  width: 100%;
  height: 100vh;
  position: relative;
  overflow: hidden;
  background: #030306;
}

.back-btn {
  position: fixed;
  top: 24px;
  left: 24px;
  z-index: 100;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 1px solid rgba(120, 120, 160, 0.2);
  background: rgba(3, 3, 6, 0.6);
  color: #6a6a80;
  font-size: 18px;
  cursor: pointer;
  backdrop-filter: blur(8px);
  transition: all 0.3s;
}
.back-btn:hover { border-color: rgba(160, 140, 255, 0.5); color: #c8b8ff; }

/* 输入阶段 */
.input-phase {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  padding: 24px;
}

/* 星云核心 */
.nebula-core {
  position: relative;
  width: 140px;
  height: 140px;
  margin-bottom: 40px;
}
.nebula-glow {
  position: absolute;
  inset: 20px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(140, 120, 255, 0.35) 0%, rgba(80, 60, 180, 0.1) 50%, transparent 70%);
  animation: core-breathe 5s ease-in-out infinite;
}
.nebula-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 1px solid rgba(140, 120, 255, 0.15);
  animation: ring-spin 12s linear infinite;
}
.nebula-ring::after {
  content: '';
  position: absolute;
  top: -2px;
  left: 50%;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: rgba(180, 160, 255, 0.8);
  box-shadow: 0 0 8px rgba(140, 120, 255, 0.6);
}
.ring-2 {
  inset: 15px;
  border-color: rgba(100, 80, 200, 0.1);
  animation-duration: 8s;
  animation-direction: reverse;
}
@keyframes core-breathe {
  0%, 100% { transform: scale(1); opacity: 0.7; }
  50% { transform: scale(1.15); opacity: 1; }
}
@keyframes ring-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.create-title {
  font-family: 'Ma Shan Zheng', var(--font-display);
  font-size: clamp(2rem, 5vw, 3rem);
  font-weight: 400;
  color: #f0f0f8;
  letter-spacing: 0.3em;
  text-shadow: 0 0 40px rgba(140, 120, 255, 0.2);
}

.create-sub {
  margin-top: 14px;
  color: #5a5a70;
  font-size: 0.85rem;
  letter-spacing: 0.08em;
}

/* 输入区域 */
.input-ritual {
  position: relative;
  margin-top: 48px;
  width: min(440px, 85vw);
}
.concept-input {
  width: 100%;
  padding: 16px 24px;
  background: transparent;
  border: none;
  border-bottom: 1px solid rgba(120, 120, 160, 0.2);
  color: #e8e8f0;
  font-size: 1.05rem;
  font-family: 'Noto Serif SC', serif;
  letter-spacing: 0.03em;
  line-height: 1.8;
  text-align: center;
  resize: none;
  overflow: hidden;
  transition: border-color 0.4s;
}
.concept-input:focus {
  outline: none;
  border-color: rgba(160, 140, 255, 0.5);
}
.concept-input::placeholder { color: #3a3a50; }
.input-glow {
  position: absolute;
  bottom: -1px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(160, 140, 255, 0.6), transparent);
  transition: width 0.5s ease;
}
.concept-input:focus ~ .input-glow {
  width: 100%;
}

/* 凝聚按钮 */
.forge-btn {
  position: relative;
  margin-top: 40px;
  padding: 14px 48px;
  background: transparent;
  border: 1px solid rgba(120, 120, 160, 0.15);
  color: #4a4a60;
  font-family: 'Ma Shan Zheng', var(--font-display);
  font-size: 1.2rem;
  letter-spacing: 0.4em;
  cursor: not-allowed;
  transition: all 0.5s ease;
  overflow: hidden;
}
.forge-btn.ready {
  border-color: rgba(160, 140, 255, 0.4);
  color: #c8b8ff;
  cursor: pointer;
  text-shadow: 0 0 20px rgba(140, 120, 255, 0.3);
}
.forge-btn.ready:hover {
  border-color: rgba(160, 140, 255, 0.7);
  box-shadow: 0 0 40px rgba(140, 120, 255, 0.1), inset 0 0 30px rgba(140, 120, 255, 0.05);
}
.forge-pulse {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at center, rgba(160, 140, 255, 0.1) 0%, transparent 70%);
  opacity: 0;
  animation: forge-breathe 3s ease-in-out infinite;
}
.forge-btn.ready .forge-pulse { opacity: 1; }
@keyframes forge-breathe {
  0%, 100% { transform: scale(0.8); opacity: 0; }
  50% { transform: scale(1.2); opacity: 1; }
}

/* 已验证灵感 */
.verified-hints {
  margin-top: 48px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 10px;
  max-width: 480px;
}
.hint-label {
  font-size: 0.7rem;
  color: #3a3a50;
  letter-spacing: 0.15em;
  margin-right: 4px;
}
.hint-chip {
  padding: 6px 14px;
  background: transparent;
  border: 1px solid rgba(120, 120, 160, 0.12);
  border-radius: 14px;
  color: #5a5a70;
  font-size: 0.78rem;
  font-family: 'Noto Serif SC', serif;
  cursor: pointer;
  transition: all 0.3s;
  letter-spacing: 0.05em;
}
.hint-chip:hover {
  border-color: rgba(160, 140, 255, 0.4);
  color: #b8a8e8;
  background: rgba(140, 120, 255, 0.05);
}

/* 生成阶段 */
.grow-phase {
  width: 100%;
  height: 100%;
  position: relative;
}
.graph-container {
  width: 100%;
  height: 100%;
}
.grow-status {
  position: fixed;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
}
.grow-text {
  padding: 10px 24px;
  background: rgba(3, 3, 6, 0.8);
  border: 1px solid rgba(120, 120, 160, 0.15);
  border-radius: 20px;
  color: #6a6a80;
  font-size: 0.85rem;
  letter-spacing: 0.1em;
  backdrop-filter: blur(8px);
}
.grow-done {
  position: fixed;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  display: flex;
  gap: 16px;
  align-items: center;
}
.error-msg {
  color: #e05545;
  font-size: 0.8rem;
  margin: 0;
}
.share-btn {
  padding: 12px 32px;
  background: rgba(232, 168, 56, 0.08);
  border: 1px solid rgba(232, 168, 56, 0.3);
  color: #e8a838;
  font-family: 'Ma Shan Zheng', var(--font-display);
  font-size: 1rem;
  cursor: pointer;
  letter-spacing: 0.2em;
  transition: all 0.3s;
}
.share-btn:hover {
  background: rgba(232, 168, 56, 0.15);
  box-shadow: 0 0 30px rgba(232, 168, 56, 0.1);
}
.back-star-btn {
  padding: 12px 32px;
  background: transparent;
  border: 1px solid rgba(120, 120, 160, 0.2);
  color: #6a6a80;
  font-family: 'Ma Shan Zheng', var(--font-display);
  font-size: 1rem;
  cursor: pointer;
  letter-spacing: 0.2em;
  transition: all 0.3s;
}
.back-star-btn:hover {
  border-color: rgba(160, 140, 255, 0.4);
  color: #c8b8ff;
}

/* 世界宣言浮层 */
.card-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(8px);
}
.card-preview {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  max-height: 90vh;
}
.card-img {
  max-height: 72vh;
  width: auto;
  border: 1px solid rgba(140, 120, 255, 0.2);
  box-shadow: 0 0 60px rgba(100, 80, 200, 0.15);
}
.card-actions {
  display: flex;
  gap: 16px;
}
.card-dl-btn {
  padding: 12px 36px;
  background: rgba(160, 140, 255, 0.12);
  border: 1px solid rgba(160, 140, 255, 0.4);
  color: #c8b8ff;
  font-family: 'Ma Shan Zheng', var(--font-display);
  font-size: 1rem;
  letter-spacing: 0.2em;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.3s;
}
.card-dl-btn:hover {
  background: rgba(160, 140, 255, 0.2);
  box-shadow: 0 0 30px rgba(140, 120, 255, 0.15);
}
.card-close-btn {
  padding: 12px 36px;
  background: transparent;
  border: 1px solid rgba(120, 120, 160, 0.2);
  color: #6a6a80;
  font-family: 'Ma Shan Zheng', var(--font-display);
  font-size: 1rem;
  letter-spacing: 0.2em;
  cursor: pointer;
  transition: all 0.3s;
}
.card-close-btn:hover {
  border-color: rgba(160, 140, 255, 0.3);
  color: #a0a0c0;
}
.card-fade-enter-active, .card-fade-leave-active {
  transition: opacity 0.4s ease;
}
.card-fade-enter-from, .card-fade-leave-to {
  opacity: 0;
}

@media (max-width: 480px) {
  .nebula-core { width: 100px; height: 100px; margin-bottom: 28px; }
  .verified-hints { margin-top: 32px; gap: 8px; }
  .hint-chip { padding: 5px 10px; font-size: 0.72rem; }
  .card-img { max-height: 60vh; max-width: 90vw; }
  .card-actions { flex-direction: column; gap: 10px; }
  .grow-done { flex-direction: column; gap: 10px; }
}
</style>
