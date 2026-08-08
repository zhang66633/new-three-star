<template>
  <div class="play-page">
    <!-- 水墨氛围背景（Seedream 生图 + 光晕漂移 + 暗角） -->
    <AtmoBackground :atmo-tag="currentAtmo" />
    <!-- Canvas 粒子氛围（雨/火/尘/雪/星 按 atmo 自动切换） -->
    <ParticleLayer :atmo-tag="currentAtmo" />

    <!-- 墨染转场遮罩（场景切换时触发） -->
    <div class="ink-transition" :class="{ active: inkActive }" aria-hidden="true"></div>

    <!-- 错误提示（请求失败时显示，可重试） -->
    <transition name="error-fade">
      <div v-if="errorMessage" class="error-banner">
        <span class="error-text">{{ errorMessage }}</span>
        <button class="error-retry" @click="retryAfterError">重试</button>
      </div>
    </transition>

    <!-- 返回星图 -->
    <button class="back-btn" @click="goBack" aria-label="返回星图">←</button>

    <!-- 加载动画（开局/场景切换） -->
    <CinematicLoader
      :show="loaderVisible"
      :title="loaderTitle"
      :chapter-label="loaderChapterLabel"
      :status-text="loaderStatus"
    />

    <!-- 主界面（started 后常显；加载器为 fixed 遮罩盖在其上，不隐藏主界面） -->
    <div class="play-main" v-show="started">
      <!-- 章节铭牌 -->
      <header class="era-banner">
        <span class="era-label">{{ eraLabel }}</span>
        <span class="era-chapter">{{ eraChapter }}</span>
        <span class="era-goldline"></span>
        <!-- 8 PHASE 质量指示灯 -->
        <button
          v-if="phaseReport"
          class="phase-indicator"
          :class="{ 'phase-warn': hasPhaseWarnings }"
          @click="showPhaseDetail = !showPhaseDetail"
          :aria-label="'校验报告'"
        >◈</button>
        <!-- 天意修正指示器 -->
        <span v-if="correctedCount > 0" class="corrected-badge" :title="lastCorrected">
          修正×{{ correctedCount }}
        </span>
        <!-- PHASE 详情面板 -->
        <div v-if="showPhaseDetail && phaseReport" class="phase-detail">
          <div class="pd-title">8 PHASE 校验</div>
          <div v-for="(v, k) in phaseReport.llm" :key="k" class="pd-row">
            <span class="pd-phase">{{ k.toUpperCase() }}</span>
            <span class="pd-status" :class="v.pass ? 'pd-pass' : 'pd-fail'">{{ v.pass ? '✓' : '✗' }}</span>
            <span class="pd-reason">{{ v.reason }}</span>
          </div>
        </div>
      </header>

      <!-- 叙事区 -->
      <main class="narrative-area" ref="narrativeRef">

        <!-- ① 思维链阶段：AI 正在推演当前局势 -->
        <div v-if="loadPhase === 'thinking'" class="thinking-phase">
          <div class="think-header">
            <span class="think-icon">◈</span>
            <span class="think-title">天意正在推演此局……</span>
          </div>
          <div class="think-detail">
            <div class="think-row">
              <span class="think-label">场景</span>
              <span class="think-val">{{ loaderChapterLabel }} · {{ loaderTitle }}</span>
            </div>
            <div class="think-row" v-if="thinkingNpcList.length">
              <span class="think-label">在场</span>
              <span class="think-val">
                <span v-for="(n, i) in thinkingNpcList" :key="n[0]" class="think-npc">
                  {{ n[0] }}<span class="think-npc-rel" :class="relClass(n[1])">感{{ n[1] }}</span>
                  <span v-if="i < thinkingNpcList.length - 1"> · </span>
                </span>
              </span>
            </div>
            <div class="think-row">
              <span class="think-label">记忆</span>
              <span class="think-val">STM {{ thinkingStmCount }} 条 · LTM {{ thinkingLtmCount }} 条 · PIN {{ thinkingPinCount }} 条</span>
            </div>
            <div class="think-row" v-if="thinkingForeshadowCount">
              <span class="think-label">伏笔</span>
              <span class="think-val think-foreshadow">{{ thinkingForeshadowCount }} 条未解</span>
            </div>
            <div class="think-row">
              <span class="think-label">天意</span>
              <span class="think-val" :class="tensionClass(thinkingTension)">{{ thinkingTension }}/100</span>
            </div>
          </div>
          <div class="think-pulse">
            <span class="think-ember"></span>
            <span class="think-ember" style="animation-delay:0.4s"></span>
            <span class="think-ember" style="animation-delay:0.8s"></span>
          </div>
        </div>

        <!-- ②-④ 剧情流式 / 记忆 / 人物 → 叙事文本 -->

        <div v-for="(block, i) in narrativeBlocks" :key="i" class="narrative-block">
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

      <!-- 选项区（仅选项阶段显示） -->
      <footer class="choice-area" :class="{ 'choice-reveal': loadPhase === 'options' }" v-if="loadPhase === 'options'">
        <template v-if="options.length > 0">
          <button
            v-for="(opt, i) in options"
            :key="i"
            class="choice-btn"
            :class="tensionClass(opt.tension)"
            @click="chooseOption(opt)"
          >
            <span class="choice-text">{{ opt.text }}</span>
            <span v-if="opt.effect" class="choice-effect">{{ opt.effect }}</span>
          </button>
        </template>
        <!-- options 缺失/被截断时的兜底：给玩家一个继续入口，避免硬卡死 -->
        <button v-else class="choice-btn tension-mid" @click="sendAction('继续前行', 0)">
          <span class="choice-text">继续前行……</span>
          <span class="choice-effect">（选项未及到达，先走一步）</span>
        </button>
        <div class="free-row">
          <input
            v-model="freeInput"
            class="free-input"
            placeholder="或者，你想做点什么……"
            @keydown.enter="submitFree"
          />
          <button class="free-submit" :disabled="!freeInput.trim()" @click="submitFree()">行动</button>
        </div>
      </footer>

      <!-- 角色状态卡（仅在场有人时显示） -->
      <aside class="character-panel" :class="{ 'cp-reveal': loadPhase === 'character' }" v-if="Object.keys(characterRels).length > 0">
        <div class="cp-title">在场</div>
        <div v-for="(rel, name) in characterRels" :key="name" class="character-chip">
          <span class="chip-avatar">{{ name[0] }}</span>
          <span class="chip-info">
            <span class="chip-name">{{ name }}</span>
            <span v-if="NPC_PERSONA[name]" class="chip-trait">{{ NPC_PERSONA[name].trait }}</span>
            <span class="chip-rels">
              <span class="chip-rel" :class="relClass(rel)">感{{ rel }}</span>
              <span class="chip-trust" :class="trustClass(trust[name] ?? 50)">信{{ trust[name] ?? 50 }}</span>
            </span>
            <span v-if="NPC_PERSONA[name]?.mechanism" class="chip-mech">{{ NPC_PERSONA[name].mechanism }}</span>
          </span>
        </div>
      </aside>

      <!-- 记忆抽屉（三段式：PIN / LTM / STM） -->
      <button class="memory-toggle" :class="{ 'mem-reveal': loadPhase === 'memory' }" @click="showMemory = !showMemory">
        {{ showMemory ? '收起记忆 ▲' : '记忆' }}
        <span v-if="totalMemCount > 0" class="mt-counts">
          STM [{{ stmList.length }}/6]｜LTM [{{ ltmList.length }}]｜PIN {{ pinnedCount }}
        </span>
      </button>
      <div v-if="showMemory" class="memory-drawer">
        <!-- 计数头 -->
        <div class="md-header">STM [{{ stmList.length }}/6]｜LTM [{{ ltmList.length }}]｜PIN {{ pinnedCount }}条</div>

        <!-- 📌 PIN 钉选记忆 -->
        <div class="md-section">
          <div class="md-section-title">📌 PIN 钉选记忆</div>
          <div v-if="pinItems.length === 0" class="md-empty-row">— 暂无 —</div>
          <div v-for="(m, i) in pinItems" :key="m.id" class="memory-row">
            <span class="mr-num">{{ i + 1 }}</span>
            <span class="mr-time">{{ m.time || '—' }}</span>
            <span class="mr-scene">{{ m.scene || '—' }}</span>
            <span class="mr-text">{{ m.text }}</span>
            <button class="mi-pin pinned" @click="togglePin(m.id)" aria-label="取消钉选">📌</button>
          </div>
        </div>

        <!-- 📚 LTM 长期记忆 -->
        <div class="md-section">
          <div class="md-section-title">📚 LTM 长期记忆</div>
          <div v-if="ltmList.length === 0" class="md-empty-row">— 暂无 —</div>
          <div v-for="(m, i) in ltmList" :key="m.id" class="memory-row">
            <span class="mr-num">{{ i + 1 }}</span>
            <span class="mr-time">{{ m.time || '—' }}</span>
            <span class="mr-scene">{{ m.scene || '—' }}</span>
            <span class="mr-text">{{ m.text }}</span>
            <button
              class="mi-pin"
              :class="{ pinned: isPinned(m.id) }"
              @click="togglePin(m.id)"
              :aria-label="isPinned(m.id) ? '取消钉选' : '钉选'"
            >{{ isPinned(m.id) ? '📌' : '📍' }}</button>
          </div>
        </div>

        <!-- 📝 STM 短期记忆 -->
        <div class="md-section">
          <div class="md-section-title">📝 STM 短期记忆</div>
          <div v-if="stmList.length === 0" class="md-empty-row">— 暂无 —</div>
          <div v-for="(m, i) in stmList" :key="m.id" class="memory-row">
            <span class="mr-num">{{ i + 1 }}</span>
            <span class="mr-time">{{ m.time || '—' }}</span>
            <span class="mr-scene">{{ m.scene || '—' }}</span>
            <span class="mr-text">{{ m.text }}</span>
            <button
              class="mi-pin"
              :class="{ pinned: isPinned(m.id) }"
              @click="togglePin(m.id)"
              :aria-label="isPinned(m.id) ? '取消钉选' : '钉选'"
            >{{ isPinned(m.id) ? '📌' : '📍' }}</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onBeforeUnmount, inject } from 'vue'
import { useRouter } from 'vue-router'
import CinematicLoader from '../components/CinematicLoader.vue'
import StreamText from '../components/StreamText.vue'
import AtmoBackground from '../components/AtmoBackground.vue'
import ParticleLayer from '../components/ParticleLayer.vue'
import { usePlaySse } from '../composables/usePlaySse'
import type { GameState, OptionSpec, MemoryItem, PhaseReport } from '../types/play'

const router = useRouter()
const { playStep, isStreaming } = usePlaySse()
const playGuanyu = inject<() => void>('playGuanyu', () => {})

// ── NPC 人设速查（对齐 backend/engine/writer.py PERSONA_FULL）──
const NPC_PERSONA: Record<string, { trait: string; mechanism?: string }> = {
  '曹操':   { trait: '枭雄·窥天侵蚀', mechanism: '魏武挥鞭/世人看错' },
  '刘备':   { trait: '仁义面具·内心盘算', mechanism: '自刎归天/心灵控制' },
  '关羽':   { trait: '傲慢武圣·摸须装逼', mechanism: '一刀斩/水淹七军' },
  '张飞':   { trait: '暴躁猛将·性如烈火', mechanism: '酿制美酒' },
  '诸葛亮': { trait: '天才受气包·窥天最深', mechanism: '人体炼成/向下霸凌' },
  '司马懿': { trait: '隐忍老狐狸·视人如NPC', mechanism: '化骨绵掌' },
  '吕布':   { trait: '率真莽夫·武力+100%', mechanism: '三姓家奴' },
  '董卓':   { trait: '自认大汉忠臣', mechanism: '视刘协为亲人' },
  '袁绍':   { trait: '宽厚明主·屡失良机', mechanism: '死亡抗性II' },
  '孙权':   { trait: '受气主公', mechanism: '江东之主诅咒' },
  '周瑜':   { trait: '水火无敌·暴怒降寿', mechanism: '大都督诅咒' },
  '貂蝉':   { trait: '间谍·身不由己' },
  '陈宫':   { trait: '谋士·虫系宝可梦大师' },
  '赵云':   { trait: '忠勇无双' },
  '马超':   { trait: '西凉铁骑' },
  '黄忠':   { trait: '老当益壮' },
  '魏延':   { trait: '脑后有反骨' },
  '庞统':   { trait: '凤雏·黑暗兵法' },
  '姜维':   { trait: '天水麒麟儿' },
  '鲁肃':   { trait: '老实人·受气包' },
  '吕蒙':   { trait: '吴下阿蒙' },
  '陆逊':   { trait: '书生拜将' },
}

// ── 类型 ──
interface NarrativeBlock {
  text: string
  isScene?: boolean
  sceneTitle?: string
  isPlayerPov?: boolean
  streaming?: boolean  // 当前流式接收中（直出 + 光标）
  reveal?: boolean     // 最新完成块（打字机揭示一次）
}

// ── 状态 ──
const gameState = ref<GameState | null>(null)
const narrativeBlocks = ref<NarrativeBlock[]>([])
const options = ref<OptionSpec[]>([])
const freeInput = ref('')
const currentStreamText = ref('')
const showMemory = ref(false)
const errorMessage = ref('')   // 请求失败的用户可见错误提示
const stmList = computed<MemoryItem[]>(() => gameState.value?.memory?.stm ?? [])
const ltmList = computed<MemoryItem[]>(() => gameState.value?.memory?.ltm ?? [])
const pinItems = computed<MemoryItem[]>(() => {
  const pins = gameState.value?.memory?.pins ?? []
  const all = [...stmList.value, ...ltmList.value]
  const byId = new Map(all.map(m => [m.id, m]))
  return pins.map(id => byId.get(id)).filter(Boolean) as MemoryItem[]
})
const pinnedCount = computed(() => gameState.value?.memory?.pins?.length ?? 0)
const totalMemCount = computed(() => stmList.value.length + ltmList.value.length)
const started = ref(false)      // 首次流式开始后主界面常显（与 turn 解耦）
const lastSceneId = ref('')     // 场景门控：仅 scene_id 变化才触发加载器/分隔
const currentAtmo = ref('雨夜沉静')  // 当前氛围标签（驱动 AtmoBackground 切换）
const inkActive = ref(false)       // 墨染转场遮罩状态
const narrativeRef = ref<HTMLElement | null>(null)
// 8 PHASE 质量报告（最近一次校验结果）
const phaseReport = ref<PhaseReport | null>(null)
const showPhaseDetail = ref(false)
// 天意修正追踪
const correctedCount = computed(() => gameState.value?.corrected?.length ?? 0)
const lastCorrected = computed(() => {
  const c = gameState.value?.corrected
  return c?.length ? c[c.length - 1] : ''
})
// ── 五阶段动画序列 ──
type LoadPhase = 'cinematic' | 'thinking' | 'streaming' | 'memory' | 'character' | 'options'
const loadPhase = ref<LoadPhase>('cinematic')
const newMemCount = ref(0)       // 本轮新增记忆数（触发高亮）
const prevRelations = ref<Record<string, number>>({})  // 上轮关系值（计算 delta）
let loaderTimer: number | null = null
// 阶段切换定时器句柄：跨回合清理，防旧 timer 把新回合强置成 'options'
let phaseTimers: number[] = []

function schedulePhase(fn: () => void, ms: number) {
  const t = window.setTimeout(() => {
    phaseTimers = phaseTimers.filter(x => x !== t)
    fn()
  }, ms)
  phaseTimers.push(t)
  return t
}

function clearPhaseTimers() {
  phaseTimers.forEach(t => clearTimeout(t))
  phaseTimers = []
}

// ── 加载动画 ──
const loaderVisible = ref(true)
const loaderTitle = ref('三国')
const loaderChapterLabel = ref('184 年 · 颍川')
const loaderStatus = ref('')
// 三国化加载文案（随机轮换，随 CinematicLoader 台词轮播同步）
const LOADING_STATUS = [
  '乱世将起，风云际会……',
  '星夜赶路，千里可至……',
  '天意难测，人事难料……',
  '骄兵必败，哀兵必胜……',
  '苍天已死，黄金当立……',
  '生死不明，便是死了……',
]

// ── 初始化 ──
onMounted(() => {
  startGame()
  window.addEventListener('pointerdown', inkSplash, { passive: true })
})

onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', inkSplash)
})

async function startGame() {
  loaderVisible.value = true
  loadPhase.value = 'cinematic'
  loaderTitle.value = '三国'
  loaderChapterLabel.value = '184 年 · 颍川'
  loaderStatus.value = LOADING_STATUS[Math.floor(Math.random() * LOADING_STATUS.length)]
  gameState.value = null
  narrativeBlocks.value = []
  options.value = []
  currentStreamText.value = ''
  started.value = false
  lastSceneId.value = ''
  newMemCount.value = 0
  prevRelations.value = {}

  await playStep('', {} as GameState, 0, {
    onScene: (ev) => {
      // ① 场景就绪 → 切到思维链阶段（环境立即可见）
      lastSceneId.value = ev.scene.scene_id
      loaderTitle.value = ev.scene.title
      loaderChapterLabel.value = ev.scene.chapter_label
      if (ev.scene.atmo) currentAtmo.value = ev.scene.atmo
      hideLoader()
      started.value = true
      loadPhase.value = 'thinking'
    },
    onChunk: (text) => {
      if (!currentStreamText.value) {
        // ② 首 chunk → 思维链结束，剧情开始
        loadPhase.value = 'streaming'
        ensureStreamingBlock()
      }
      currentStreamText.value += text
      updateLastBlock()
    },
    onState: (state) => {
      // ③ 状态到达 → 记忆 & 人物更新
      const prev = gameState.value
      gameState.value = state
      // 计算新增记忆数
      const prevStm = prev?.memory?.stm?.length ?? 0
      const curStm = state?.memory?.stm?.length ?? 0
      newMemCount.value = Math.max(0, curStm - prevStm)
      // 记录上轮关系
      prevRelations.value = prev?.relations ? { ...prev.relations } : {}
      // 触发记忆阶段
      if (newMemCount.value > 0) {
        loadPhase.value = 'memory'
        // 短暂高亮后进入人物阶段
        schedulePhase(() => {
          loadPhase.value = 'character'
          // 人物阶段 → 选项阶段
          schedulePhase(() => {
            loadPhase.value = 'options'
          }, 600)
        }, 800)
      } else {
        loadPhase.value = 'character'
        schedulePhase(() => {
          loadPhase.value = 'options'
        }, 500)
      }
    },
    onOptions: (opts) => {
      options.value = opts
      // 不强制切 phase — 让 timeout 序列自然走到 'options'
    },
    onPhase: (ev) => { phaseReport.value = ev.report },
    onDone: () => {
      finalizeBlock()
      hideLoader()
      // 兜底：若 phase 序列卡住则 2s 后强制到 options
      schedulePhase(() => {
        if (loadPhase.value !== 'options' && loadPhase.value !== 'streaming') {
          loadPhase.value = 'options'
        }
      }, 2000)
    },
    onError: (msg) => {
      hideLoader()
      loaderVisible.value = false
      errorMessage.value = '世界短暂失序……请稍后重试'
      console.error(msg)
    },
  })
}

// 点击溅色：绑定当前背景(atmo)主题色——波/光/墨色随背景变化
const SPLASH_COLORS: Record<string, { edge: string; flash: string; drop: string }> = {
  '雨夜沉静': { edge: '#a8d4ec', flash: '#e2f3ff', drop: '#9cc8e2' },
  '荒野苍茫': { edge: '#dcbc90', flash: '#f7e8cd', drop: '#c6a475' },
  '战火远方': { edge: '#ff9a68', flash: '#ffddc5', drop: '#e87d50' },
  '洛阳暗巷': { edge: '#e6c97a', flash: '#fff0c4', drop: '#cfb060' },
  '水墨山岚': { edge: '#c6d6de', flash: '#f0f6f9', drop: '#a9bcc5' },
  '破晓行军': { edge: '#e6c97a', flash: '#fff0c4', drop: '#cfb060' },
  '竹林清幽': { edge: '#a7c997', flash: '#e8f2e1', drop: '#8ab07c' },
  '黄河怒涛': { edge: '#e7c27c', flash: '#fff3c8', drop: '#d4ac6e' },
  '帐中暖光': { edge: '#ffc65e', flash: '#fff3ce', drop: '#eab353' },
  '雪夜孤城': { edge: '#ecf5fb', flash: '#ffffff', drop: '#d2e4f0' },
  '星空原野': { edge: '#deeaf4', flash: '#f5faff', drop: '#c9d9e8' },
  '血色残阳': { edge: '#db6a50', flash: '#ffd5c5', drop: '#b24e3a' },
}

// ── 墨迹点击粒子（全局点击：水面细波扩散 + 中央落点微光 + 弧线飞溅的亮墨滴）──
function inkSplash(e: PointerEvent) {
  // 系统减弱动态效果时静默跳过：粒子是纯装饰，不值得触犯无障碍偏好
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  // 文本输入/文本域不触发（避免干扰打字）
  const t = e.target as HTMLElement | null
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA')) return
  const x = e.clientX
  const y = e.clientY
  // 当前背景主题色：溅色随 atmo 背景绑定
  const pal = SPLASH_COLORS[currentAtmo.value] ?? SPLASH_COLORS['雨夜沉静']

  // 节点自移除：animationend 主通道 + setTimeout 兜底（tab 隐藏/动画被抑制时也能清掉）
  const selfRemove = (node: HTMLElement, ms: number) => {
    node.addEventListener('animationend', () => node.remove())
    setTimeout(() => node.remove(), ms)
  }

  // 1) 水面细波：3 圈薄亮缘，指数外扩、先亮后淡（克制，不糊）
  const BASE = 220
  const WAVES = [
    { from: 0.1,  delay: 0,   dur: 0.8 },
    { from: 0.45, delay: 130, dur: 0.95 },
    { from: 0.75, delay: 260, dur: 1.1 },
  ]
  for (const w of WAVES) {
    const wave = document.createElement('span')
    wave.className = 'click-wave'
    wave.style.left = x + 'px'
    wave.style.top = y + 'px'
    wave.style.width = wave.style.height = BASE + 'px'
    wave.style.setProperty('--ws', String(w.from))
    wave.style.setProperty('--wdur', w.dur + 's')
    wave.style.setProperty('--wdelay', w.delay + 'ms')
    wave.style.setProperty('--s-edge', pal.edge)
    document.body.appendChild(wave)
    selfRemove(wave, w.delay + w.dur * 1000 + 200)
  }

  // 2) 中央落点微光：轻闪一下即散（不是浓晕）
  const flash = document.createElement('span')
  flash.className = 'click-flash'
  flash.style.left = x + 'px'
  flash.style.top = y + 'px'
  flash.style.setProperty('--s-flash', pal.flash)
  document.body.appendChild(flash)
  selfRemove(flash, 600)

  // 3) 墨滴飞溅：细而密的青白水珠，上抛弧线下落，微光晕精致克制
  for (let i = 0; i < 16; i++) {
    const d = document.createElement('span')
    d.className = 'click-drop'
    const angle = (Math.PI * 2 * i) / 16 + (Math.random() - 0.5) * 0.8
    const dist = 26 + Math.random() * 46
    // toFixed(2)：避免极小的 cos/sin 序列化成指数记法（1e-15px 是非法 CSS 长度，
    // 该声明会被丢弃，墨滴原地淡出而不飞）
    d.style.setProperty('--dx', `${(Math.cos(angle) * dist).toFixed(2)}px`)
    d.style.setProperty('--dy', `${(Math.sin(angle) * dist).toFixed(2)}px`)
    d.style.setProperty('--sag', `${dist * 0.35 + 6}px`)
    d.style.setProperty('--s-drop', pal.drop)
    d.style.left = x + 'px'
    d.style.top = y + 'px'
    d.style.width = d.style.height = `${3 + Math.random() * 3}px`
    d.style.background = `radial-gradient(circle at 35% 30%, color-mix(in srgb, white 40%, ${pal.drop}), ${pal.drop})`
    document.body.appendChild(d)
    selfRemove(d, 900)
  }
}

// ── 墨染转场（场景切换时触发）──
function triggerInk() {
  inkActive.value = true
  setTimeout(() => { inkActive.value = false }, 1200)
}

async function chooseOption(opt: OptionSpec) {
  // 粒子爆发需要 DOM 元素引用；用事件 target 获取
  await sendAction(opt.text, opt.tension)
}

async function submitFree() {
  const action = freeInput.value.trim()
  if (!action) return
  await sendAction(action, 0)
}

async function sendAction(action: string, tension: number) {
  clearPhaseTimers()   // 清除上一回合遗留的阶段切换 timer，防串回合
  const prevOptions = options.value
  options.value = []
  currentStreamText.value = ''
  started.value = true
  isStreaming.value = true
  newMemCount.value = 0

  await playStep(action, gameState.value ?? ({} as GameState), tension, {
    onChunk: (text) => {
      if (!currentStreamText.value) {
        hideLoader()
        loadPhase.value = 'streaming'
        ensureStreamingBlock()
      }
      currentStreamText.value += text
      updateLastBlock()
    },
    onScene: (ev) => {
      const scene = ev.scene as { music?: string; atmo?: string }
      if (ev.scene.scene_id !== lastSceneId.value) {
        // 真场景切换：定格旧块 → 插分隔 → 更新铭牌 → 墨染 → 氛围
        freezeLastBlock(false)
        narrativeBlocks.value.push({
          text: '',
          isScene: true,
          sceneTitle: `${ev.scene.chapter_label} · ${ev.scene.title}`,
        })
        lastSceneId.value = ev.scene.scene_id
        loaderTitle.value = ev.scene.title
        loaderChapterLabel.value = ev.scene.chapter_label
        loaderStatus.value = LOADING_STATUS[Math.floor(Math.random() * LOADING_STATUS.length)]
        triggerInk()
        showLoader(1800)
        loadPhase.value = 'thinking'
        // 场景切换时重置流式累积，防止旧场景文本串入新场景块
        currentStreamText.value = ''
        if (scene.music === 'guanyu') playGuanyu()
        if (scene.atmo) currentAtmo.value = scene.atmo
      } else {
        // 同场景：更新铭牌，思维链
        loaderTitle.value = ev.scene.title
        loaderChapterLabel.value = ev.scene.chapter_label
        loadPhase.value = 'thinking'
        if (scene.atmo) currentAtmo.value = scene.atmo
      }
    },
    onState: (state) => {
      const prev = gameState.value
      gameState.value = state
      const prevStm = prev?.memory?.stm?.length ?? 0
      const curStm = state?.memory?.stm?.length ?? 0
      newMemCount.value = Math.max(0, curStm - prevStm)
      prevRelations.value = prev?.relations ? { ...prev.relations } : {}
      if (newMemCount.value > 0) {
        loadPhase.value = 'memory'
        schedulePhase(() => {
          loadPhase.value = 'character'
          schedulePhase(() => { loadPhase.value = 'options' }, 600)
        }, 800)
      } else {
        loadPhase.value = 'character'
        schedulePhase(() => { loadPhase.value = 'options' }, 500)
      }
    },
    onOptions: (opts) => {
      options.value = opts
    },
    onPhase: (ev) => { phaseReport.value = ev.report },
    onDone: () => {
      finalizeBlock()
      hideLoader()
      schedulePhase(() => {
        if (loadPhase.value !== 'options' && loadPhase.value !== 'streaming') {
          loadPhase.value = 'options'
        }
      }, 2000)
    },
    onError: (msg) => {
      hideLoader()
      options.value = prevOptions   // 恢复上一回合选项
      isStreaming.value = false
      currentStreamText.value = ''
      loadPhase.value = 'options'   // 关键：错误后回到选项阶段，避免卡死在 streaming/thinking
      errorMessage.value = '世界短暂失序……请重试'
      console.error(msg)
    },
  })
}

/** 首 chunk：确保最后有一个 streaming 块接收流式文本（分隔块/静态块后追加） */
function ensureStreamingBlock() {
  const blocks = narrativeBlocks.value
  const last = blocks[blocks.length - 1]
  if (!last || last.isScene || !last.streaming) {
    blocks.push({ text: '', streaming: true })
  }
}

function updateLastBlock() {
  const blocks = narrativeBlocks.value
  for (let i = blocks.length - 1; i >= 0; i--) {
    const b = blocks[i]
    if (b.isScene) continue
    if (b.streaming) { b.text = currentStreamText.value; break }
    // 无 streaming 块（罕见）：追加
    blocks.push({ text: currentStreamText.value, streaming: true })
    break
  }
  scrollToBottom()
}

/** 定格流式块为完成态；reveal=true 时只让最新完成块跑打字机，其余定格静态 */
function freezeLastBlock(reveal: boolean) {
  const blocks = narrativeBlocks.value
  let target: NarrativeBlock | null = null
  for (let i = blocks.length - 1; i >= 0; i--) {
    const b = blocks[i]
    if (!b.isScene && b.streaming) { target = b; break }
  }
  if (target) {
    target.streaming = false
    if (reveal) {
      for (const b of blocks) if (b !== target) b.reveal = false
      target.reveal = true
    } else {
      target.reveal = false
    }
  }
}

function finalizeBlock() {
  isStreaming.value = false
  // streaming 态已用快速 StreamText 打完，不再设 reveal=true 触发二次打字
  freezeLastBlock(false)
  currentStreamText.value = ''
  scrollToBottom()
}

/** 加载器管理：显示带超时兜底，隐藏时清 timer（防竞态/黑屏卡死） */
function showLoader(dur = 2000) {
  loaderVisible.value = true
  if (loaderTimer) clearTimeout(loaderTimer)
  loaderTimer = window.setTimeout(() => {
    loaderVisible.value = false
    loaderTimer = null
  }, dur)
}
function hideLoader() {
  loaderVisible.value = false
  if (loaderTimer) { clearTimeout(loaderTimer); loaderTimer = null }
}

function scrollToBottom() {
  nextTick(() => {
    const el = narrativeRef.value
    if (!el) return
    // 仅在用户已接近底部时自动滚底，避免打断回读
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 120) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'auto' })
    }
  })
}

// ── 派生 ──
const eraLabel = computed(() => {
  const era = gameState.value?.era
  return era ? `${era.year} 年 · ${era.season}` : '184 年 · 春'
})
const eraChapter = computed(() => gameState.value?.era?.chapter ?? 'P1 黄金风起')

const characterRels = computed(() => gameState.value?.relations ?? {})
const trust = computed(() => gameState.value?.trust ?? {})

function relClass(v: number) {
  if (v >= 60) return 'rel-high'
  if (v >= 30) return 'rel-mid'
  return 'rel-low'
}
function trustClass(v: number) {
  if (v >= 60) return 'trust-high'
  if (v >= 30) return 'trust-mid'
  return 'trust-low'
}

function tensionClass(t: number) {
  if (t <= 30) return 'tension-low'    // 青=顺历史
  if (t <= 70) return 'tension-mid'    // 鎏金=局部
  return 'tension-high'                // 赤铁=硬干预
}

// ── 思维链阶段：从当前状态提取上下文数据 ──
const thinkingNpcList = computed(() => {
  const rels = gameState.value?.relations ?? {}
  return Object.entries(rels).sort((a, b) => b[1] - a[1]).slice(0, 5)
})
const thinkingStmCount = computed(() => gameState.value?.memory?.stm?.length ?? 0)
const thinkingLtmCount = computed(() => gameState.value?.memory?.ltm?.length ?? 0)
const thinkingPinCount = computed(() => gameState.value?.memory?.pins?.length ?? 0)
const thinkingForeshadowCount = computed(() => gameState.value?.foreshadowing?.length ?? 0)
const thinkingTension = computed(() => gameState.value?.tension ?? 0)

// PHASE 质量报告：是否有硬校验未通过
const hasPhaseWarnings = computed(() => {
  const llm = phaseReport.value?.llm
  if (!llm) return false
  const hardPhases = ['p0', 'p1', 'p2', 'p3', 'p4', 'p5']
  return hardPhases.some(p => llm[p] && !llm[p].pass)
})

// ── PIN 记忆 ──
function isPinned(id: string) {
  return gameState.value?.memory?.pins?.includes(id) ?? false
}
async function togglePin(id: string) {
  // PIN 状态由前端维护（后续 Phase 4 回传持久化）
  const gs = gameState.value
  if (!gs) return
  const pins = [...(gs.memory?.pins ?? [])]
  const idx = pins.indexOf(id)
  if (idx >= 0) pins.splice(idx, 1)
  else if (pins.length < 5) pins.push(id)
  gs.memory = { ...gs.memory, pins }
  gameState.value = { ...gs }
}

function goBack() {
  router.push('/')
}

/** 错误重试：开局失败→重开；回合中失败→重发上回合动作 */
function retryAfterError() {
  errorMessage.value = ''
  if (gameState.value === null) {
    startGame()
  } else {
    sendAction(freeInput.value.trim() || '继续前行', 0)
  }
}

onBeforeUnmount(() => {
  if (loaderTimer) { clearTimeout(loaderTimer); loaderTimer = null }
})
</script>

<style scoped>
.play-page {
  width: 100%;
  height: 100%;
  /* 背景由 AtmoBackground 组件提供（水墨图 + 光晕 + 毛玻璃） */
  background: #020203;  /* 兜底底色 */
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 错误提示横幅 */
.error-banner {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 120;
  display: flex;
  align-items: center;
  gap: 14px;
  background: rgba(192, 64, 48, 0.15);
  border: 1px solid rgba(192, 64, 48, 0.4);
  color: #f1f5f9;
  padding: 10px 18px;
  border-radius: 10px;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.4);
}
.error-text {
  font-size: 0.82rem;
  letter-spacing: 0.04em;
  color: rgba(248, 250, 252, 0.9);
}
.error-retry {
  background: rgba(202, 138, 4, 0.2);
  border: 1px solid rgba(202, 138, 4, 0.5);
  color: #ca8a04;
  border-radius: 6px;
  padding: 4px 14px;
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  transition: all 0.25s ease;
}
.error-retry:hover {
  background: rgba(202, 138, 4, 0.35);
}
.error-fade-enter-active,
.error-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.error-fade-enter-from,
.error-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-8px);
}

/* 返回按钮 */
.back-btn {
  position: absolute;
  top: 20px;
  left: 20px;
  z-index: 50;
  background: rgba(15, 15, 35, 0.6);
  border: 1px solid rgba(202, 138, 4, 0.3);
  color: #ca8a04;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.3s ease;
}
.back-btn:hover {
  background: rgba(202, 138, 4, 0.15);
  border-color: rgba(202, 138, 4, 0.7);
}

/* 主界面 */
.play-main {
  flex: 1;
  min-height: 0;  /* 关键：flex 子项默认 min-height:auto 会被内容撑高，overflow:hidden 裁掉而非滚动 */
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 2;
}

/* ── 章节铭牌 ── */
.era-banner {
  padding: 30px 24px 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  position: relative;
}
.era-banner::after {
  content: '';
  position: absolute;
  bottom: 0; left: 50%; transform: translateX(-50%);
  width: 60px; height: 1px;
  background: radial-gradient(circle, rgba(202, 138, 4, 0.25), transparent);
}
.era-label {
  font-size: 0.75rem;
  letter-spacing: 0.45em;
  color: rgba(202, 138, 4, 0.6);
  text-transform: uppercase;
}
.era-chapter {
  font-family: var(--font-display);
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: 0.3em;
  color: #f1f5f9;
  text-shadow: 0 0 30px rgba(202, 138, 4, 0.15);
}
.era-goldline {
  width: 120px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(202, 138, 4, 0.4), transparent);
}

/* 8 PHASE 质量指示灯 */
.phase-indicator {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: rgba(90, 122, 106, 0.5);    /* 青铜绿 */
  font-size: 0.6rem;
  cursor: pointer;
  padding: 4px 6px;
  transition: color 0.3s, text-shadow 0.3s;
}
.phase-indicator:hover {
  color: rgba(90, 122, 106, 0.85);
  text-shadow: 0 0 6px rgba(90, 122, 106, 0.3);
}
.phase-indicator.phase-warn {
  color: rgba(192, 64, 48, 0.7);     /* 校验未过→赤铁色 */
}

/* 天意修正徽章 */
.corrected-badge {
  position: absolute;
  right: 10px;
  top: calc(50% - 14px);
  font-size: 0.55rem;
  letter-spacing: 0.1em;
  color: rgba(192, 64, 48, 0.55);
  background: rgba(192, 64, 48, 0.08);
  border: 1px solid rgba(192, 64, 48, 0.15);
  border-radius: 8px;
  padding: 1px 8px;
  cursor: help;
}

/* PHASE 详情面板 */
.phase-detail {
  position: absolute;
  right: 10px;
  top: 100%;
  width: 260px;
  background: rgba(10, 10, 18, 0.96);
  border: 1px solid rgba(90, 122, 106, 0.2);
  border-radius: 10px;
  padding: 10px 12px;
  z-index: 25;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.5);
  animation: phase-in 0.25s ease both;
}
@keyframes phase-in {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}
.pd-title {
  font-size: 0.6rem;
  letter-spacing: 0.25em;
  text-transform: uppercase;
  color: rgba(90, 122, 106, 0.55);
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.06);
}
.pd-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.68rem;
  padding: 2px 0;
}
.pd-phase {
  color: rgba(202, 138, 4, 0.5);
  font-weight: 500;
  min-width: 24px;
}
.pd-status {
  font-size: 0.6rem;
  min-width: 16px;
}
.pd-pass { color: #4a9ea0; }
.pd-fail { color: #c04030; }
.pd-reason {
  color: rgba(148, 163, 184, 0.5);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 叙事区 */
.narrative-area {
  flex: 1;
  min-height: 0;  /* 允许收缩，配合 overflow-y:auto 产生滚动 */
  overflow-y: auto;
  padding: 24px 10%;
  max-width: 860px;        /* 舒适阅读宽度（~75 字/行） */
  margin: 0 auto;          /* 居中文本列 */
  width: 100%;
  /* 不加 scroll-behavior:smooth —— 逐 chunk 自动滚底会反复重启动画导致抖动 */
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

/* 流式光标 */
.live-caret {
  display: inline-block;
  width: 2px;
  vertical-align: text-bottom;
  color: #ca8a04;
  text-shadow: 0 0 8px rgba(202, 138, 4, 0.7);
  animation: caret-blink 0.9s step-end infinite;
  margin-left: 1px;
}
@keyframes caret-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
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

/* ── 选项区 ── */
.choice-area {
  padding: 16px 10% 28px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 1600px;
  margin: 0 auto;
  width: 100%;
}
.choice-btn {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: rgba(15, 15, 30, 0.55);
  border: 1px solid;
  border-left: 3px solid;
  border-radius: 0 10px 10px 0;
  padding: 8px 14px;
  cursor: pointer;
  text-align: left;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  color: #f1f5f9;
  font-family: var(--font-body);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  position: relative;
  overflow: hidden;
  animation: option-enter 0.35s cubic-bezier(0.16, 1, 0.3, 1) both;
}
.choice-btn:nth-child(1) { animation-delay: 0.04s; }
.choice-btn:nth-child(2) { animation-delay: 0.10s; }
.choice-btn:nth-child(3) { animation-delay: 0.16s; }
@keyframes option-enter {
  from { opacity: 0; transform: translateX(10px); }
  to   { opacity: 1; transform: translateX(0); }
}
.choice-btn:hover {
  background: rgba(15, 15, 35, 0.7);
  transform: translateX(3px);
}
.choice-btn:active {
  transform: scale(0.98);
  transition-duration: 0.08s;
}
.choice-text { flex: 1; font-size: 0.9rem; line-height: 1.4; }
.choice-effect {
  font-size: 0.7rem;
  color: rgba(202, 168, 100, 0.78);   /* 暖金 — 后果说明，暗底清晰可读 */
  max-width: 35%;
  text-align: right;
  line-height: 1.35;
  flex-shrink: 0;
}

/* tension 三色：左竖线 + 细边框 */
.tension-low  { border-color: rgba(74, 158, 160, 0.2); border-left-color: #4a9ea0; }
.tension-low:hover  { border-color: rgba(74, 158, 160, 0.5); background: rgba(74, 158, 160, 0.06); }
.tension-mid  { border-color: rgba(232, 168, 56, 0.2); border-left-color: #e8a838; }
.tension-mid:hover  { border-color: rgba(232, 168, 56, 0.5); background: rgba(232, 168, 56, 0.06); }
.tension-high { border-color: rgba(192, 64, 48, 0.2); border-left-color: #c04030; }
.tension-high:hover { border-color: rgba(192, 64, 48, 0.5); background: rgba(192, 64, 48, 0.06); }

/* ── 自由输入 ── */
.free-row {
  display: flex;
  gap: 10px;
  margin-top: 6px;
}
.free-input {
  flex: 1;
  background: rgba(15, 15, 30, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 10px;
  padding: 10px 14px;
  color: #e2e8f0;
  font-family: var(--font-body);
  font-size: 0.88rem;
  transition: border-color 0.3s, box-shadow 0.3s;
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}
.free-input::placeholder { color: rgba(148, 163, 184, 0.35); }
.free-input:focus {
  outline: none;
  border-color: rgba(202, 138, 4, 0.5);
  box-shadow: 0 0 14px rgba(202, 138, 4, 0.06);
}
.free-submit {
  background: rgba(202, 138, 4, 0.12);
  border: 1px solid rgba(202, 138, 4, 0.35);
  color: #ca8a04;
  border-radius: 10px;
  padding: 0 20px;
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 0.85rem;
  letter-spacing: 0.05em;
  transition: all 0.25s ease;
}
.free-submit:disabled { opacity: 0.3; cursor: default; }
.free-submit:not(:disabled):hover { background: rgba(202, 138, 4, 0.22); border-color: rgba(202, 138, 4, 0.6); }

/* ── 角色状态卡 ── */
.character-panel {
  position: fixed;
  right: 20px;
  top: 50%;
  transform: translateY(-50%);
  width: 170px;
  background: rgba(10, 10, 18, 0.82);
  border: 1px solid rgba(202, 138, 4, 0.18);
  border-radius: 14px;
  padding: 14px 12px;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  z-index: 20;
  animation: panel-slide-in 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
  box-shadow: 0 0 30px rgba(202, 138, 4, 0.04), inset 0 1px 0 rgba(255, 255, 255, 0.03);
}
@keyframes panel-slide-in {
  from { opacity: 0; transform: translateY(-50%) translateX(12px); }
  to   { opacity: 1; transform: translateY(-50%) translateX(0); }
}
.cp-title {
  font-size: 0.65rem;
  letter-spacing: 0.35em;
  text-transform: uppercase;
  color: rgba(202, 138, 4, 0.55);
  margin-bottom: 12px;
  text-align: center;
}
.character-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.06);
}
.character-chip:last-child { border-bottom: none; }
.chip-avatar {
  width: 24px; height: 24px;
  border-radius: 50%;
  background: rgba(202, 138, 4, 0.12);
  color: rgba(202, 138, 4, 0.7);
  font-size: 0.6rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.chip-info { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.chip-name {
  font-size: 0.8rem; color: #f1f5f9; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.chip-rels { display: flex; gap: 8px; font-size: 0.65rem; }
.chip-trait {
  font-size: 0.6rem;
  color: rgba(202, 138, 4, 0.55);
  font-style: italic;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chip-mech {
  font-size: 0.55rem;
  color: rgba(90, 122, 106, 0.5);    /* 青铜绿 — 机制标注 */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  letter-spacing: 0.02em;
}
.chip-rel, .chip-trust {
  display: inline-flex; align-items: center; gap: 2px;
}
.rel-high, .trust-high { color: #4a9ea0; }
.rel-mid,  .trust-mid  { color: #e8a838; }
.rel-low,  .trust-low  { color: #c04030; }

/* ── 记忆抽屉（三段式：PIN / LTM / STM）── */
.memory-toggle {
  position: fixed;
  right: 20px;
  top: 14px;
  background: rgba(10, 10, 18, 0.82);
  border: 1px solid rgba(202, 138, 4, 0.25);
  color: #ca8a04;
  border-radius: 20px;
  padding: 7px 16px;
  font-size: 0.75rem;
  cursor: pointer;
  z-index: 30;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  transition: all 0.3s ease;
  letter-spacing: 0.05em;
  display: flex;
  align-items: center;
  gap: 8px;
}
.mt-counts {
  font-size: 0.62rem;
  color: rgba(202, 168, 100, 0.6);
  letter-spacing: 0.03em;
}
.memory-toggle:hover {
  background: rgba(202, 138, 4, 0.12);
  border-color: rgba(202, 138, 4, 0.5);
}
.memory-drawer {
  position: fixed;
  right: 20px;
  top: 50px;
  width: 420px;
  max-width: calc(100vw - 40px);
  height: 70vh;
  max-height: calc(100vh - 70px);
  background: rgba(10, 10, 18, 0.94);
  border: 1px solid rgba(202, 138, 4, 0.2);
  border-radius: 14px;
  padding: 16px 18px;
  z-index: 30;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
  animation: drawer-slide-down 0.3s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes drawer-slide-down {
  from { opacity: 0; transform: translateY(-8px) scale(0.97); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
.md-header {
  font-size: 0.62rem;
  letter-spacing: 0.25em;
  color: rgba(202, 138, 4, 0.5);
  text-align: center;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(202, 138, 4, 0.12);
  flex-shrink: 0;
}
.md-section {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
  margin-bottom: 10px;
  padding-right: 4px;
}
.md-section:last-child { margin-bottom: 0; }
/* 各板块滚动条 */
.md-section::-webkit-scrollbar { width: 3px; }
.md-section::-webkit-scrollbar-thumb { background: rgba(202, 138, 4, 0.15); border-radius: 3px; }
.md-section-title {
  font-size: 0.62rem;
  letter-spacing: 0.2em;
  color: rgba(202, 168, 100, 0.55);
  margin-bottom: 6px;
  padding-left: 2px;
}
.md-empty-row {
  font-size: 0.7rem;
  color: rgba(148, 163, 184, 0.25);
  padding: 4px 8px;
  font-style: italic;
}
.memory-row {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 5px 4px;
  font-size: 0.78rem;
  color: rgba(226, 232, 240, 0.85);
  line-height: 1.5;
  border-bottom: 1px solid rgba(148, 163, 184, 0.04);
  animation: mem-row-enter 0.25s ease both;
}
.memory-row:nth-child(2) { animation-delay: 0.03s; }
.memory-row:nth-child(3) { animation-delay: 0.06s; }
.memory-row:nth-child(4) { animation-delay: 0.09s; }
.memory-row:nth-child(5) { animation-delay: 0.12s; }
.memory-row:nth-child(6) { animation-delay: 0.15s; }
@keyframes mem-row-enter {
  from { opacity: 0; transform: translateX(4px); }
  to   { opacity: 1; transform: translateX(0); }
}
.mr-num {
  font-size: 0.55rem;
  color: rgba(202, 168, 100, 0.3);
  min-width: 14px;
  flex-shrink: 0;
  text-align: right;
  padding-top: 1px;
}
.mr-time {
  font-size: 0.58rem;
  color: rgba(90, 122, 106, 0.4);
  white-space: nowrap;
  flex-shrink: 0;
  min-width: 52px;
  max-width: 64px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mr-scene {
  font-size: 0.58rem;
  color: rgba(90, 122, 106, 0.35);
  white-space: nowrap;
  flex-shrink: 0;
  min-width: 48px;
  max-width: 72px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mr-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.mi-pin {
  background: none;
  border: none;
  font-size: 0.72rem;
  cursor: pointer;
  opacity: 0.3;
  flex-shrink: 0;
  transition: opacity 0.2s;
  padding: 1px 2px;
}
.mi-pin:hover { opacity: 0.7; }
.mi-pin.pinned { opacity: 1; }

/* ── 墨染转场遮罩（场景切换时 1.2s 墨迹扩散）── */
.ink-transition {
  position: fixed;
  inset: 0;
  z-index: 50;
  pointer-events: none;
  opacity: 0;
  background: radial-gradient(circle at center, transparent 0%, rgba(2, 2, 3, 1) 100%);
  transition: none;
}
.ink-transition.active {
  opacity: 1;
  animation: ink-spread 1.2s cubic-bezier(0.4, 0, 0.2, 1) both;
}
@keyframes ink-spread {
  0%   { clip-path: circle(0% at 50% 50%); }
  60%  { clip-path: circle(100% at 50% 50%); }
  100% { clip-path: circle(0% at 50% 50%); }
}

/* ── ① 思维链阶段 ── */
.thinking-phase {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  padding: 40px 0 50px;
  animation: think-enter 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes think-enter {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}
.think-header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.think-icon {
  font-size: 1.1rem;
  color: rgba(202, 138, 4, 0.6);
  animation: think-rotate 3s linear infinite;
}
@keyframes think-rotate {
  to { transform: rotate(360deg); }
}
.think-title {
  font-family: var(--font-display);
  font-size: 1.1rem;
  letter-spacing: 0.25em;
  color: rgba(202, 138, 4, 0.7);
}
.think-detail {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  max-width: 480px;
  padding: 16px 20px;
  background: rgba(10, 10, 18, 0.5);
  border: 1px solid rgba(202, 138, 4, 0.12);
  border-radius: 12px;
}
.think-row {
  display: flex;
  gap: 12px;
  font-size: 0.82rem;
  line-height: 1.5;
}
.think-label {
  color: rgba(202, 138, 4, 0.45);
  min-width: 36px;
  letter-spacing: 0.08em;
  flex-shrink: 0;
}
.think-val {
  color: rgba(226, 232, 240, 0.75);
}
.think-npc {
  white-space: nowrap;
}
.think-npc-rel {
  font-size: 0.62rem;
  margin-left: 2px;
}
.think-foreshadow {
  color: rgba(192, 64, 48, 0.55);
}
.think-pulse {
  display: flex;
  gap: 12px;
  margin-top: 4px;
}
.think-ember {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: rgba(202, 138, 4, 0.5);
  animation: think-ember-pulse 1.4s ease-in-out infinite;
}
@keyframes think-ember-pulse {
  0%, 100% { opacity: 0.2; transform: scale(0.7); }
  50%      { opacity: 1;   transform: scale(1.2); }
}

/* ── ③ 记忆浮现高亮 ── */
.memory-toggle.mem-reveal {
  animation: mem-glow 0.8s ease-in-out;
  border-color: rgba(202, 138, 4, 0.65) !important;
  box-shadow: 0 0 18px rgba(202, 138, 4, 0.2);
}
@keyframes mem-glow {
  0%   { box-shadow: 0 0 0px rgba(202, 138, 4, 0); }
  50%  { box-shadow: 0 0 24px rgba(202, 138, 4, 0.35); }
  100% { box-shadow: 0 0 8px rgba(202, 138, 4, 0.12); }
}

/* ── ④ 人物状态浮现高亮 ── */
.character-panel.cp-reveal {
  animation: cp-glow 0.6s ease-in-out;
  border-color: rgba(202, 138, 4, 0.45) !important;
  box-shadow: 0 0 22px rgba(202, 138, 4, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.05);
}
@keyframes cp-glow {
  0%   { box-shadow: 0 0 0px rgba(202, 138, 4, 0); }
  50%  { box-shadow: 0 0 30px rgba(202, 138, 4, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.08); }
  100% { box-shadow: 0 0 30px rgba(202, 138, 4, 0.04), inset 0 1px 0 rgba(255, 255, 255, 0.03); }
}

/* ── ⑤ 选项浮现 ── */
.choice-reveal .choice-btn {
  animation: option-enter 0.35s cubic-bezier(0.16, 1, 0.3, 1) both;
}


/* 响应式 */
@media (max-width: 768px) {
  .narrative-area { padding: 16px 5%; }
  .choice-area { padding: 12px 5% 24px; }
  .character-panel { display: none; }
}

/* prefers-reduced-motion：关闭所有动画 */
@media (prefers-reduced-motion: reduce) {
  .narrative-block,
  .choice-btn {
    animation: none !important;
  }
  .choice-btn:active {
    transform: none !important;
  }
}
</style>

<!-- 点击墨迹粒子：元素 append 到 document.body，scoped 会给类加 data-v 属性导致匹配不到 → 必须非 scoped -->
<style>
.click-wave {
  position: fixed;
  left: 0; top: 0;
  pointer-events: none;
  z-index: 99;
  border-radius: 50%;
  transform: translate(-50%, -50%) scale(var(--ws));
  opacity: 0;
  background: radial-gradient(
    circle,
    transparent 56%,
    color-mix(in srgb, var(--s-edge, #a8d4ec) 45%, transparent) 66%, /* 波峰亮缘（薄而克制） */
    color-mix(in srgb, var(--s-edge, #a8d4ec) 13%, transparent) 78%, /* 波后尾迹（更薄） */
    transparent 90%
  );
  animation:
    wave-grow var(--wdur, 0.9s) cubic-bezier(0.16, 1, 0.3, 1) var(--wdelay, 0ms) both,
    wave-fade var(--wdur, 0.9s) cubic-bezier(0.3, 0, 0.55, 1) var(--wdelay, 0ms) both;
}
@keyframes wave-grow {
  0%   { transform: translate(-50%, -50%) scale(var(--ws)); }
  100% { transform: translate(-50%, -50%) scale(1); }
}
@keyframes wave-fade {
  0%   { opacity: 0.6; }
  100% { opacity: 0; }
}

/* 中央落点微光：小、快、轻，一闪即散 */
.click-flash {
  position: fixed;
  transform: translate(-50%, -50%);
  z-index: 98;
  pointer-events: none;
  width: 6px; height: 6px;
  border-radius: 50%;
  background: radial-gradient(circle,
    color-mix(in srgb, var(--s-flash, #e2f3ff) 90%, transparent) 0%,
    color-mix(in srgb, var(--s-flash, #e2f3ff) 28%, transparent) 45%,
    transparent 72%);
  animation: flash-pop 0.4s ease-out both;
}
@keyframes flash-pop {
  0%   { width: 5px; height: 5px; opacity: 0.9; }
  100% { width: 24px; height: 24px; opacity: 0; }
}

/* 亮墨滴：径向渐变模拟受光的小液滴 + 微光晕；弧线飞行（先上抛后下落） */
.click-drop {
  position: fixed;
  z-index: 100;
  pointer-events: none;
  border-radius: 50%;
  box-shadow: 0 0 5px 0.5px color-mix(in srgb, var(--s-drop, #9cc8e2) 45%, transparent);
  animation: drop-fly 0.65s cubic-bezier(0.16, 0.55, 0.45, 1) both;
}
@keyframes drop-fly {
  0%   { transform: translate(0, 0) scale(1); opacity: 1; }
  50%  { transform: translate(calc(var(--dx) * 0.5), calc(var(--dy) * 0.5 - var(--sag))) scale(0.75); opacity: 0.95; }
  100% { transform: translate(var(--dx), calc(var(--dy) + var(--sag) * 0.6)) scale(0.12); opacity: 0; }
}
</style>
