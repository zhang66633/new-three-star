<template>
  <div class="explore">
    <button class="back-btn" @click="goBack">←</button>

    <!-- 加载状态 -->
    <div v-if="pageLoading" class="page-status">
      <div class="status-spinner"></div>
      <p>星图凝聚中……</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="pageError" class="page-status">
      <p class="error-text">世界线断裂，无法加载此世界</p>
      <button class="retry-btn" @click="goBack">返回星图</button>
    </div>

    <div ref="graphRef" class="graph-container" v-show="!pageLoading && !pageError"></div>

    <!-- 右侧面板 -->
    <transition name="panel-slide">
      <div v-if="selectedNode" class="detail-panel">
        <button class="panel-close" @click="selectedNode = null">✕</button>
        <div class="panel-header">
          <span class="node-type-badge" :style="{ color: selectedNode.color, borderColor: selectedNode.color + '40' }">
            {{ typeLabel(selectedNode.type) }}
          </span>
          <h2 class="node-name">{{ selectedNode.name }}</h2>
        </div>
        <p class="node-summary">{{ selectedNode.summary }}</p>

        <div v-if="deepDiveContent" class="deep-dive">
          <div class="deep-dive-content" :class="{ streaming: isDeepDiving }" v-html="renderMd(deepDiveContent)"></div>
        </div>

        <button
          v-if="!deepDiveContent && !isDeepDiving"
          class="deep-dive-btn"
          @click="startDeepDive"
        >
          深度解读
        </button>
        <div v-if="isDeepDiving && !deepDiveContent" class="loading-hint">天意推演中……</div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, inject } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ForceGraph3D from '3d-force-graph'
const ForceGraph3DAny = ForceGraph3D as any
import type { GraphNode } from '../types'

const route = useRoute()
const router = useRouter()
const graphRef = ref<HTMLElement>()
const selectedNode = ref<GraphNode | null>(null)
const deepDiveContent = ref('')
const isDeepDiving = ref(false)
const pageLoading = ref(true)
const pageError = ref(false)
const playGuanyu = inject<() => void>('playGuanyu', () => {})

let graphInstance: any = null
const API_BASE = import.meta.env.VITE_API_BASE || ''

function goBack() {
  router.push('/')
}

function typeLabel(type: string) {
  const map: Record<string, string> = {
    character: '角色', tianyi: '天意', spacetime: '时空',
    military: '军事', social: '社会', item: '物品', creature: '生物',
  }
  return map[type] || '机制'
}

function renderMd(text: string) {
  return text
    .split('\n')
    .map(l => {
      if (l.startsWith('## ')) return `<h3>${l.slice(3)}</h3>`
      if (l.startsWith('# ')) return `<h3>${l.slice(2)}</h3>`
      if (l.trim() === '') return '<br/>'
      return `<p>${l}</p>`
    })
    .join('')
}

async function startDeepDive() {
  if (!selectedNode.value) return
  isDeepDiving.value = true
  deepDiveContent.value = ''

  const frameworkId = route.params.id as string
  try {
    const resp = await fetch(`${API_BASE}/api/worldview/node-dive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        framework: frameworkId,
        node_name: selectedNode.value.name,
        node_type: selectedNode.value.type,
        node_summary: selectedNode.value.summary,
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
          if (msg.type === 'content') deepDiveContent.value += msg.text
          if (msg.type === 'done') { isDeepDiving.value = false; playGuanyu() }
        } catch {}
      }
    }
  } catch {
    isDeepDiving.value = false
  }
}

onMounted(async () => {
  const frameworkId = route.params.id as string
  try {
    const resp = await fetch(`${API_BASE}/api/graph/${frameworkId}`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    initGraph(data)
    pageLoading.value = false
  } catch (e) {
    console.error('Failed to load graph data', e)
    pageLoading.value = false
    pageError.value = true
  }
})

onBeforeUnmount(() => {
  graphInstance?._destructor?.()
})

function initGraph(data: { nodes: any[]; links: any[] }) {
  if (!graphRef.value) return

  const colorMap: Record<string, string> = {
    character: '#e8a838', tianyi: '#ffd700', spacetime: '#4a9eff',
    military: '#e05545', social: '#45c48a', item: '#38c8c8', creature: '#a878e8',
  }

  graphInstance = ForceGraph3DAny()(graphRef.value)
    .graphData(data)
    .backgroundColor('#050508')
    .showNavInfo(false)
    .enableNodeDrag(true)
    .autoRotate(true)
    .autoRotateSpeed(0.15)
    .nodeRelSize(4)
    .nodeVal((n: any) => n.type === 'character' ? 14 : 7)
    .nodeColor((n: any) => colorMap[n.type] || '#888')
    .nodeOpacity(0.85)
    .linkColor(() => 'rgba(160, 160, 200, 0.12)')
    .linkWidth(0.8)
    .linkDirectionalParticles(2)
    .linkDirectionalParticleWidth(1.5)
    .linkDirectionalParticleColor(() => 'rgba(232, 168, 56, 0.3)')
    .nodeLabel((n: any) => `<div style="font-family:'Noto Serif SC',serif;padding:6px 10px;background:rgba(5,5,8,0.92);border:1px solid ${colorMap[n.type]}40;border-radius:4px;color:#f0f0f8;font-size:13px;">${n.name}</div>`)
    .onNodeClick((node: any) => {
      selectedNode.value = node as GraphNode
      deepDiveContent.value = ''
      isDeepDiving.value = false
      if (node.type === 'tianyi') playGuanyu()
      // 镜头聚焦
      const distance = 80
      const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z)
      graphInstance.cameraPosition(
        { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
        node, 1000
      )
    })
    .onBackgroundClick(() => { selectedNode.value = null })

  const resize = () => {
    if (graphInstance && graphRef.value) {
      graphInstance.width(graphRef.value.clientWidth)
      graphInstance.height(graphRef.value.clientHeight)
    }
  }
  window.addEventListener('resize', resize)
  resize()
}
</script>

<style scoped>
.explore {
  width: 100%;
  height: 100vh;
  position: relative;
  overflow: hidden;
}

.graph-container {
  width: 100%;
  height: 100%;
}

.page-status {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #8888aa;
  font-size: 0.95rem;
  letter-spacing: 0.1em;
}
.status-spinner {
  width: 32px;
  height: 32px;
  border: 2px solid rgba(136, 136, 170, 0.2);
  border-top-color: #8888aa;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.error-text { color: #e05545; }
.retry-btn {
  background: transparent;
  border: 1px solid #555;
  color: #aaa;
  padding: 8px 24px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.2s;
}
.retry-btn:hover { border-color: #aaa; color: #fff; }

.back-btn {
  position: fixed;
  top: 24px;
  left: 24px;
  z-index: 100;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 1px solid var(--panel-border);
  background: var(--panel-bg);
  color: var(--text-muted);
  font-size: 18px;
  cursor: pointer;
  backdrop-filter: blur(8px);
  transition: all 0.3s;
}
.back-btn:hover {
  border-color: var(--accent-gold);
  color: var(--accent-gold);
}

/* 右侧面板 */
.detail-panel {
  position: fixed;
  top: 0;
  right: 0;
  width: min(380px, 85vw);
  height: 100vh;
  background: var(--panel-bg);
  border-left: 1px solid var(--panel-border);
  backdrop-filter: blur(20px);
  padding: 32px 24px;
  overflow-y: auto;
  z-index: 50;
}

.panel-slide-enter-active, .panel-slide-leave-active {
  transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.panel-slide-enter-from, .panel-slide-leave-to {
  transform: translateX(100%);
}

.panel-close {
  position: absolute;
  top: 16px;
  right: 16px;
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 16px;
  cursor: pointer;
}
.panel-close:hover { color: var(--text-bright); }

.node-type-badge {
  font-size: 0.7rem;
  padding: 2px 8px;
  border: 1px solid;
  border-radius: 3px;
  letter-spacing: 0.1em;
}

.node-name {
  font-family: var(--font-display);
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--text-bright);
  margin-top: 12px;
}

.node-summary {
  margin-top: 16px;
  font-size: 0.9rem;
  line-height: 1.9;
  color: var(--text-primary);
}

.deep-dive-btn {
  margin-top: 24px;
  padding: 10px 24px;
  background: rgba(232, 168, 56, 0.08);
  border: 1px solid rgba(232, 168, 56, 0.3);
  border-radius: 6px;
  color: var(--accent-gold);
  font-family: var(--font-display);
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.3s;
  letter-spacing: 0.1em;
}
.deep-dive-btn:hover {
  background: rgba(232, 168, 56, 0.15);
  box-shadow: 0 0 20px rgba(232, 168, 56, 0.1);
}

.loading-hint {
  margin-top: 24px;
  color: var(--text-muted);
  font-size: 0.85rem;
  letter-spacing: 0.2em;
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

.deep-dive {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--panel-border);
}

.deep-dive-content {
  font-size: 0.88rem;
  line-height: 2;
  color: var(--text-primary);
}
.deep-dive-content :deep(h3) {
  color: var(--accent-gold);
  font-size: 1rem;
  margin: 16px 0 8px;
  padding-left: 10px;
  border-left: 2px solid var(--accent-cinnabar);
}
.deep-dive-content :deep(p) {
  margin-bottom: 6px;
  text-indent: 2em;
}
.deep-dive-content.streaming::after {
  content: '▌';
  color: var(--accent-gold);
  animation: blink 1s step-end infinite;
}
@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
</style>
