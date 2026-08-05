<template>
  <div class="terminal" :class="{ glitching: isGlitching }">
    <!-- CRT 故障艺术覆盖层 -->
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

    <!-- ═══════════ 天意面板（顶部固定） ═══════════ -->
    <div class="tianyi-panel">
      <span class="panel-label">天意面板</span>
      <span class="panel-sep">|</span>
      <span class="panel-item">节点：<b>{{ panelNode || '—' }}</b></span>
      <span class="panel-item">温度：<b :class="tempClass">{{ panelTemp }}</b></span>
      <span class="panel-item">上下文：<b :class="ctxClass">{{ panelCtx }}%</b></span>
      <span class="panel-item" :class="{ warning: panelAnomaly }">异常：<b>{{ panelAnomaly || '无' }}</b></span>
      <span class="panel-item">偏离度：<b :class="devClass">{{ panelDeviation }}%</b></span>
      <span class="panel-sep">|</span>
      <span class="panel-item phase-summary" :class="phaseSummaryClass" @click="showPhase = !showPhase">
        {{ phaseSummary }}
      </span>
      <span class="panel-sep">|</span>
      <span class="panel-inject" v-if="lastInjection" :title="lastInjection">
        上轮：{{ lastInjection }}
      </span>
    </div>

    <!-- ═══════════ 三栏主体 ═══════════ -->
    <div class="main-body">
      <!-- 左栏：折叠思维链（PHASE 校验） -->
      <aside class="sidebar-left" :class="{ open: showPhase }">
        <div class="sidebar-header" @click="showPhase = !showPhase">
          <span>◈ PHASE 校验链</span>
          <span class="sidebar-toggle">{{ showPhase ? '◀' : '▶' }}</span>
        </div>
        <div v-if="showPhase" class="sidebar-content">
          <!-- 综合评定 -->
          <div class="phase-grade" :class="phaseSummaryClass">
            {{ phaseSummary }}
          </div>
          <div v-if="phaseStrategy" class="phase-strategy">
            {{ phaseStrategy }}
          </div>
          <!-- 各 PHASE 折叠卡片 -->
          <div
            v-for="(check, key) in phaseChecks"
            :key="key"
            class="phase-card"
            :class="{ fail: !check.pass }"
          >
            <div class="phase-card-header" @click="togglePhaseDetail(key)">
              <span class="phase-icon">{{ check.pass ? '✓' : '✗' }}</span>
              <span class="phase-label">{{ check.label }}</span>
              <span class="phase-arrow">{{ expandedPhases[key] ? '▾' : '▸' }}</span>
            </div>
            <div v-if="expandedPhases[key]" class="phase-card-detail">
              {{ check.detail }}
            </div>
          </div>
        </div>
      </aside>

      <!-- 中栏：世界响应 -->
      <main class="log-container" ref="logRef">
        <div v-for="(block, i) in logBlocks" :key="i" class="log-block" :class="block.type">
          <span v-if="block.type === 'sys'" class="prefix">[SYS]</span>
          <span v-else-if="block.type === 'err'" class="prefix">[ERR]</span>
          <span v-else-if="block.type === 'music'" class="prefix music-note">♪</span>
          <span v-else-if="block.type === 'dialogue'" class="prefix">[{{ block.speaker }}]</span>
          <span class="log-text" v-html="block.html"></span>
        </div>
        <div v-if="isStreaming" class="log-block streaming">
          <template v-if="!contentStarted">
            <span class="loading-dots">◈</span>
            <span class="loading-quote" :key="loadingQuoteIndex">{{ loadingQuotes[loadingQuoteIndex] }}</span>
          </template>
          <span v-else class="cursor-blink">▌</span>
        </div>
      </main>

      <!-- 右栏：选项分析 -->
      <aside class="sidebar-right" :class="{ open: showOptAnalysis }">
        <div class="sidebar-header" @click="showOptAnalysis = !showOptAnalysis">
          <span>◈ 天意推荐分析</span>
          <span class="sidebar-toggle">{{ showOptAnalysis ? '▶' : '◀' }}</span>
        </div>
        <div v-if="showOptAnalysis && options.length > 0" class="sidebar-content">
          <div
            v-for="(opt, i) in options"
            :key="i"
            class="opt-card"
            :class="optTypeClass(i)"
            @click="pickOption(opt)"
          >
            <div class="opt-card-num">{{ i + 1 }}</div>
            <div class="opt-card-body">
              <div class="opt-card-text">{{ opt }}</div>
              <div class="opt-card-impact">
                <span class="impact-label">{{ optImpactLabel(i) }}</span>
                <span class="impact-detail">{{ optImpactDetail(opt) }}</span>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>

    <!-- ═══════════ 底部：天意推荐 + 自由注入 ═══════════ -->
    <div v-if="options.length > 0 && !isStreaming" class="input-area">
      <div class="options-list">
        <button
          v-for="(opt, i) in options"
          :key="i"
          class="option-btn"
          @click="sendInjection(opt)"
        >
          <span class="opt-num">{{ i + 1 }}</span>
          <span class="opt-text">{{ opt }}</span>
          <span class="opt-hint">{{ optHint(i) }}</span>
        </button>
      </div>
      <div class="free-row">
        <textarea
          v-model="freeInput"
          class="free-input"
          placeholder="输入天意指令，改写世界……"
          rows="1"
          @keydown.enter.exact.prevent="submitFree"
        ></textarea>
        <button class="submit-btn" @click="submitFree" :disabled="!freeInput.trim()">注入</button>
      </div>
    </div>

    <!-- 初始加载 -->
    <div v-if="pageLoading" class="init-overlay">
      <p class="init-text">{{ initText }}</p>
    </div>

    <!-- 开局确认 -->
    <div v-if="showSetup" class="setup-overlay">
      <div class="setup-panel">
        <h2 class="setup-title">天意降临</h2>
        <p class="setup-desc">
          你是天意。你输入的文字，就是注入这个世界的 prompt。<br/>
          角色不会意识到你的存在——他们只是在每一次注入后，<br/>
          世界被无声地改写。他们觉得一切都是自然的。
        </p>
        <div class="setup-section">
          <p class="setup-label">选择起始节点</p>
          <div class="setup-chips">
            <button
              v-for="node in nodeOptions"
              :key="node"
              class="setup-chip"
              :class="{ selected: selectedNode === node }"
              @click="selectedNode = node"
            >{{ node }}</button>
          </div>
        </div>
        <button class="setup-enter" @click="startGame">降临此世界</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick, computed, onMounted, onBeforeUnmount, inject } from 'vue'
import { useRouter } from 'vue-router'

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
const contentStarted = ref(false)
const storyState = ref<Record<string, any>>({})
const musicPlayedCount = ref(0)

// 天意面板
const panelNode = ref('')
const panelTemp = ref(1.3)
const panelCtx = ref(80)
const panelAnomaly = ref('')
const panelDeviation = ref(0)
const lastInjection = ref('')

// 面板样式
const tempClass = computed(() => {
  if (panelTemp.value > 1.5) return 'val-danger'
  if (panelTemp.value < 1.0) return 'val-cool'
  return ''
})
const ctxClass = computed(() => {
  if (panelCtx.value < 40) return 'val-danger'
  if (panelCtx.value < 70) return 'val-warn'
  return ''
})
const devClass = computed(() => {
  if (panelDeviation.value > 60) return 'val-danger'
  if (panelDeviation.value > 30) return 'val-warn'
  return ''
})

// ═══════════ PHASE 校验链（折叠思维链） ═══════════
const showPhase = ref(false)
const showOptAnalysis = ref(false)
const phaseChecks = ref<Record<string, { label: string; pass: boolean; detail: string }>>({})
const phaseSummary = ref('—')
const phaseStrategy = ref('')
const expandedPhases = reactive<Record<string, boolean>>({})

const phaseSummaryClass = computed(() => {
  if (phaseSummary.value.includes('通过')) return 'grade-pass'
  if (phaseSummary.value.includes('警告')) return 'grade-warn'
  if (phaseSummary.value.includes('高风险')) return 'grade-fail'
  return ''
})

function togglePhaseDetail(key: string) {
  expandedPhases[key] = !expandedPhases[key]
}

// ═══════════ 选项分析 ═══════════
function optTypeClass(i: number) {
  if (i === 0) return 'opt-push'
  if (i === 1) return 'opt-absurd'
  return 'opt-pull'
}

function optImpactLabel(i: number) {
  if (i === 0) return '推进剧情'
  if (i === 1) return '制造荒诞'
  return '拉回正轨'
}

function optImpactDetail(opt: string) {
  const lower = opt.toLowerCase()
  if (lower.includes('跳转') || lower.includes('跳过') || lower.includes('下一个')) return '偏离度 +30'
  if (lower.includes('继续') || lower.includes('然后') || lower.includes('回到')) return '偏离度 −10'
  if (lower.includes('突然') || lower.includes('莫名其妙') || lower.includes('叉出去')) return '偏离度 +10'
  return '偏离度 +5~15'
}

function optHint(i: number) {
  if (i === 0) return '推进'
  if (i === 1) return '荒诞'
  return '拉回'
}

// 加载轮播
const loadingQuotes = [
  '天意如刀，一笔改命。',
  '你输入什么，世界就变成什么。',
  '角色不会质疑——他们觉得一切都是自然的。',
  '温度越高，角色越疯狂。',
  '上下文窗口溢出，角色开始健忘。',
  '胜兵必骄，骄兵必败，败兵必哀，哀兵必胜。',
  '宁可我负天下人，休教天下人负我。',
  '接着奏乐接着舞。',
  '关羽之歌响起——不管关羽在不在场。',
  '死是凉爽的夏夜，可供人无忧地安眠。',
  '不可能！我二弟天下无敌！',
  '好方略，不过我想稍作修改。',
  '叉出去！',
  '自刎归天。',
  '新三国道：两端是传送门，一夜千里。',
]
const loadingQuoteIndex = ref(0)
let loadingQuoteTimer: number | null = null

function startLoadingQuotes() {
  contentStarted.value = false
  loadingQuoteIndex.value = Math.floor(Math.random() * loadingQuotes.length)
  if (loadingQuoteTimer) clearInterval(loadingQuoteTimer)
  loadingQuoteTimer = window.setInterval(() => {
    loadingQuoteIndex.value = (loadingQuoteIndex.value + 1) % loadingQuotes.length
  }, 2200)
}

function stopLoadingQuotes() {
  if (loadingQuoteTimer) { clearInterval(loadingQuoteTimer); loadingQuoteTimer = null }
}

const showSetup = ref(false)
const selectedNode = ref('曹操献刀')
const nodeOptions = [
  '曹操献刀', '捉放曹', '桃园结义', '诸侯讨董', '连环计',
  '三让徐州', '辕门射戟', '吕布殒命', '煮酒论英雄',
  '斩颜良诛文丑', '过五关斩六将', '官渡之战', '三顾茅庐', '博望坡',
  '长坂坡', '火烧赤壁', '华容道', '取长沙', '三气周瑜',
  '假道灭虢', '铜雀台', '割须弃袍', '入蜀', '单刀赴会',
  '虎女犬子', '败走麦城', '曹操之死', '曹丕废帝', '刘备伐吴',
  '陆逊拜将', '夷陵之战', '白帝城托孤', '出师表', '北伐中原',
  '失街亭', '木牛流马', '张郃中计', '仲达受辱', '上方谷',
  '五丈原', '高平陵', '归晋',
]

function startGame() {
  showSetup.value = false
  storyState.value = {}
  sendInjection('', selectedNode.value)
}

function goBack() { router.push('/') }

// 故障噪点
interface NoiseBlock { x: number; y: number; w: number; h: number; color: string }
const noiseBlocks = ref<NoiseBlock[]>([])

function spawnNoise(count: number) {
  const colors = ['rgba(0,255,65,0.15)', 'rgba(255,0,170,0.12)', 'rgba(0,204,255,0.12)', 'rgba(255,255,255,0.08)']
  const blocks: NoiseBlock[] = []
  for (let i = 0; i < count; i++) {
    blocks.push({
      x: Math.random() * 100, y: Math.random() * 100,
      w: 20 + Math.random() * 120, h: 2 + Math.random() * 8,
      color: colors[Math.floor(Math.random() * colors.length)],
    })
  }
  noiseBlocks.value = blocks
  setTimeout(() => { noiseBlocks.value = [] }, 120)
}

let ambientNoiseTimer: number | null = null

function scrollToBottom() {
  nextTick(() => {
    if (logRef.value) { logRef.value.scrollTop = logRef.value.scrollHeight }
  })
}

function parseNarrative(text: string) {
  const blocks: { type: string; speaker?: string; html: string }[] = []
  const opts: string[] = []
  const lines = text.split('\n')

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
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
      if (match && isSpeakerName(match[1])) {
        blocks.push({ type: 'dialogue', speaker: match[1], html: escapeHtml(match[2]) })
      } else {
        blocks.push({ type: 'narration', html: escapeHtml(trimmed) })
      }
    } else if (trimmed) {
      // 检测面板关键字段（模型输出在"当前："行）
      if (trimmed.includes('温度：') && trimmed.includes('上下文：')) {
        const m = trimmed.match(/温度：([\d.]+)/)
        if (m) panelTemp.value = parseFloat(m[1])
        const c = trimmed.match(/上下文：(\d+)%?/)
        if (c) panelCtx.value = parseInt(c[1])
        const d = trimmed.match(/偏离度：(\d+)%?/)
        if (d) panelDeviation.value = parseInt(d[1])
        // 面板行不显示在日志中
        continue
      }
      if (trimmed.includes('异常：')) {
        const a = trimmed.replace(/.*异常：/, '').replace(/\(.*\)/, '').trim()
        panelAnomaly.value = a === '无' ? '' : a
        continue
      }
      blocks.push({ type: 'narration', html: escapeHtml(trimmed) })
    }
  }
  return { blocks, opts }
}

function isSpeakerName(name: string): boolean {
  return name.length >= 1 && name.length <= 8 && !/[。，！？、；：\s·…—]/.test(name)
}

function escapeHtml(text: string) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function triggerGlitch() {
  isGlitching.value = true
  spawnNoise(6)
  setTimeout(() => { isGlitching.value = false }, 150)
}

const history: { role: string; content: string }[] = []

async function sendInjection(injection: string, startNode: string = '') {
  options.value = []
  showOptAnalysis.value = false
  isStreaming.value = true
  startLoadingQuotes()
  scrollToBottom()

  history.push({ role: 'user', content: injection })

  let fullText = ''
  try {
    const resp = await fetch(`${API_BASE}/api/tianyi`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: injection,
        history: history.slice(0, -1),
        state: storyState.value,
        start_node: startNode,
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
            if (!contentStarted.value) { contentStarted.value = true; stopLoadingQuotes() }
            fullText += msg.content
            const { blocks } = parseNarrative(fullText)
            logBlocks.value = blocks
            // 关羽之歌：检测 [MUSIC] 标记
            const musicCount = (fullText.match(/\[MUSIC\]/g) || []).length
            if (musicCount > musicPlayedCount.value) {
              musicPlayedCount.value = musicCount
              playGuanyu()
            }
            if (Math.random() < 0.3) triggerGlitch()
          } else if (msg.type === 'state') {
            storyState.value = msg.state || {}
            if (msg.state) {
              panelNode.value = msg.state.node || ''
              panelTemp.value = msg.state.world_temperature || 1.3
              panelCtx.value = msg.state.context_window || 80
              panelAnomaly.value = msg.state.anomaly || ''
              panelDeviation.value = msg.state.deviation || 0
              lastInjection.value = msg.state.last_injection || ''
              // PHASE 校验链
              if (msg.state.phase) {
                phaseSummary.value = msg.state.phase.summary || '—'
                phaseStrategy.value = msg.state.phase.strategy || ''
                phaseChecks.value = msg.state.phase.checks || {}
                // 自动展开不通过的项
                for (const [key, check] of Object.entries(phaseChecks.value) as any) {
                  if (!check.pass) expandedPhases[key] = true
                }
              }
              // 关羽之歌：special_event 触发
              if (msg.state.special_event === '关羽之歌响起') {
                playGuanyu()
                triggerGlitch()
              }
              // 关羽之歌：文本检测 [MUSIC] 标记
              if (msg.state.anomaly === '关羽之歌') {
                playGuanyu()
              }
            }
          } else if (msg.type === 'done') {
            const { blocks, opts } = parseNarrative(fullText)
            logBlocks.value = blocks
            options.value = opts
            // 自动展开选项分析
            if (opts.length > 0) showOptAnalysis.value = true
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

function submitFree() {
  const text = freeInput.value.trim()
  if (!text) return
  freeInput.value = ''
  showOptAnalysis.value = false
  sendInjection(text)
}

function pickOption(opt: string) {
  showOptAnalysis.value = false
  sendInjection(opt)
}

onMounted(async () => {
  const initSteps = ['正在连接世界意志……', '初始化天意接口……', '加载 PHASE 校验链……']
  for (let i = 0; i < initSteps.length; i++) {
    initText.value = initSteps[i]
    await new Promise(r => setTimeout(r, 500))
  }
  pageLoading.value = false
  showSetup.value = true

  const scheduleNoise = () => {
    ambientNoiseTimer = window.setTimeout(() => {
      spawnNoise(2 + Math.floor(Math.random() * 3))
      scheduleNoise()
    }, 2000 + Math.random() * 3000)
  }
  scheduleNoise()
})

onBeforeUnmount(() => {
  if (ambientNoiseTimer) clearTimeout(ambientNoiseTimer)
  stopLoadingQuotes()
})
</script>

<style scoped>
/* ═══════════ 基础 CRT ═══════════ */
.terminal {
  width: 100%; height: 100vh;
  background: radial-gradient(ellipse at 50% 40%, #0a120a 0%, #060906 60%, #030503 100%);
  display: flex; flex-direction: column;
  font-family: 'Courier New', 'Source Code Pro', 'Consolas', monospace;
  position: relative; overflow: hidden;
}
.terminal.glitching { animation: glitch 0.18s linear; }
@keyframes glitch {
  0% { transform: translate(0); filter: none; }
  20% { transform: translate(-3px, 2px) skewX(1deg); filter: hue-rotate(90deg) contrast(1.5); }
  40% { transform: translate(2px, -1px); filter: saturate(3) brightness(1.3); }
  60% { transform: translate(-2px, 1px) skewX(-1deg); filter: hue-rotate(-90deg); }
  80% { transform: translate(1px, 2px); filter: invert(0.1) contrast(2); }
  100% { transform: translate(0); filter: none; }
}

.scanlines {
  position: fixed; inset: 0; z-index: 90; pointer-events: none;
  background: repeating-linear-gradient(to bottom, transparent 0px, transparent 2px, rgba(0,0,0,0.15) 3px, rgba(0,0,0,0.15) 4px);
  opacity: 0.5;
}
.vignette {
  position: fixed; inset: 0; z-index: 89; pointer-events: none;
  background: radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.5) 100%);
}
.noise-layer { position: fixed; inset: 0; z-index: 95; pointer-events: none; }
.noise-block { position: absolute; mix-blend-mode: screen; }

.back-btn {
  position: fixed; top: 20px; left: 20px; z-index: 200;
  background: none; border: 1px solid rgba(0,255,65,0.2); color: rgba(0,255,65,0.5);
  width: 36px; height: 36px; border-radius: 4px; font-size: 1rem;
  cursor: pointer; font-family: inherit;
}
.back-btn:hover { border-color: rgba(0,255,65,0.6); color: rgba(0,255,65,0.9); }

/* ═══════════ 天意面板 ═══════════ */
.tianyi-panel {
  position: fixed; top: 0; left: 0; right: 0;
  z-index: 100; height: 38px;
  background: rgba(3, 8, 3, 0.94); border-bottom: 1px solid rgba(255, 68, 34, 0.2);
  display: flex; align-items: center; gap: 8px; padding: 0 16px;
  font-size: 0.68rem; backdrop-filter: blur(4px);
}
.panel-label { color: rgba(255, 68, 34, 0.7); letter-spacing: 0.25em; font-weight: bold; }
.panel-sep { color: rgba(0,255,65,0.15); }
.panel-item { color: rgba(0, 255, 65, 0.7); white-space: nowrap; }
.panel-item b { font-weight: 600; }
.panel-item.warning { color: #ffd700; }
.panel-item.warning b { color: #ffd700; }
.panel-inject {
  color: rgba(0, 255, 65, 0.4); font-style: italic; font-size: 0.65rem;
  max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  cursor: default; margin-left: auto;
}
.phase-summary {
  cursor: pointer; padding: 1px 6px; border-radius: 3px;
  border: 1px solid transparent; transition: all 0.2s;
}
.phase-summary:hover { border-color: rgba(0,255,65,0.3); background: rgba(0,255,65,0.05); }
.grade-pass { color: #00ff41; }
.grade-warn { color: #ffd700; }
.grade-fail { color: #ff4422; }

.val-danger { color: #ff4422; }
.val-warn { color: #ffd700; }
.val-cool { color: #4488ff; }

/* ═══════════ 三栏主体 ═══════════ */
.main-body {
  display: flex; flex: 1; margin-top: 38px; overflow: hidden;
}

/* 左栏：PHASE 校验链 */
.sidebar-left {
  width: 0; overflow: hidden;
  background: rgba(3, 8, 3, 0.96); border-right: 1px solid rgba(0,255,65,0.1);
  transition: width 0.25s ease; flex-shrink: 0;
  display: flex; flex-direction: column;
}
.sidebar-left.open { width: 280px; }
.sidebar-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 12px; font-size: 0.7rem; color: rgba(0,255,65,0.5);
  cursor: pointer; border-bottom: 1px solid rgba(0,255,65,0.08);
  letter-spacing: 0.1em; flex-shrink: 0;
}
.sidebar-header:hover { color: rgba(0,255,65,0.8); }
.sidebar-toggle { font-size: 0.7rem; }
.sidebar-content {
  overflow-y: auto; flex: 1; padding: 8px;
}

/* PHASE 卡片 */
.phase-grade {
  font-size: 0.75rem; font-weight: bold; padding: 6px 10px;
  border-radius: 4px; margin-bottom: 8px; text-align: center;
}
.phase-grade.grade-pass { background: rgba(0,255,65,0.08); border: 1px solid rgba(0,255,65,0.2); }
.phase-grade.grade-warn { background: rgba(255,215,0,0.08); border: 1px solid rgba(255,215,0,0.2); }
.phase-grade.grade-fail { background: rgba(255,68,34,0.08); border: 1px solid rgba(255,68,34,0.2); }
.phase-strategy {
  font-size: 0.65rem; color: rgba(0,255,65,0.5); padding: 4px 8px;
  margin-bottom: 8px; line-height: 1.5;
}

.phase-card {
  margin-bottom: 4px; border-radius: 3px;
  border: 1px solid rgba(0,255,65,0.08);
  background: rgba(0,255,65,0.02);
  transition: all 0.15s;
}
.phase-card.fail { border-color: rgba(255,68,34,0.2); background: rgba(255,68,34,0.03); }
.phase-card-header {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 8px; cursor: pointer; font-size: 0.65rem;
  color: rgba(0,255,65,0.7);
}
.phase-card.fail .phase-card-header { color: rgba(255,68,34,0.8); }
.phase-icon { font-size: 0.6rem; width: 14px; text-align: center; }
.phase-card.fail .phase-icon { color: #ff4422; }
.phase-label { flex: 1; }
.phase-arrow { font-size: 0.55rem; color: rgba(0,255,65,0.3); }
.phase-card-detail {
  padding: 4px 8px 6px 28px; font-size: 0.6rem;
  color: rgba(0,255,65,0.45); line-height: 1.5;
  border-top: 1px solid rgba(0,255,65,0.05);
}

/* 中栏：日志区 */
.log-container {
  flex: 1; overflow-y: auto;
  padding: 16px 20px 170px;
  max-width: 700px; margin: 0 auto; width: 100%;
}
.log-block { margin-bottom: 10px; line-height: 1.75; font-size: 0.85rem; animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }

.log-block.narration { color: #88aa88; }
.log-block.narration .log-text { opacity: 0.8; }
.log-block.dialogue { color: #00ff41; }
.log-block.dialogue .prefix { color: #00ff41; font-weight: bold; margin-right: 8px; letter-spacing: 0.05em; }
.log-block.dialogue .log-text { font-weight: 600; }
.log-block.sys { color: #ffffff; opacity: 0.7; font-size: 0.75rem; }
.log-block.sys .prefix { color: #888; margin-right: 6px; }
.log-block.err { color: #ff3333; font-size: 0.75rem; }
.log-block.err .prefix { color: #ff3333; margin-right: 6px; }
.log-block.music { color: #ffd700; font-size: 0.8rem; }
.log-block.music .music-note {
  color: #ffd700; margin-right: 8px; display: inline-block;
  animation: music-pulse 1s ease-in-out infinite;
}
@keyframes music-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.3); opacity: 0.6; }
}

.cursor-blink { color: #00ff41; animation: blink 0.8s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }
.loading-dots { color: #00ff41; display: inline-block; margin-right: 10px; animation: spin360 1.6s linear infinite; }
@keyframes spin360 { to { transform: rotate(360deg); } }
.loading-quote { color: rgba(0, 255, 65, 0.5); font-size: 0.78rem; animation: quote-fade 0.5s ease; }
@keyframes quote-fade { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }

/* 右栏：选项分析 */
.sidebar-right {
  width: 0; overflow: hidden;
  background: rgba(3, 8, 3, 0.96); border-left: 1px solid rgba(0,255,65,0.1);
  transition: width 0.25s ease; flex-shrink: 0;
  display: flex; flex-direction: column;
}
.sidebar-right.open { width: 260px; }

.opt-card {
  margin-bottom: 6px; border-radius: 4px; padding: 8px 10px;
  border: 1px solid rgba(0,255,65,0.1);
  background: rgba(0,255,65,0.02);
  display: flex; gap: 8px; align-items: flex-start;
  cursor: pointer; transition: all 0.15s;
}
.opt-card:hover { background: rgba(0,255,65,0.06); border-color: rgba(0,255,65,0.25); }
.opt-card.opt-push { border-left: 2px solid rgba(0,255,65,0.4); }
.opt-card.opt-absurd { border-left: 2px solid rgba(255,170,0,0.4); }
.opt-card.opt-pull { border-left: 2px solid rgba(68,136,255,0.4); }
.opt-card-num {
  font-size: 0.65rem; color: rgba(0,255,65,0.4); font-weight: bold;
  width: 18px; height: 18px; border-radius: 50%;
  border: 1px solid rgba(0,255,65,0.2); display: flex;
  align-items: center; justify-content: center; flex-shrink: 0;
}
.opt-card-body { flex: 1; min-width: 0; }
.opt-card-text {
  font-size: 0.65rem; color: rgba(0,255,65,0.7); line-height: 1.4;
  margin-bottom: 4px;
}
.opt-card-impact {
  display: flex; gap: 6px; font-size: 0.58rem;
}
.impact-label {
  color: rgba(0,255,65,0.35); background: rgba(0,255,65,0.05);
  padding: 1px 5px; border-radius: 2px; white-space: nowrap;
}
.impact-detail { color: rgba(0,255,65,0.4); }

/* ═══════════ 底部输入区 ═══════════ */
.input-area {
  position: fixed; bottom: 0; left: 50%; transform: translateX(-50%);
  z-index: 100; width: min(700px, 90vw);
  padding: 10px 16px 18px;
  background: rgba(3, 8, 3, 0.94);
  border-top: 1px solid rgba(0, 255, 65, 0.15);
  backdrop-filter: blur(4px);
}
.options-list { display: flex; flex-direction: column; gap: 5px; margin-bottom: 8px; }
.option-btn {
  display: flex; align-items: center; gap: 8px; width: 100%; text-align: left;
  background: rgba(0, 255, 65, 0.03); border: 1px solid rgba(0, 255, 65, 0.15);
  color: #00ff41; padding: 7px 12px; border-radius: 4px;
  cursor: pointer; font-family: inherit; font-size: 0.78rem; transition: all 0.2s;
}
.option-btn:hover { background: rgba(0, 255, 65, 0.08); border-color: rgba(0, 255, 65, 0.4); }
.opt-num { opacity: 0.4; flex-shrink: 0; font-size: 0.7rem; }
.opt-text { flex: 1; }
.opt-hint {
  font-size: 0.6rem; color: rgba(0,255,65,0.3); background: rgba(0,255,65,0.05);
  padding: 1px 6px; border-radius: 2px; flex-shrink: 0;
}

.free-row { display: flex; gap: 8px; }
.free-input {
  flex: 1; background: rgba(0, 255, 65, 0.03); border: 1px solid rgba(0, 255, 65, 0.12);
  color: #00ff41; padding: 9px 12px; border-radius: 4px;
  font-family: inherit; font-size: 0.82rem; outline: none; resize: none;
}
.free-input::placeholder { color: rgba(0, 255, 65, 0.25); }
.free-input:focus { border-color: rgba(0, 255, 65, 0.35); }
.submit-btn {
  background: rgba(255, 68, 34, 0.12); border: 1px solid rgba(255, 68, 34, 0.3);
  color: #ff5533; padding: 9px 16px; border-radius: 4px;
  cursor: pointer; font-size: 0.82rem; font-family: inherit;
  white-space: nowrap; transition: all 0.2s;
}
.submit-btn:hover { background: rgba(255, 68, 34, 0.2); }
.submit-btn:disabled { opacity: 0.3; cursor: default; }

/* ═══════════ 加载 & 开局 ═══════════ */
.init-overlay { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: #0a0a0a; z-index: 50; }
.init-text { color: rgba(0, 255, 65, 0.6); font-size: 0.9rem; animation: blink 1.2s step-end infinite; }

.setup-overlay {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  background: rgba(5, 8, 5, 0.92); z-index: 60; backdrop-filter: blur(4px);
}
.setup-panel {
  width: min(560px, 88vw); max-height: 82vh; overflow-y: auto;
  padding: 36px 32px; text-align: center;
  border: 1px solid rgba(255, 68, 34, 0.3); border-radius: 8px;
  background: rgba(8, 12, 8, 0.9);
}
.setup-title { color: #ff5533; font-size: 1.6rem; letter-spacing: 0.4em; margin: 0 0 20px; }
.setup-desc { color: rgba(0, 255, 65, 0.6); font-size: 0.85rem; line-height: 1.8; margin: 0 0 28px; }
.setup-section { margin-bottom: 22px; text-align: left; }
.setup-label {
  color: rgba(0, 255, 65, 0.7); font-size: 0.8rem; letter-spacing: 0.15em;
  margin: 0 0 10px;
}
.setup-chips {
  display: flex; flex-wrap: wrap; gap: 8px;
  max-height: 160px; overflow-y: auto;
}
.setup-chip {
  background: transparent; border: 1px solid rgba(0, 255, 65, 0.25);
  color: rgba(0, 255, 65, 0.6); padding: 6px 14px; border-radius: 4px;
  font-size: 0.8rem; cursor: pointer; font-family: inherit;
  transition: all 0.2s;
}
.setup-chip:hover { border-color: rgba(0, 255, 65, 0.5); color: #00ff41; }
.setup-chip.selected {
  background: rgba(0, 255, 65, 0.15); border-color: #00ff41; color: #00ff41;
}
.setup-enter {
  display: block; width: 100%;
  background: rgba(255, 68, 34, 0.12); border: 1px solid #ff5533;
  color: #ff5533; padding: 12px; border-radius: 4px;
  font-size: 0.95rem; letter-spacing: 0.25em;
  cursor: pointer; font-family: inherit; transition: all 0.2s;
}
.setup-enter:hover { background: rgba(255, 68, 34, 0.22); }
</style>