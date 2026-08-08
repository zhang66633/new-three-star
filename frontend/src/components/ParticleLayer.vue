<template>
  <canvas
    ref="canvasRef"
    class="particle-canvas"
    aria-hidden="true"
  />
</template>

<script setup lang="ts">
/**
 * ParticleLayer — 纯 Canvas 粒子氛围层
 * 根据 atmo 标签自动切换密度/色调/运动模式。
 * 雨丝 · 火星 · 飞尘 · 雪 · 雾 · 星 · 叶 · 沫 · 烬 · 夜萤
 */
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'

const props = withDefaults(defineProps<{
  atmoTag?: string
}>(), {
  atmoTag: '雨夜沉静',
})

// ── 粒子配置表 ──
interface ParticleConfig {
  type: string
  color: string      // CSS color
  count: number      // 最大粒子数
  speed: number      // 基础速度系数
  size: number       // 基础尺寸 (px)
  opacity: number    // 基础透明度
  direction?: 'down' | 'up' | 'horizontal' | 'twinkle' | 'drift-sway'
}

const CONFIGS: Record<string, ParticleConfig> = {
  '雨夜沉静': { type: 'rain',   color: '#7eb8da', count: 140, speed: 2.8, size: 1.2, opacity: 0.35, direction: 'down' },
  '荒野苍茫': { type: 'dust',   color: '#b8976e', count: 55,  speed: 0.35, size: 2.2, opacity: 0.22, direction: 'horizontal' },
  '战火远方': { type: 'fire',   color: '#e8734a', count: 90,  speed: 0.8,  size: 2.8, opacity: 0.28, direction: 'up' },
  '洛阳暗巷': { type: 'night',  color: '#c8a84e', count: 35,  speed: 0.25, size: 1.6, opacity: 0.18, direction: 'drift-sway' },
  '水墨山岚': { type: 'mist',   color: '#9aacb5', count: 45,  speed: 0.3,  size: 3.5, opacity: 0.12, direction: 'horizontal' },
  '破晓行军': { type: 'dawn',   color: '#c8a84e', count: 55,  speed: 0.45, size: 1.6, opacity: 0.22, direction: 'drift-sway' },
  '竹林清幽': { type: 'leaf',   color: '#7a9a6e', count: 30,  speed: 0.55, size: 2.4, opacity: 0.22, direction: 'drift-sway' },
  '黄河怒涛': { type: 'spray',  color: '#c8a060', count: 110, speed: 1.6,  size: 1.8, opacity: 0.28, direction: 'horizontal' },
  '帐中暖光': { type: 'ember',  color: '#e8a838', count: 50,  speed: 0.5,  size: 2.2, opacity: 0.24, direction: 'up' },
  '雪夜孤城': { type: 'snow',   color: '#d8e8f0', count: 90,  speed: 0.55, size: 2.0, opacity: 0.22, direction: 'down' },
  '星空原野': { type: 'star',   color: '#c8d8e8', count: 70,  speed: 0,    size: 1.4, opacity: 0.28, direction: 'twinkle' },
  '血色残阳': { type: 'ash',    color: '#a04030', count: 55,  speed: 0.3,  size: 2.0, opacity: 0.2,  direction: 'down' },
}

// ── 粒子 ──
interface Particle {
  x: number; y: number
  vx: number; vy: number
  life: number; maxLife: number
  size: number; opacity: number
  color: string
}

const canvasRef = ref<HTMLCanvasElement | null>(null)
let ctx: CanvasRenderingContext2D | null = null
let particles: Particle[] = []
let animId = 0
let W = 0, H = 0
let currentConfig: ParticleConfig = CONFIGS['雨夜沉静']

// ── 配置切换 crossfade ──
function applyConfig(cfg: ParticleConfig) {
  currentConfig = cfg
  // 不立即清空粒子——旧粒子自然衰减，新粒子逐步填充
}

function spawnParticle(): Particle {
  const c = currentConfig
  const maxLife = c.direction === 'twinkle'
    ? 180 + Math.random() * 240
    : 120 + Math.random() * 200
  return {
    x: Math.random() * W,
    y: c.direction === 'up' ? H + 10 : -10,
    vx: 0, vy: 0,
    life: Math.random() * maxLife,
    maxLife,
    size: c.size * (0.5 + Math.random()),
    opacity: c.opacity * (0.4 + Math.random() * 0.6),
    color: c.color,
  }
}

function resetVelocity(p: Particle) {
  const c = currentConfig
  const base = c.speed * (0.5 + Math.random() * 0.5)
  switch (c.direction) {
    case 'down':
      p.vx = (Math.random() - 0.5) * base * 0.3
      p.vy = base * (2 + Math.random() * 3)
      break
    case 'up':
      p.vx = (Math.random() - 0.5) * base * 1.2
      p.vy = -base * (1 + Math.random() * 2)
      break
    case 'horizontal':
      p.vx = (Math.random() > 0.5 ? 1 : -1) * base * (0.5 + Math.random())
      p.vy = (Math.random() - 0.5) * base * 0.4
      break
    case 'drift-sway':
      p.vx = (Math.random() - 0.5) * base * 1.5
      p.vy = (Math.random() - 0.5) * base * 0.8
      break
    case 'twinkle':
      p.vx = 0; p.vy = 0
      break
  }
}

// ── 渲染循环 ──
function tick() {
  if (!ctx) return
  ctx.clearRect(0, 0, W, H)

  // 维持粒子池大小
  const target = currentConfig.count
  while (particles.length < target) {
    const p = spawnParticle()
    resetVelocity(p)
    particles.push(p)
  }

  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i]
    p.life--

    if (p.life <= 0 || p.y > H + 40 || p.y < -40 || p.x < -40 || p.x > W + 40) {
      // 置换新粒子（保持池大小）
      const fresh = spawnParticle()
      resetVelocity(fresh)
      particles[i] = fresh
      continue
    }

    // 运动
    if (currentConfig.direction === 'twinkle') {
      // 静止闪烁
    } else {
      p.x += p.vx
      p.y += p.vy
      // 微扰动
      p.vx += (Math.random() - 0.5) * 0.04
      p.vy += (Math.random() - 0.5) * 0.02
    }

    // 渲染
    const lifeRatio = Math.min(1, p.life / p.maxLife)
    const alpha = p.opacity * (currentConfig.direction === 'twinkle'
      ? 0.3 + 0.7 * Math.abs(Math.sin(p.life * 0.03))
      : lifeRatio < 0.15 ? lifeRatio / 0.15 : lifeRatio > 0.8 ? (1 - lifeRatio) / 0.2 : 1)

    ctx.globalAlpha = alpha
    ctx.fillStyle = p.color

    if (currentConfig.type === 'rain') {
      // 雨丝：细长竖线
      ctx.fillRect(p.x, p.y, 1, p.size * 6)
    } else if (currentConfig.type === 'star') {
      // 星点：圆 + 微光晕
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
      ctx.fill()
    } else {
      // 通用圆点
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.size * 0.7, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  ctx.globalAlpha = 1
  // 剔除超出上限的粒子（切换配置时 count 变小）
  while (particles.length > target + 20) particles.pop()

  animId = requestAnimationFrame(tick)
}

// ── 尺寸响应 ──
function resize() {
  const c = canvasRef.value
  if (!c) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  W = window.innerWidth
  H = window.innerHeight
  c.width = W * dpr
  c.height = H * dpr
  c.style.width = W + 'px'
  c.style.height = H + 'px'
  if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
}

// ── 生命周期 ──
onMounted(() => {
  const c = canvasRef.value
  if (!c) return
  ctx = c.getContext('2d')
  resize()
  window.addEventListener('resize', resize)
  applyConfig(CONFIGS[props.atmoTag] || CONFIGS['雨夜沉静'])
  tick()
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animId)
  window.removeEventListener('resize', resize)
})

// ── atmo 切换 ──
watch(() => props.atmoTag, (tag) => {
  const cfg = CONFIGS[tag] || CONFIGS['雨夜沉静']
  applyConfig(cfg)
})
</script>

<style scoped>
.particle-canvas {
  position: fixed;
  inset: 0;
  z-index: 1;         /* 在 AtmoBackground(z=0) 之上，内容(z=2+) 之下 */
  pointer-events: none;
}
</style>
