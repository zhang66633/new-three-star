<template>
  <div class="narrative" :class="{ glitching: isGlitching }">
    <!-- 故障艺术覆盖层 -->
    <div class="scanlines"></div>
    <div class="vignette"></div>
    <div class="noise-layer">
      <div
        v-for="(nb, i) in noiseBlocks"
        :key="i"
        class="noise-block"
        :style="{ left: nb.x + '%', top: nb.y + '%', width: nb.w + 'px', height: nb.h + 'px', background: nb.color }"
      ></div>
    </div>

    <button class="back-btn" @click="goBack">←</button>

    <!-- 叙事日志 -->
    <div class="log-container" ref="logRef">
      <div v-for="(block, i) in logBlocks" :key="i" class="log-block" :class="block.type">
        <span v-if="block.type === 'sys'" class="prefix">[SYS]</span>
        <span v-else-if="block.type === 'err'" class="prefix">[ERR]</span>
        <span v-else-if="block.type === 'music'" class="prefix music-note">♪</span>
        <span v-else-if="block.type === 'dialogue'" class="prefix">[{{ block.speaker }}]</span>
        <span class="log-text" v-html="block.html"></span>
      </div>
      <div v-if="isStreaming" class="log-block streaming">
        <span class="cursor-blink">▌</span>
      </div>
    </div>

    <!-- 选项区 -->
    <div v-if="options.length > 0 && !isStreaming" class="options-area">
      <button
        v-for="(opt, i) in options"
        :key="i"
        class="option-btn"
        @click="chooseOption(opt)"
      >
        <span class="opt-num">{{ i + 1 }}</span> {{ opt }}
      </button>
      <div class="free-input-row">
        <input
          v-model="freeInput"
          class="free-input"
          placeholder="或者，你想做点别的……"
          @keydown.enter="submitFree"
        />
        <button class="submit-btn" @click="submitFree" :disabled="!freeInput.trim()">→</button>
      </div>
    </div>

    <!-- 初始加载 -->
    <div v-if="pageLoading" class="init-overlay">
      <p class="init-text">{{ initText }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onBeforeUnmount, inject } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE || ''
const playGuanyu = inject<() => void>('playGuanyu', () => {})

const logRef = ref<HTMLElement>()
const logBlocks = ref<{ type: string; speaker?: string; html: string }[]>([])
const options = ref<string[]>([])
const isStreaming = ref(false)
const pageLoading = ref(true)
const initText = ref('正在连接世界意志……')
const freeInput = ref('')
const isGlitching = ref(false)
const musicPlayedCount = ref(0)

// 故障噪点块
interface NoiseBlock { x: number; y: number; w: number; h: number; color: string }
const noiseBlocks = ref<NoiseBlock[]>([])

function spawnNoise(count: number) {
  const colors = ['rgba(0,255,65,0.15)', 'rgba(255,0,170,0.12)', 'rgba(0,204,255,0.12)', 'rgba(255,255,255,0.08)']
  const blocks: NoiseBlock[] = []
  for (let i = 0; i < count; i++) {
    blocks.push({
      x: Math.random() * 100,
      y: Math.random() * 100,
      w: 20 + Math.random() * 120,
      h: 2 + Math.random() * 8,
      color: colors[Math.floor(Math.random() * colors.length)],
    })
  }
  noiseBlocks.value = blocks
  // 短暂显示后清除
  setTimeout(() => { noiseBlocks.value = [] }, 120)
}

const history: { role: string; content: string }[] = []
let glitchTimer: number | null = null
let ambientNoiseTimer: number | null = null

function goBack() {
  router.push('/')
}

function scrollToBottom() {
  nextTick(() => {
    if (logRef.value) {
      logRef.value.scrollTop = logRef.value.scrollHeight
    }
  })
}

function parseNarrative(text: string) {
  // Parse the streamed text into typed blocks
  const lines = text.split('\n').filter(l => l.trim())
  const blocks: { type: string; speaker?: string; html: string }[] = []
  const opts: string[] = []

  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('[OPT]')) {
      opts.push(trimmed.slice(5).trim())
    } else if (trimmed.startsWith('[MUSIC]')) {
      blocks.push({ type: 'music', html: escapeHtml(trimmed.slice(7).trim() || '关羽之歌响起') })
    } else if (trimmed.startsWith('[SYS]')) {
      blocks.push({ type: 'sys', html: escapeHtml(trimmed.slice(5).trim()) })
    } else if (trimmed.startsWith('[ERR]')) {
      blocks.push({ type: 'err', html: escapeHtml(trimmed.slice(5).trim()) })
    } else if (/^\[.+?\]/.test(trimmed)) {
      const match = trimmed.match(/^\[(.+?)\]\s*(.*)/)
      if (match) {
        blocks.push({ type: 'dialogue', speaker: match[1], html: escapeHtml(match[2]) })
      }
    } else {
      blocks.push({ type: 'narration', html: escapeHtml(trimmed) })
    }
  }
  return { blocks, opts }
}

function escapeHtml(text: string) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function triggerGlitch() {
  isGlitching.value = true
  spawnNoise(6)
  glitchTimer = window.setTimeout(() => { isGlitching.value = false }, 150)
}

async function sendAction(action: string) {
  options.value = []
  isStreaming.value = true
  scrollToBottom()

  history.push({ role: 'user', content: action })

  let fullText = ''
  try {
    const resp = await fetch(`${API_BASE}/api/worldview/narrative`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        world_id: route.params.id,
        action,
        history: history.slice(0, -1),
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
            const prevLen = fullText.length
            fullText += msg.content
            // Live parse and display
            const { blocks } = parseNarrative(fullText)
            logBlocks.value = blocks
            scrollToBottom()
            // Glitch when a new [SYS] or [ERR] marker appears in accumulated text
            const newPart = fullText.slice(prevLen)
            const sysCount = (fullText.match(/\[SYS\]/g) || []).length
            const errCount = (fullText.match(/\[ERR\]/g) || []).length
            if (newPart.includes('SYS') || newPart.includes('ERR')) {
              if (Math.random() < 0.5) triggerGlitch()
            }
            // 关羽之歌：检测到新的[MUSIC]标记时播放
            const musicCount = (fullText.match(/\[MUSIC\]/g) || []).length
            if (musicCount > musicPlayedCount.value) {
              musicPlayedCount.value = musicCount
              playGuanyu()
            }
          } else if (msg.type === 'done') {
            // Final parse
            const { blocks, opts } = parseNarrative(fullText)
            logBlocks.value = blocks
            options.value = opts
            history.push({ role: 'assistant', content: fullText })
          }
        } catch {}
      }
    }
  } catch (e) {
    logBlocks.value.push({ type: 'err', html: '连接中断。世界意志暂时无法响应。' })
  }
  isStreaming.value = false
  scrollToBottom()
}

function chooseOption(opt: string) {
  sendAction(opt)
}

function submitFree() {
  const text = freeInput.value.trim()
  if (!text) return
  freeInput.value = ''
  sendAction(text)
}

onMounted(async () => {
  // Init sequence
  const initSteps = ['正在连接世界意志……', '加载世界规则……', '生成初始场景……']
  for (let i = 0; i < initSteps.length; i++) {
    initText.value = initSteps[i]
    await new Promise(r => setTimeout(r, 600))
  }
  pageLoading.value = false
  // Start narrative
  sendAction('')
  // 环境噪点（随机间隔闪现）
  const scheduleNoise = () => {
    ambientNoiseTimer = window.setTimeout(() => {
      spawnNoise(2 + Math.floor(Math.random() * 3))
      scheduleNoise()
    }, 2000 + Math.random() * 3000)
  }
  scheduleNoise()
})

onBeforeUnmount(() => {
  if (glitchTimer) clearTimeout(glitchTimer)
  if (ambientNoiseTimer) clearTimeout(ambientNoiseTimer)
})
</script>

<style scoped>
.narrative {
  width: 100%;
  height: 100vh;
  background: radial-gradient(ellipse at 50% 40%, #0a120a 0%, #060906 60%, #030503 100%);
  display: flex;
  flex-direction: column;
  font-family: 'Courier New', 'Source Code Pro', monospace;
  position: relative;
  overflow: hidden;
}
.narrative.glitching {
  animation: glitch 0.18s linear;
}
@keyframes glitch {
  0% { transform: translate(0); filter: none; }
  20% { transform: translate(-3px, 2px) skewX(1deg); filter: hue-rotate(90deg) contrast(1.5); }
  40% { transform: translate(2px, -1px); filter: saturate(3) brightness(1.3); }
  60% { transform: translate(-2px, 1px) skewX(-1deg); filter: hue-rotate(-90deg); }
  80% { transform: translate(1px, 2px); filter: invert(0.1) contrast(2); }
  100% { transform: translate(0); filter: none; }
}

/* CRT扫描线 */
.scanlines {
  position: fixed;
  inset: 0;
  z-index: 90;
  pointer-events: none;
  background: repeating-linear-gradient(
    to bottom,
    transparent 0px,
    transparent 2px,
    rgba(0, 0, 0, 0.15) 3px,
    rgba(0, 0, 0, 0.15) 4px
  );
  opacity: 0.5;
}

/* 暗角 */
.vignette {
  position: fixed;
  inset: 0;
  z-index: 89;
  pointer-events: none;
  background: radial-gradient(ellipse at center, transparent 55%, rgba(0, 0, 0, 0.5) 100%);
}

/* 故障噪点块 */
.noise-layer {
  position: fixed;
  inset: 0;
  z-index: 95;
  pointer-events: none;
}
.noise-block {
  position: absolute;
  mix-blend-mode: screen;
}

.back-btn {
  position: fixed;
  top: 20px; left: 20px;
  z-index: 100;
  background: none;
  border: 1px solid rgba(0,255,65,0.2);
  color: rgba(0,255,65,0.5);
  width: 36px; height: 36px;
  border-radius: 4px;
  font-size: 1rem;
  cursor: pointer;
  font-family: inherit;
}
.back-btn:hover { border-color: rgba(0,255,65,0.6); color: rgba(0,255,65,0.9); }

/* 日志区 */
.log-container {
  flex: 1;
  overflow-y: auto;
  padding: 60px 24px 20px;
  max-width: 720px;
  margin: 0 auto;
  width: 100%;
}
.log-block {
  margin-bottom: 12px;
  line-height: 1.8;
  font-size: 0.9rem;
  animation: fadeIn 0.3s ease;
}
@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }

.log-block.narration { color: #33cc55; }
.log-block.narration .log-text { font-style: italic; opacity: 0.85; }

.log-block.dialogue { color: #00ff41; }
.log-block.dialogue .prefix { color: #00ff41; font-weight: bold; margin-right: 8px; }

.log-block.sys { color: #ffffff; opacity: 0.7; font-size: 0.8rem; }
.log-block.sys .prefix { color: #888; margin-right: 6px; }

.log-block.err { color: #ff3333; font-size: 0.8rem; }
.log-block.err .prefix { color: #ff3333; margin-right: 6px; }

.log-block.music { color: #ffd700; font-size: 0.85rem; }
.log-block.music .music-note {
  color: #ffd700;
  margin-right: 8px;
  display: inline-block;
  animation: music-pulse 1s ease-in-out infinite;
}
.log-block.music .log-text { font-style: italic; letter-spacing: 0.05em; }
@keyframes music-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.3); opacity: 0.6; }
}

.cursor-blink { color: #00ff41; animation: blink 0.8s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }

/* 选项区 */
.options-area {
  padding: 16px 24px 24px;
  max-width: 720px;
  margin: 0 auto;
  width: 100%;
}
.option-btn {
  display: block;
  width: 100%;
  text-align: left;
  background: rgba(0, 255, 65, 0.03);
  border: 1px solid rgba(0, 255, 65, 0.2);
  color: #00ff41;
  padding: 10px 16px;
  margin-bottom: 8px;
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.85rem;
  transition: all 0.2s;
}
.option-btn:hover {
  background: rgba(0, 255, 65, 0.08);
  border-color: rgba(0, 255, 65, 0.5);
}
.opt-num { opacity: 0.5; margin-right: 8px; }

.free-input-row {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
.free-input {
  flex: 1;
  background: rgba(0, 255, 65, 0.03);
  border: 1px solid rgba(0, 255, 65, 0.15);
  color: #00ff41;
  padding: 10px 14px;
  border-radius: 4px;
  font-family: inherit;
  font-size: 0.85rem;
  outline: none;
}
.free-input::placeholder { color: rgba(0, 255, 65, 0.3); }
.free-input:focus { border-color: rgba(0, 255, 65, 0.4); }

.submit-btn {
  background: rgba(0, 255, 65, 0.1);
  border: 1px solid rgba(0, 255, 65, 0.3);
  color: #00ff41;
  width: 40px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1.1rem;
}
.submit-btn:hover { background: rgba(0, 255, 65, 0.2); }
.submit-btn:disabled { opacity: 0.3; cursor: default; }

/* 初始加载 */
.init-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0a0a0a;
  z-index: 50;
}
.init-text {
  color: rgba(0, 255, 65, 0.6);
  font-size: 0.9rem;
  animation: blink 1.2s step-end infinite;
}
</style>
