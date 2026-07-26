<template>
  <canvas ref="canvasRef" class="mobile-starmap" @touchstart="onTouch" @click="onClick"></canvas>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps<{
  worlds: { id: string; name: string; tagline: string; color: string }[]
}>()

const emit = defineEmits<{
  (e: 'navigate', id: string): void
}>()

const canvasRef = ref<HTMLCanvasElement>()
let animId: number | null = null
let dpr = 1

interface StarNode {
  id: string
  name: string
  color: string
  x: number
  y: number
  radius: number
  phase: number
}

let nodes: StarNode[] = []
let stars: { x: number; y: number; r: number; a: number }[] = []

function layout(w: number, h: number) {
  const cx = w / 2
  const cy = h / 2
  const allWorlds = [...props.worlds, { id: 'create', name: '创造新世界', tagline: '', color: '#aabbff' }]
  const count = allWorlds.length
  const radiusX = Math.min(w * 0.36, 260)
  const radiusY = Math.min(h * 0.34, 300)

  nodes = allWorlds.map((wd, i) => {
    const angle = (i / count) * Math.PI * 2 - Math.PI / 2
    return {
      id: wd.id,
      name: wd.name,
      color: wd.color,
      x: cx + Math.cos(angle) * radiusX,
      y: cy + Math.sin(angle) * radiusY,
      radius: wd.id === 'create' ? 14 : 18,
      phase: Math.random() * Math.PI * 2,
    }
  })

  stars = Array.from({ length: 120 }, () => ({
    x: Math.random() * w,
    y: Math.random() * h,
    r: Math.random() * 1.2 + 0.3,
    a: Math.random() * 0.5 + 0.1,
  }))
}

function draw(t: number) {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')!
  const w = canvas.width / dpr
  const h = canvas.height / dpr

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, w, h)

  // 背景
  ctx.fillStyle = '#030306'
  ctx.fillRect(0, 0, w, h)

  // 星点
  for (const s of stars) {
    const flicker = s.a + Math.sin(t * 0.001 + s.x) * 0.1
    ctx.beginPath()
    ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(200, 200, 230, ${Math.max(0, flicker)})`
    ctx.fill()
  }

  // 连线（星座感）
  ctx.strokeStyle = 'rgba(120, 130, 180, 0.06)'
  ctx.lineWidth = 0.5
  for (let i = 0; i < nodes.length; i++) {
    const next = nodes[(i + 1) % nodes.length]
    ctx.beginPath()
    ctx.moveTo(nodes[i].x, nodes[i].y)
    ctx.lineTo(next.x, next.y)
    ctx.stroke()
  }

  // 节点
  for (const node of nodes) {
    const pulse = 1 + Math.sin(t * 0.002 + node.phase) * 0.12
    const r = node.radius * pulse

    // 外发光
    const glow = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, r * 3)
    glow.addColorStop(0, node.color + '30')
    glow.addColorStop(1, 'transparent')
    ctx.fillStyle = glow
    ctx.fillRect(node.x - r * 3, node.y - r * 3, r * 6, r * 6)

    // 核心
    const core = ctx.createRadialGradient(node.x - r * 0.3, node.y - r * 0.3, 0, node.x, node.y, r)
    core.addColorStop(0, node.color)
    core.addColorStop(0.7, node.color + 'aa')
    core.addColorStop(1, node.color + '44')
    ctx.beginPath()
    ctx.arc(node.x, node.y, r, 0, Math.PI * 2)
    ctx.fillStyle = core
    ctx.fill()

    // 名称
    ctx.font = `${node.id === 'create' ? 13 : 14}px "Noto Serif SC", serif`
    ctx.textAlign = 'center'
    ctx.fillStyle = 'rgba(240, 240, 248, 0.85)'
    ctx.fillText(node.name, node.x, node.y + r + 20)
  }
}

function animate(t: number) {
  draw(t)
  animId = requestAnimationFrame(animate)
}

function hitTest(clientX: number, clientY: number): string | null {
  const canvas = canvasRef.value
  if (!canvas) return null
  const rect = canvas.getBoundingClientRect()
  const x = clientX - rect.left
  const y = clientY - rect.top

  for (const node of nodes) {
    const dx = x - node.x
    const dy = y - node.y
    if (dx * dx + dy * dy < (node.radius + 16) * (node.radius + 16)) {
      return node.id
    }
  }
  return null
}

function onTouch(e: TouchEvent) {
  const touch = e.touches[0]
  if (!touch) return
  const id = hitTest(touch.clientX, touch.clientY)
  if (id) {
    e.preventDefault()
    emit('navigate', id)
  }
}

function onClick(e: MouseEvent) {
  const id = hitTest(e.clientX, e.clientY)
  if (id) emit('navigate', id)
}

function resize() {
  const canvas = canvasRef.value
  if (!canvas) return
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  const w = canvas.clientWidth
  const h = canvas.clientHeight
  canvas.width = w * dpr
  canvas.height = h * dpr
  layout(w, h)
}

onMounted(() => {
  resize()
  window.addEventListener('resize', resize)
  animId = requestAnimationFrame(animate)
})

onBeforeUnmount(() => {
  if (animId) cancelAnimationFrame(animId)
  window.removeEventListener('resize', resize)
})
</script>

<style scoped>
.mobile-starmap {
  width: 100%;
  height: 100%;
  display: block;
  touch-action: manipulation;
}
</style>
