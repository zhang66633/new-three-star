<template>
  <div class="play-page">
    <!-- 返回星图 -->
    <button class="back-btn" @click="goBack" aria-label="返回星图">←</button>

    <!-- 加载动画（开局/场景切换） -->
    <CinematicLoader
      :show="loaderVisible"
      :title="loaderTitle"
      :chapter-label="loaderChapterLabel"
      :status-text="loaderStatus"
    />

    <!-- 主界面 -->
    <div class="play-main" v-show="!loaderVisible || (gameState?.turn ?? 0) > 1">
      <!-- 章节铭牌 -->
      <header class="era-banner">
        <span class="era-label">{{ eraLabel }}</span>
        <span class="era-chapter">{{ eraChapter }}</span>
        <span class="era-goldline"></span>
      </header>

      <!-- 叙事区 -->
      <main class="narrative-area" ref="narrativeRef">
        <div v-for="(block, i) in narrativeBlocks" :key="i" class="narrative-block">
          <!-- 场景分隔（新场景标题） -->
          <div v-if="block.isScene" class="scene-divider">
            <span class="scene-divider-line"></span>
            <span class="scene-divider-text">{{ block.sceneTitle }}</span>
            <span class="scene-divider-line"></span>
          </div>
          <!-- 叙事文本（流式） -->
          <p class="narrative-text" :class="{ playerPov: block.isPlayerPov }">
            <StreamText v-if="i === narrativeBlocks.length - 1 && isStreaming && !block.isScene" :text="block.text" />
            <template v-else>{{ block.text }}</template>
            <span v-if="block.isPlayerPov" class="pov-mark">·思绪</span>
          </p>
        </div>
        <div v-if="isStreaming && !currentStreamText" class="streaming-indicator">
          <span class="gold-dot"></span>
          <span class="streaming-text">世界在低语……</span>
        </div>
      </main>

      <!-- 选项区 -->
      <footer class="choice-area" v-if="options.length > 0 && !isStreaming">
        <button
          v-for="(opt, i) in options"
          :key="i"
          class="choice-btn"
          :class="tensionClass(opt.tension)"
          @click="chooseOption(opt)"
        >
          <span class="choice-num">{{ i + 1 }}</span>
          <span class="choice-text">{{ opt.text }}</span>
          <span v-if="opt.effect" class="choice-effect">{{ opt.effect }}</span>
        </button>
        <div class="free-row">
          <input
            v-model="freeInput"
            class="free-input"
            placeholder="或者，你想做点什么……"
            @keydown.enter="submitFree"
          />
          <button class="free-submit" :disabled="!freeInput.trim()" @click="submitFree">行动</button>
        </div>
      </footer>

      <!-- 角色状态卡 -->
      <aside class="character-panel">
        <div class="cp-title">在场</div>
        <div v-for="(rel, name) in characterRels" :key="name" class="character-chip">
          <span class="chip-name">{{ name }}</span>
          <span class="chip-rels">
            <span class="chip-rel" :class="relClass(rel)">好{{ rel }}</span>
            <span class="chip-rel" :class="trustClass(trust[name] ?? 0)">信{{ trust[name] ?? 0 }}</span>
          </span>
        </div>
        <div v-if="Object.keys(characterRels).length === 0" class="cp-empty">荒野无人</div>
      </aside>

      <!-- 记忆抽屉 -->
      <button class="memory-toggle" @click="showMemory = !showMemory">
        {{ showMemory ? '收起记忆' : '记忆' }}{{ stmList.length ? `(${stmList.length})` : '' }}
      </button>
      <div v-if="showMemory" class="memory-drawer">
        <div class="md-title">短期记忆</div>
        <div v-for="m in stmList" :key="m.id" class="memory-item">
          <span class="mi-text">{{ m.text }}</span>
          <button
            class="mi-pin"
            :class="{ pinned: isPinned(m.id) }"
            @click="togglePin(m.id)"
          >{{ isPinned(m.id) ? '📌' : '📍' }}</button>
        </div>
        <div v-if="stmList.length === 0" class="md-empty">暂无记忆</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import CinematicLoader from '../components/CinematicLoader.vue'
import StreamText from '../components/StreamText.vue'
import { usePlaySse } from '../composables/usePlaySse'
import type { GameState, OptionSpec, MemoryItem } from '../types/play'

const router = useRouter()
const { playStep, isStreaming } = usePlaySse()

// ── 状态 ──
const gameState = ref<GameState | null>(null)
const narrativeBlocks = ref<{ text: string; isScene?: boolean; sceneTitle?: string; isPlayerPov?: boolean }[]>([])
const options = ref<OptionSpec[]>([])
const freeInput = ref('')
const currentStreamText = ref('')
const showMemory = ref(false)
const stmList = computed<MemoryItem[]>(() => gameState.value?.memory?.stm ?? [])

// ── 加载动画 ──
const loaderVisible = ref(true)
const loaderTitle = ref('新三国 星空')
const loaderChapterLabel = ref('184 年 · 颍川')
const loaderStatus = ref('世界正在生成……')

// ── 初始化 ──
onMounted(() => {
  startGame()
})

async function startGame() {
  loaderVisible.value = true
  loaderTitle.value = '新三国 星空'
  loaderChapterLabel.value = '184 年 · 颍川'
  loaderStatus.value = '世界正在生成……'
  gameState.value = null
  narrativeBlocks.value = []
  options.value = []

  await playStep('', {} as GameState, 0, {
    onChunk: (text) => {
      if (!currentStreamText.value) {
        // 首 chunk：切掉加载动画，开始流式
        loaderVisible.value = false
      }
      currentStreamText.value += text
      updateLastBlock()
    },
    onState: (state) => { gameState.value = state },
    onOptions: (opts) => { options.value = opts },
    onDone: () => {
      finalizeBlock()
      loaderVisible.value = false
    },
    onError: (msg) => {
      loaderStatus.value = '世界短暂失序……'
      setTimeout(() => { loaderVisible.value = false }, 2000)
      console.error(msg)
    },
  })
}

async function chooseOption(opt: OptionSpec) {
  await sendAction(opt.text, opt.tension)
}

async function submitFree() {
  const action = freeInput.value.trim()
  if (!action) return
  freeInput.value = ''
  await sendAction(action, 0)
}

async function sendAction(action: string, tension: number) {
  options.value = []
  currentStreamText.value = ''
  narrativeBlocks.value.push({ text: '' })
  isStreaming.value = true

  await playStep(action, gameState.value ?? ({} as GameState), tension, {
    onChunk: (text) => {
      currentStreamText.value += text
      updateLastBlock()
    },
    onScene: (ev) => {
      // 场景切换：插入分隔 + 更新铭牌
      narrativeBlocks.value.push({
        text: '',
        isScene: true,
        sceneTitle: `${ev.scene.chapter_label} · ${ev.scene.title}`,
      })
      loaderTitle.value = ev.scene.title
      loaderChapterLabel.value = ev.scene.chapter_label
      loaderVisible.value = true
      setTimeout(() => { loaderVisible.value = false }, 1500)
    },
    onState: (state) => { gameState.value = state },
    onOptions: (opts) => { options.value = opts },
    onDone: () => { finalizeBlock() },
    onError: (msg) => console.error(msg),
  })
}

function updateLastBlock() {
  const blocks = narrativeBlocks.value
  if (blocks.length === 0) return
  const last = blocks[blocks.length - 1]
  if (!last.isScene) {
    last.text = currentStreamText.value
  } else {
    // 场景分隔后追加叙事块
    narrativeBlocks.value.push({ text: currentStreamText.value })
  }
  scrollToBottom()
}

function finalizeBlock() {
  isStreaming.value = false
  currentStreamText.value = ''
  scrollToBottom()
}

function scrollToBottom() {
  nextTick(() => {
    const el = document.querySelector('.narrative-area')
    if (el) el.scrollTop = el.scrollHeight
  })
}

// ── 派生 ──
const eraLabel = computed(() => {
  const era = gameState.value?.era
  return era ? `${era.year} 年 · ${era.season}` : '184 年 · 春'
})
const eraChapter = computed(() => gameState.value?.era?.chapter ?? 'P1 黄巾风起')

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

onBeforeUnmount(() => {
  // 清理
})
</script>

<style scoped>
.play-page {
  width: 100%;
  height: 100%;
  background: radial-gradient(ellipse at 50% 30%, #0f0f23 0%, #020203 75%);
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
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
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 2;
}

/* 章节铭牌 */
.era-banner {
  padding: 28px 24px 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.era-label {
  font-size: 0.8rem;
  letter-spacing: 0.4em;
  color: rgba(202, 138, 4, 0.7);
}
.era-chapter {
  font-family: var(--font-display);
  font-size: 1.4rem;
  font-weight: 700;
  letter-spacing: 0.25em;
  color: #f8fafc;
}
.era-goldline {
  width: 140px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(202, 138, 4, 0.6), transparent);
}

/* 叙事区 */
.narrative-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px 10%;
  scroll-behavior: smooth;
}
.narrative-block {
  margin-bottom: 18px;
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

/* 选项区 */
.choice-area {
  padding: 16px 10% 30px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.choice-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(15, 15, 35, 0.7);
  border: 1px solid;
  border-radius: 10px;
  padding: 12px 16px;
  cursor: pointer;
  text-align: left;
  transition: all 0.25s ease;
  color: #f8fafc;
  font-family: var(--font-body);
}
.choice-btn:hover {
  transform: translateX(4px);
}
.choice-num {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  flex-shrink: 0;
}
.choice-text { flex: 1; font-size: 0.95rem; }
.choice-effect {
  font-size: 0.75rem;
  opacity: 0.6;
  max-width: 40%;
  text-align: right;
}

/* tension 三色 */
.tension-low { border-color: rgba(69, 196, 138, 0.4); }
.tension-low .choice-num { background: rgba(69, 196, 138, 0.15); color: #45c48a; }
.tension-low:hover { border-color: #45c48a; background: rgba(69, 196, 138, 0.08); }
.tension-mid { border-color: rgba(232, 168, 56, 0.4); }
.tension-mid .choice-num { background: rgba(232, 168, 56, 0.15); color: #e8a838; }
.tension-mid:hover { border-color: #e8a838; background: rgba(232, 168, 56, 0.08); }
.tension-high { border-color: rgba(192, 64, 48, 0.4); }
.tension-high .choice-num { background: rgba(192, 64, 48, 0.15); color: #c04030; }
.tension-high:hover { border-color: #c04030; background: rgba(192, 64, 48, 0.08); }

/* 自由输入 */
.free-row {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}
.free-input {
  flex: 1;
  background: rgba(15, 15, 35, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 8px;
  padding: 10px 14px;
  color: #f8fafc;
  font-family: var(--font-body);
  font-size: 0.9rem;
}
.free-input:focus {
  outline: none;
  border-color: rgba(202, 138, 4, 0.6);
}
.free-submit {
  background: rgba(202, 138, 4, 0.15);
  border: 1px solid rgba(202, 138, 4, 0.5);
  color: #ca8a04;
  border-radius: 8px;
  padding: 0 18px;
  cursor: pointer;
  font-family: var(--font-body);
  transition: all 0.25s ease;
}
.free-submit:disabled { opacity: 0.3; cursor: default; }
.free-submit:not(:disabled):hover { background: rgba(202, 138, 4, 0.3); }

/* 角色状态卡 */
.character-panel {
  position: absolute;
  right: 24px;
  top: 100px;
  width: 160px;
  background: rgba(10, 10, 18, 0.85);
  border: 1px solid rgba(202, 138, 4, 0.15);
  border-radius: 12px;
  padding: 12px;
  backdrop-filter: blur(8px);
}
.cp-title {
  font-size: 0.7rem;
  letter-spacing: 0.3em;
  color: rgba(202, 138, 4, 0.6);
  margin-bottom: 10px;
}
.character-chip {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 6px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
}
.chip-name { font-size: 0.85rem; color: #f8fafc; }
.chip-rels { display: flex; gap: 10px; font-size: 0.7rem; }
.rel-high { color: #45c48a; }
.rel-mid { color: #e8a838; }
.rel-low { color: #c04030; }
.trust-high { color: #45c48a; }
.trust-mid { color: #e8a838; }
.trust-low { color: #c04030; }
.cp-empty { color: rgba(148, 163, 184, 0.4); font-size: 0.8rem; }

/* 记忆抽屉 */
.memory-toggle {
  position: absolute;
  right: 24px;
  bottom: 20px;
  background: rgba(10, 10, 18, 0.85);
  border: 1px solid rgba(202, 138, 4, 0.3);
  color: #ca8a04;
  border-radius: 20px;
  padding: 6px 14px;
  font-size: 0.75rem;
  cursor: pointer;
  z-index: 30;
}
.memory-drawer {
  position: absolute;
  right: 24px;
  bottom: 60px;
  width: 300px;
  background: rgba(10, 10, 18, 0.95);
  border: 1px solid rgba(202, 138, 4, 0.2);
  border-radius: 12px;
  padding: 14px;
  z-index: 30;
  max-height: 40vh;
  overflow-y: auto;
}
.md-title {
  font-size: 0.7rem;
  letter-spacing: 0.3em;
  color: rgba(202, 138, 4, 0.6);
  margin-bottom: 10px;
}
.memory-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 0;
  font-size: 0.8rem;
  color: rgba(248, 250, 252, 0.8);
  line-height: 1.6;
}
.mi-text { flex: 1; }
.mi-pin {
  background: none;
  border: none;
  font-size: 0.85rem;
  cursor: pointer;
  opacity: 0.4;
}
.mi-pin.pinned { opacity: 1; }
.md-empty { color: rgba(148, 163, 184, 0.4); font-size: 0.8rem; }

/* 响应式 */
@media (max-width: 768px) {
  .narrative-area { padding: 16px 5%; }
  .choice-area { padding: 12px 5% 24px; }
  .character-panel { display: none; }
}
</style>
