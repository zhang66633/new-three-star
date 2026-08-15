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

    <!-- 断点续玩确认层（有存档时取代开场：继续历险 / 新开历险） -->
    <transition name="resume-fade">
      <div v-if="resumeDialog" class="resume-dialog">
        <div class="resume-title">行者归位</div>
        <div class="resume-sub">你曾在此世留下足迹，要接续这段历险吗？</div>
        <div v-if="resumeDateLabel" class="resume-meta">{{ resumeDateLabel }}</div>
        <div class="resume-actions">
          <button class="resume-btn resume-continue" @click="resumeGame()">继续历险</button>
          <button class="resume-btn resume-new" @click="startNewAdventure">新开历险</button>
        </div>
      </div>
    </transition>

    <!-- 死亡回档层（三属性同时极端 → 读档最近快照） -->
    <transition name="resume-fade">
      <div v-if="deadDialog" class="resume-dialog death-dialog">
        <div class="resume-title">此身已逝</div>
        <div class="resume-sub">油尽灯枯，魂归长夜——但你留下的足迹仍在世间。</div>
        <div class="resume-actions">
          <button class="resume-btn resume-continue" @click="reloadFromDeath">回到此前</button>
        </div>
      </div>
    </transition>

    <!-- 操作引导（首次进入显示一次） -->
    <OperationGuide v-if="opsGuideVisible && started && !showIntro" @close="closeOpsGuide" />

    <!-- 返回星图 -->
    <button class="back-btn" @click="goBack" aria-label="返回星图">←</button>

    <!-- 世界简报（自由沙盒：先出简报后进场景叙事；SSE briefing 事件驱动，受控弹出） -->
    <WorldBriefing :visible="briefingVisible" :events="briefingEvents" :briefing="briefingText" @read="closeBriefing" />

    <!-- 成就解锁提示（临时浮层） -->
    <AchievementToast :achievements="newAchToasts" />

    <!-- 加载动画（开局/跨章节场景切换） -->
    <CinematicLoader
      :show="loaderVisible"
      :title="loaderTitle"
      :chapter-label="loaderChapterLabel"
      :status-text="loaderStatus"
    />

    <!-- 轻过渡铭牌（同章内移动/推进：顶部淡入，无全屏） -->
    <transition name="lite-fade">
      <div v-if="liteBannerText" class="lite-banner">{{ liteBannerText }}</div>
    </transition>

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

      <!-- 主菜单页（全屏 tab 切换：地图/档案/在场/天下事/记忆） -->
      <GameMenu
        :location-state="gameState?.location_state ?? { current: null, unlocked: [], next_station: null, rumored: [] }"
        :player="gameState?.player ?? null"
        :rels="characterRels"
        :trust="trust"
        :stances="stances"
        :character-states="gameState?.character_states"
        :world-events="gameState?.world_events"
        :world-rumors="gameState?.world_rumors"
        :briefing="gameState?.briefing"
        :world-date="gameState?.world_date"
        :stm-list="stmList"
        :ltm-list="ltmList"
        :pin-items="pinItems"
        :pins="pins"
        :pinned-count="pinnedCount"
        :total-mem-count="totalMemCount"
        :reveal="loadPhase === 'character'"
        @travel="travelTo"
        @ask="askRumor"
        @toggle-pin="togglePin"
        @read="markMenuRead"
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
import GameMenu from '../components/GameMenu.vue'
import CinematicLoader from '../components/CinematicLoader.vue'
import EraBanner from '../components/EraBanner.vue'
import NarrativeArea from '../components/NarrativeArea.vue'
import ChoiceArea from '../components/ChoiceArea.vue'
import AchievementToast from '../components/AchievementToast.vue'
import OperationGuide from '../components/OperationGuide.vue'
import { usePlaySse } from '../composables/usePlaySse'
import { useNarrativeBlocks } from '../composables/useNarrativeBlocks'
import { useInkSplash } from '../composables/useInkSplash'
import { clearPlayerId, deletePlayer, getPlayerId, loadPlayer, savePlayer } from '../composables/useSaveSystem'
import type { GameState, OptionSpec, MemoryItem, PhaseReport, WorldEvent, StreamEvent } from '../types/play'

const router = useRouter()
const { playStep, isStreaming, abort } = usePlaySse()
const playGuanyu = inject<() => void>('playGuanyu', () => {})

// ── 叙事流式块（composable 抽离）──
const { narrativeBlocks, currentStreamText, ensureStreamingBlock, updateLastBlock, freezeLastBlock, finalizeBlock, resetBlocks } = useNarrativeBlocks()

// ── 类型 ──
type LoadPhase = 'cinematic' | 'thinking' | 'streaming' | 'memory' | 'character' | 'options'

// ── 状态 ──
const gameState = ref<GameState | null>(null)
const options = ref<OptionSpec[]>([])
const freeInput = ref('')
const lastAction = ref('')     // 最近一次实际发出的动作（错误重试用，防输入框已清空丢失原动作）
// 存档串行化：fire-and-forget 并发 POST 会乱序落库（旧快照覆盖新状态），排队保证写库顺序
let saveChain: Promise<unknown> = Promise.resolve()
function queueSave(st: GameState | null) {
  saveChain = saveChain.then(() => savePlayer(st)).catch(() => {})
}
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

// ── 断点续玩：有存档时取代开场（继续历险 / 新开历险）──
const resumeDialog = ref(false)
const resumeState = ref<GameState | null>(null)
// ── 死亡回档：三属性同时极端（alive=False）→ 弹层读档最近快照 ──
const deadDialog = ref(false)
const resumeDateLabel = computed(() => {
  const wd = resumeState.value?.world_date
  if (!wd) return ''
  const day = Number(wd.day)
  const dayText = Number.isInteger(day) ? `${day}日` : `初${day >= 15 ? '二' : '一'}`
  return `上次进度 · ${wd.year}年${wd.month}月${dayText}`
})

// ── 成就解锁提示（后端 _commit 产出 new_achievements → onState 检测，浮层展示）──
const newAchToasts = ref<string[]>([])
let achTimer: number | null = null
function pushAchievements(ids: string[] | undefined) {
  if (!ids?.length) return
  const fresh = ids.filter(id => !newAchToasts.value.includes(id))
  if (!fresh.length) return
  newAchToasts.value.push(...fresh)
  // 最后一批出现后 3.2s 清空（连续解锁可堆叠展示）
  if (achTimer) clearTimeout(achTimer)
  achTimer = window.setTimeout(() => { newAchToasts.value = []; achTimer = null }, 3200)
}

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

// ── 全屏分轻重：跨年代才全屏，同年移动用轻过渡铭牌 ──
const lastSceneYear = ref(0)         // 当前场景声明年代（scene.year，判断跨年代）
const liteBannerText = ref('')       // 轻过渡铭牌文本（顶部淡入）
// 场景事件的世界日期/季节预告：scene 先于 state，时代快进时立即刷新 EraBanner（否则全屏宣告 189 但日期还停 184）
const sceneDatePreview = ref<{ year: number; month: number; day: number; season?: string } | null>(null)
let liteBannerTimer: number | null = null
let inkTimer: number | null = null   // 墨染转场复位 timer（triggerInk 使用，onBeforeUnmount 清理）
function showLiteBanner(chapter: string, title: string, location = '') {
  liteBannerText.value = [location || chapter, title].filter(Boolean).join(' · ')
  if (liteBannerTimer) clearTimeout(liteBannerTimer)
  liteBannerTimer = window.setTimeout(() => { liteBannerText.value = '' }, 2400)
}

// ── 操作引导（首次进入显示一次）──
const opsGuideVisible = ref(false)
function closeOpsGuide() {
  try { localStorage.setItem('sg3d_ops_guide_seen', '1') } catch { /* 隐私模式忽略 */ }
  opsGuideVisible.value = false
}

// ── 生命周期 ──
onMounted(() => {
  window.addEventListener('pointerdown', inkSplash, { passive: true })
  checkResume()   // 检测存档：有档弹「继续/新开」，无档正常开场
  // 首次进入游戏显示操作引导（localStorage 记一次）
  try {
    opsGuideVisible.value = localStorage.getItem('sg3d_ops_guide_seen') !== '1'
  } catch { opsGuideVisible.value = false }
})
onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', inkSplash)
  abort()                          // 中止在飞 SSE：防卸载后回调在死实例上执行、onDone 误存档
  clearPhaseTimers()               // 清理阶段切换 timer（防卸载后死实例上改 loadPhase）
  if (liteBannerTimer) { clearTimeout(liteBannerTimer); liteBannerTimer = null }
  if (inkTimer) { clearTimeout(inkTimer); inkTimer = null }
  if (loaderTimer) { clearTimeout(loaderTimer); loaderTimer = null }
  if (achTimer) { clearTimeout(achTimer); achTimer = null }
})

// ── 开局 / 断点续玩 ──
function beginAdventure() {
  showIntro.value = false
  startGame()
}

/** 检测存档：有则弹「继续/新开」（不播开场旁白），无则正常开场 */
async function checkResume() {
  const { hasSave, state } = await loadPlayer()
  if (hasSave && state) {
    resumeState.value = state
    resumeDialog.value = true
    showIntro.value = false   // 有档：intro 不播，直接确认层
  }
  // 无档：showIntro 保持 true（IntroOverlay 挂载即播放开场）
}

/** 继续历险 / 死亡回档：恢复完整 GameState + 重建叙事上下文 → 直接进入游戏态（可立即行动） */
function resumeGame(st: GameState | null = resumeState.value) {
  if (!st) return
  resumeDialog.value = false
  deadDialog.value = false
  resumeState.value = null
  gameState.value = st
  resetBlocks()
  options.value = st.last_output?.options ?? []
  // 恢复最后一段叙事（续接阅读）：标题分隔块 + 末段叙事文本块（reveal 打字机揭示一次）。
  // 注：此前的恢复块是 isScene:true——NarrativeArea 对 isScene 块只渲染标题分隔线、不渲染 text，
  // 导致续玩时末段叙事文本被静默丢弃；此处拆成两块，文本块设 reveal:true 触发揭示（接线死代码）。
  const narr = st.last_output?.narrative ?? ''
  if (narr) {
    const ps = st.meta?.plan_summary as { scene_id?: string; chapter_label?: string; title?: string } | undefined
    const title = ps?.chapter_label && ps?.title ? `${ps.chapter_label} · ${ps.title}` : ''
    if (title) {
      narrativeBlocks.value.push({ text: '', isScene: true, sceneTitle: title })
    }
    narrativeBlocks.value.push({ text: narr, streaming: false, reveal: true })
  }
  const ps = st.meta?.plan_summary as { scene_id?: string; year?: number } | undefined
  lastSceneId.value = ps?.scene_id ?? st.skeleton_pos ?? ''
  lastSceneYear.value = ps?.year ?? st.era?.year ?? 0   // 恢复当前场景年代（防恢复后首拍误判跨年代）
  sceneDatePreview.value = null   // 恢复用存档真实 world_date，清场景预告
  phaseReport.value = (st.last_output?.phase_report as PhaseReport | null) ?? null
  currentAtmo.value = '雨夜沉静'   // atmo 标签未持久化，恢复用默认
  started.value = true
  showIntro.value = false
  isStreaming.value = false
  hideLoader()   // 恢复路径不经过 onScene，必须手动隐藏加载器（否则 CinematicLoader 一直盖着）
  loadPhase.value = 'options'
  queueSave(gameState.value)   // 立即回写一次（保持存档）
}

/** 新开历险：删除旧档（放弃当前进度）→ 换新玩家档 → 重新播开场 */
function startNewAdventure() {
  resumeDialog.value = false
  resumeState.value = null
  const oldPid = getPlayerId()
  if (oldPid) deletePlayer(oldPid)   // 新开=放弃旧档，防 players 表累积孤儿档
  clearPlayerId()
  showIntro.value = true   // 重挂 IntroOverlay → 播放开场旁白
}

/** 死亡回档：读最近快照（死亡拍未保存，保留死前档）恢复 */
async function reloadFromDeath() {
  const { state } = await loadPlayer()
  if (state) {
    resumeGame(state)
  } else {
    deadDialog.value = false
    errorMessage.value = '存档缺失，只能重开历险。'
    clearPlayerId()
    showIntro.value = true
  }
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
  lastSceneYear.value = 0
  sceneDatePreview.value = null
  newMemCount.value = 0

  await playStep('', {} as GameState, 0, {
    onScene: (ev) => {
      // ① 场景就绪 → 切到思维链阶段（环境立即可见）
      lastSceneId.value = ev.scene.scene_id
      lastSceneYear.value = ev.scene.year ?? 0   // 审查⑫：开局初始化（防首个同年切换误判跨年代全屏）
      loaderTitle.value = ev.scene.title
      loaderChapterLabel.value = ev.scene.chapter_label
      sceneDatePreview.value = ev.scene.world_date ? { ...ev.scene.world_date, season: ev.scene.season } : null
      if (ev.scene.atmo) currentAtmo.value = ev.scene.atmo
      playGuanyu()   // 关羽之歌：进游戏即响（最经典的梗）
      hideLoader()
      started.value = true
      loadPhase.value = 'thinking'
    },
    onBriefing: (ev) => showBriefing(ev),
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
      sceneDatePreview.value = null   // 世界日期已由 state 权威值接管
      const prev = gameState.value
      gameState.value = state
      pushAchievements(state.new_achievements)   // 成就解锁提示
      // 计算新增记忆数
      const prevStm = prev?.memory?.stm?.length ?? 0
      const curStm = state?.memory?.stm?.length ?? 0
      newMemCount.value = Math.max(0, curStm - prevStm)
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
      queueSave(gameState.value?.dead ? null : gameState.value)   // 每拍自动快照（死亡拍不保存，保留死前档）
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

function submitFree(action?: string) {
  // 优先用 ChoiceArea emit 的 payload（与输入框清空时序解耦），缺失时回退输入框当前值
  const act = (action ?? freeInput.value).trim()
  if (!act) return
  sendAction(act, 0)
}

/** 地点面板点选：前往目标地点（director 导航：已解锁回访 / 未解锁沿 flow 推进） */
function travelTo(name: string) {
  sendAction(`前往${name}`, 0)
}

/** 地点面板传闻行点选：打听该地传闻（director 确认消息 → 解锁可前往） */
function askRumor(name: string) {
  sendAction(`打听${name}`, 0)
}

async function sendAction(action: string, tension: number) {
  if (isStreaming.value) return   // 防并发回合：SSE 进行中忽略新动作（双击选项/兜底按钮连点/挂起窗口连续操作）
  lastAction.value = action   // 记录实际动作（错误重试时重发，输入框已清空也不丢）
  clearPhaseTimers()   // 清除上一回合遗留的阶段切换 timer，防串回合
  const prevOptions = options.value
  options.value = []
  currentStreamText.value = ''
  started.value = true
  isStreaming.value = true
  newMemCount.value = 0

  await playStep(action, gameState.value ?? ({} as GameState), tension, {
    onBriefing: (ev) => showBriefing(ev),
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
      // 世界日期预告：scene 先于 state，时代快进时立即刷新 EraBanner（否则宣告 189 但显示 184）
      sceneDatePreview.value = ev.scene.world_date ? { ...ev.scene.world_date, season: ev.scene.season } : null
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
        // 全屏分轻重：跨年代才全屏（scene.year 变化，金色大标题 + 关羽之歌）；
        // 同年代内移动/推进轻过渡（顶部铭牌，无全屏无关羽）——场景标签含地点，不能按标签判定
        const crossChapter = !!ev.scene.year && ev.scene.year !== lastSceneYear.value
        lastSceneYear.value = ev.scene.year ?? lastSceneYear.value
        if (crossChapter) {
          showLoader(1800)
          playGuanyu()   // 关羽之歌：只在跨章节的大切换响
        } else {
          hideLoader()
          showLiteBanner(ev.scene.chapter_label, ev.scene.title, ev.scene.location)
        }
        loadPhase.value = 'thinking'
        // 场景切换时重置流式累积，防止旧场景文本串入新场景块
        currentStreamText.value = ''
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
      sceneDatePreview.value = null   // 世界日期已由 state 权威值接管
      const prev = gameState.value
      gameState.value = state
      // 简报已读竞态修复：briefing 事件先于 state 到达，用户在 state 前关简报会漏标本批事件 seen
      //（下次 new_briefing 回合被重播）——state 落地后按简报事件 id 补标，随 onDone 快照落盘
      const ids = pendingSeenIds
      if (ids && ids.size && state?.world_events?.length) {
        state.world_events = state.world_events.map(e =>
          ids.has(e.event_id) ? { ...e, seen: true } : e
        )
        gameState.value = { ...state }
      }
      pendingSeenIds = null
      pushAchievements(state.new_achievements)   // 成就解锁提示
      if (state.dead) deadDialog.value = true    // 死亡 → 弹「此身已逝」
      const prevStm = prev?.memory?.stm?.length ?? 0
      const curStm = state?.memory?.stm?.length ?? 0
      newMemCount.value = Math.max(0, curStm - prevStm)
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
      queueSave(gameState.value?.dead ? null : gameState.value)   // 每拍自动快照（死亡拍不保存，保留死前档）
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
  if (inkTimer) clearTimeout(inkTimer)
  inkTimer = window.setTimeout(() => { inkActive.value = false; inkTimer = null }, 1200)
}

// ── 派生 ──
const eraLabel = computed(() => {
  const pv = sceneDatePreview.value
  const era = gameState.value?.era
  const year = pv?.year ?? era?.year ?? 184
  const season = pv?.season ?? era?.season ?? '春'
  return `${year} 年 · ${season}`
})
const eraChapter = computed(() => gameState.value?.era?.chapter ?? 'P1 黄金风起')

// ── 自由沙盒：世界日期显示（取代旧世界时钟时节标签）──
// 场景预告优先（时代快进立即刷新），state 到达后回落到真实 world_date
const worldDateLabel = computed(() => {
  const wd = sceneDatePreview.value ?? gameState.value?.world_date
  if (!wd) return ''
  const day = Number(wd.day)
  const dayText = Number.isInteger(day) ? `${day}日` : `初${day >= 15 ? '二' : '一'}`
  return `${wd.year}年${wd.month}月${dayText}`
})

// ── 自由沙盒：世界简报（SSE briefing 事件驱动，受控弹窗）──
const briefingVisible = ref(false)
const briefingText = ref('')
const briefingEvents = ref<WorldEvent[]>([])
let pendingSeenIds: Set<string> | null = null   // 本批简报事件 id（state 落地后按 id 补标 seen，防关简报时序竞态）
/** 收到 SSE briefing 事件（先于 chunk 到达）→ 先弹简报，叙事在底下流式继续 */
function showBriefing(ev: StreamEvent & { type: 'briefing' }) {
  briefingText.value = ev.briefing ?? ''
  briefingEvents.value = ev.events ?? []
  pendingSeenIds = new Set((ev.events ?? []).map(e => e.event_id).filter(Boolean))
  briefingVisible.value = true
}
function closeBriefing() {
  briefingVisible.value = false
  markBriefingRead()
  // 审查⑪：已读 seen 随关闭动作落盘——onDone 快照先于用户读完简报执行，若不立即存，
  // 读后即关/刷新会丢失 seen 标记、同批事件下次重播
  queueSave(gameState.value?.dead ? null : gameState.value)
}
function markBriefingRead() {
  // 简报已读：标记 seen（前端维护；后端下次快照持久化）
  const gs = gameState.value
  if (!gs?.world_events) return
  gs.world_events = gs.world_events.map(e => e.seen ? e : { ...e, seen: true })
  gameState.value = { ...gs }
}
function markMenuRead() {
  // 世界菜单已读：标记 seen + 落盘（防刷新后同批事件重播，与简报已读同机制）
  markBriefingRead()
  queueSave(gameState.value?.dead ? null : gameState.value)
}

const characterRels = computed(() => gameState.value?.relations ?? {})
const trust = computed(() => gameState.value?.trust ?? {})
const stances = computed(() => gameState.value?.stances ?? {})

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
    // 用 lastAction 重发上回合真实动作（此前读已清空的输入框会静默退化为"继续前行"）
    sendAction(lastAction.value || '继续前行', 0)
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

/* 轻过渡铭牌（同章内移动/推进，顶部淡入淡出） */
.lite-banner {
  position: fixed;
  top: 9%;
  left: 50%;
  transform: translateX(-50%);
  z-index: 90;
  background: rgba(10, 10, 18, 0.82);
  border: 1px solid rgba(202, 138, 4, 0.28);
  border-radius: 999px;
  padding: 8px 22px;
  color: rgba(240, 220, 174, 0.92);
  font-size: 0.82rem;
  letter-spacing: 0.18em;
  font-family: "Noto Serif SC", "STKaiti", serif;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.45);
  white-space: nowrap;
  pointer-events: none;
}
.lite-fade-enter-active { transition: opacity 0.35s ease, transform 0.35s cubic-bezier(0.16, 1, 0.3, 1); }
.lite-fade-leave-active { transition: opacity 0.5s ease; }
.lite-fade-enter-from { opacity: 0; transform: translateX(-50%) translateY(-10px); }
.lite-fade-leave-to { opacity: 0; }

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

/* 断点续玩确认层（有存档时取代开场） */
.resume-dialog {
  position: fixed;
  inset: 0;
  z-index: 600;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  background: rgba(4, 4, 6, 0.82);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
.resume-title {
  font-family: "Noto Serif SC", "STKaiti", serif;
  font-size: 1.6rem;
  letter-spacing: 0.4em;
  color: #e8c88c;
  text-shadow: 0 0 30px rgba(232, 200, 140, 0.2);
}
.resume-sub {
  font-size: 0.88rem;
  letter-spacing: 0.08em;
  color: rgba(226, 232, 240, 0.75);
}
.resume-meta {
  font-size: 0.7rem;
  letter-spacing: 0.15em;
  color: rgba(202, 138, 4, 0.7);
  border: 1px solid rgba(202, 138, 4, 0.3);
  border-radius: 999px;
  padding: 4px 16px;
  margin-top: 4px;
}
.resume-actions {
  display: flex;
  gap: 14px;
  margin-top: 18px;
}
.resume-btn {
  font-family: "Noto Serif SC", "STKaiti", serif;
  font-size: 1rem;
  letter-spacing: 0.2em;
  padding: 12px 34px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.3s;
}
.resume-continue {
  color: #1a1815;
  background: linear-gradient(180deg, #f0dcae, #d2b478);
  border: 1px solid #e8c88c;
  box-shadow: 0 6px 24px rgba(232, 200, 140, 0.25);
}
.resume-continue:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 32px rgba(232, 200, 140, 0.4);
}
.resume-new {
  color: rgba(226, 232, 240, 0.75);
  background: rgba(15, 15, 30, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.3);
}
.resume-new:hover {
  background: rgba(15, 15, 35, 0.8);
  border-color: rgba(148, 163, 184, 0.5);
}
.resume-fade-enter-active { transition: opacity 0.5s ease; }
.resume-fade-leave-active { transition: opacity 0.3s ease; }
.resume-fade-enter-from, .resume-fade-leave-to { opacity: 0; }
/* 死亡回档层：标题转墨赤（区别于继续确认层的鎏金） */
.death-dialog .resume-title {
  color: #c04030;
  text-shadow: 0 0 30px rgba(192, 64, 48, 0.35);
}
</style>
