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

    <!-- 开场（IntroOverlay 自管理：高清墨彩视频背景 + 标题 + 穿越旁白 + 规则） -->
    <transition name="intro-fade">
      <IntroOverlay v-if="showIntro" @begin="beginAdventure" @back="goBack" />
    </transition>

    <!-- 返回星图 -->
    <button class="back-btn" @click="goBack" aria-label="返回星图">←</button>

    <!-- 世界简报（自由沙盒：到达新地点/周期时弹出未读强相关事件） -->
    <WorldBriefing :events="worldEvents" @read="markBriefingRead" />

    <!-- 加载动画（开局/场景切换） -->
    <CinematicLoader
      :show="loaderVisible"
      :title="loaderTitle"
      :chapter-label="loaderChapterLabel"
      :status-text="loaderStatus"
    />

    <!-- 主界面（started 后常显；加载器为 fixed 遮罩盖在其上，不隐藏主界面） -->
    <div class="play-main" v-show="started">
      <!-- 章节铭牌（时代 + 世界日期 + 8 PHASE 指示灯 + 天意修正） -->
      <EraBanner
        :era-label="eraLabel"
        :era-chapter="eraChapter"
        :world-date-label="worldDateLabel"
        :phase-report="phaseReport"
        :corrected-count="correctedCount"
        :last-corrected="lastCorrected"
      />

      <!-- 叙事区（思维链 + 叙事块 + 流式指示，内部自滚动） -->
      <NarrativeArea
        :show-thinking="loadPhase === 'thinking'"
        :thinking-chapter="loaderChapterLabel"
        :thinking-title="loaderTitle"
        :npc-list="thinkingNpcList"
        :stm-count="thinkingStmCount"
        :ltm-count="thinkingLtmCount"
        :pin-count="thinkingPinCount"
        :foreshadow-count="thinkingForeshadowCount"
        :tension="thinkingTension"
        :blocks="narrativeBlocks"
        :is-streaming="isStreaming"
        :current-stream-text="currentStreamText"
      />

      <!-- 选项区（仅选项阶段显示） -->
      <ChoiceArea
        v-if="loadPhase === 'options'"
        v-model="freeInput"
        :options="options"
        @choose="chooseOption"
        @fallback="sendAction('继续前行', 0)"
        @submit="submitFree"
      />

      <!-- 角色状态卡（仅在场有人时显示） -->
      <CharacterPanel
        v-if="Object.keys(characterRels).length > 0"
        :rels="characterRels"
        :trust="trust"
        :reveal="loadPhase === 'character'"
      />

      <!-- 记忆抽屉（三段式：PIN / LTM / STM） -->
      <MemoryDrawer
        :stm-list="stmList"
        :ltm-list="ltmList"
        :pin-items="pinItems"
        :pins="pins"
        :pinned-count="pinnedCount"
        :total-mem-count="totalMemCount"
        :reveal="loadPhase === 'memory'"
        @toggle-pin="togglePin"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
// PlayPage —— 叙事游戏主界面（编排层）
// 职责：SSE 接线（playStep 的 7 个回调）+ 五阶段动画时序 + gameState/选项/关系等状态编排。
// 展示块已拆分为子组件（IntroOverlay/EraBanner/NarrativeArea/ChoiceArea/CharacterPanel/MemoryDrawer），
// 叙事流式块状态与点击墨迹粒子抽为 composable（useNarrativeBlocks/useInkSplash）。
import { ref, computed, onMounted, onBeforeUnmount, inject } from 'vue'
import { useRouter } from 'vue-router'
import AtmoBackground from '../components/AtmoBackground.vue'
import ParticleLayer from '../components/ParticleLayer.vue'
import IntroOverlay from '../components/IntroOverlay.vue'
import WorldBriefing from '../components/WorldBriefing.vue'
import CinematicLoader from '../components/CinematicLoader.vue'
import EraBanner from '../components/EraBanner.vue'
import NarrativeArea from '../components/NarrativeArea.vue'
import ChoiceArea from '../components/ChoiceArea.vue'
import CharacterPanel from '../components/CharacterPanel.vue'
import MemoryDrawer from '../components/MemoryDrawer.vue'
import { usePlaySse } from '../composables/usePlaySse'
import { useNarrativeBlocks } from '../composables/useNarrativeBlocks'
import { useInkSplash } from '../composables/useInkSplash'
import type { GameState, OptionSpec, MemoryItem, PhaseReport } from '../types/play'

const router = useRouter()
const { playStep, isStreaming } = usePlaySse()
const playGuanyu = inject<() => void>('playGuanyu', () => {})

// ── 叙事流式块（composable 抽离）──
const { narrativeBlocks, currentStreamText, ensureStreamingBlock, updateLastBlock, freezeLastBlock, finalizeBlock, resetBlocks } = useNarrativeBlocks()

// ── 类型 ──
type LoadPhase = 'cinematic' | 'thinking' | 'streaming' | 'memory' | 'character' | 'options'

// ── 状态 ──
const gameState = ref<GameState | null>(null)
const options = ref<OptionSpec[]>([])
const freeInput = ref('')
const errorMessage = ref('')   // 请求失败的用户可见错误提示
const showIntro = ref(true)    // 开场叙述页（IntroOverlay）
const started = ref(false)     // 首次流式开始后主界面常显（与 turn 解耦）
const lastSceneId = ref('')    // 场景门控：仅 scene_id 变化才触发加载器/分隔
const currentAtmo = ref('雨夜沉静')  // 当前氛围标签（驱动 AtmoBackground 切换）
const inkActive = ref(false)       // 墨染转场遮罩状态

// ── 点击墨迹粒子（composable 抽离；getter 懒取 currentAtmo，需在其后声明）──
const { inkSplash } = useInkSplash(() => currentAtmo.value)
// 8 PHASE 质量报告（最近一次校验结果）
const phaseReport = ref<PhaseReport | null>(null)
// 天意修正追踪
const correctedCount = computed(() => gameState.value?.corrected?.length ?? 0)
const lastCorrected = computed(() => {
  const c = gameState.value?.corrected
  return c?.length ? c[c.length - 1] : ''
})

// ── 记忆派生 ──
const stmList = computed<MemoryItem[]>(() => gameState.value?.memory?.stm ?? [])
const ltmList = computed<MemoryItem[]>(() => gameState.value?.memory?.ltm ?? [])
const pinItems = computed<MemoryItem[]>(() => {
  const pins = gameState.value?.memory?.pins ?? []
  const all = [...stmList.value, ...ltmList.value]
  const byId = new Map(all.map(m => [m.id, m]))
  return pins.map(id => byId.get(id)).filter(Boolean) as MemoryItem[]
})
const pins = computed(() => gameState.value?.memory?.pins ?? [])
const pinnedCount = computed(() => gameState.value?.memory?.pins?.length ?? 0)
const totalMemCount = computed(() => stmList.value.length + ltmList.value.length)

// ── 五阶段动画序列 ──
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

// ── 生命周期 ──
onMounted(() => {
  window.addEventListener('pointerdown', inkSplash, { passive: true })
})
onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', inkSplash)
  if (loaderTimer) { clearTimeout(loaderTimer); loaderTimer = null }
})

// ── 开局 ──
function beginAdventure() {
  showIntro.value = false
  startGame()
}

async function startGame() {
  loaderVisible.value = true
  loadPhase.value = 'cinematic'
  loaderTitle.value = '三国'
  loaderChapterLabel.value = '184 年 · 颍川'
  loaderStatus.value = LOADING_STATUS[Math.floor(Math.random() * LOADING_STATUS.length)]
  gameState.value = null
  resetBlocks()
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

// ── 行动 ──
function chooseOption(opt: OptionSpec) {
  sendAction(opt.text, opt.tension)
}

function submitFree() {
  const action = freeInput.value.trim()
  if (!action) return
  sendAction(action, 0)
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

// ── 墨染转场（场景切换时触发）──
function triggerInk() {
  inkActive.value = true
  setTimeout(() => { inkActive.value = false }, 1200)
}

// ── 派生 ──
const eraLabel = computed(() => {
  const era = gameState.value?.era
  return era ? `${era.year} 年 · ${era.season}` : '184 年 · 春'
})
const eraChapter = computed(() => gameState.value?.era?.chapter ?? 'P1 黄金风起')

// ── 自由沙盒：世界日期显示（取代旧世界时钟时节标签）──
const worldDateLabel = computed(() => {
  const wd = gameState.value?.world_date
  if (!wd) return ''
  const day = Number(wd.day)
  const dayText = Number.isInteger(day) ? `${day}日` : `初${day >= 15 ? '二' : '一'}`
  return `${wd.year}年${wd.month}月${dayText}`
})

// ── 自由沙盒：世界事件队列（简报用）──
const worldEvents = computed(() => gameState.value?.world_events ?? [])
function markBriefingRead() {
  // 简报已读：标记 seen（前端维护；后端下次快照持久化）
  const gs = gameState.value
  if (!gs?.world_events) return
  gs.world_events = gs.world_events.map(e => e.seen ? e : { ...e, seen: true })
  gameState.value = { ...gs }
}

const characterRels = computed(() => gameState.value?.relations ?? {})
const trust = computed(() => gameState.value?.trust ?? {})

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

// ── PIN 记忆 ──
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

/* 墨染转场遮罩（场景切换时 1.2s 墨迹扩散） */
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
</style>
