<template>
  <!-- 开场叙述页（高清墨彩视频背景 + 标题置顶 + 穿越旁白依次浮现 + 规则） -->
  <div class="intro-overlay">
    <IntroBackground />
    <button class="intro-skip" @click="skipIntro">跳过 ▸</button>
    <div class="intro-content">
      <button class="intro-back" @click="emit('back')">← 返回星图</button>
      <!-- 标题：固定位置，静悬于画面中央，不随段落移动 -->
      <div class="intro-title">新三国 · 星空</div>
      <!-- 穿越旁白：一段一段渐渐浮现（宇宙漂浮感） -->
      <div class="intro-lines">
        <transition-group name="intro-line">
          <p v-for="(line, i) in INTRO_LINES" v-show="visibleLines >= i + 1" :key="i" class="intro-line">
            {{ line }}
          </p>
        </transition-group>
      </div>
      <transition name="error-fade">
        <div v-if="introDone" class="intro-rules">
          <div class="rule-row"><span class="rule-mark"></span>乱世 · 历史自有其轨迹——你不在正中央，也在风暴边缘</div>
          <div class="rule-row"><span class="rule-mark"></span>时间 · 每个行动都消耗时日，四季流转、天下兴替从不停步</div>
          <div class="rule-row"><span class="rule-mark"></span>后果 · 没有失败，只有选择酿成的后果——声望、关系、财富都会记住你</div>
          <div class="rule-row"><span class="rule-mark"></span>留存 · 你的资产、成就与恩怨持续留存，世道记得你来过的痕迹</div>
        </div>
      </transition>
      <button v-if="introDone" class="intro-begin" @click="begin">开始历险</button>
    </div>
  </div>
</template>

<script setup lang="ts">
// IntroOverlay —— 开场叙述页（PlayPage 抽离）
// 自管理旁白浮现时序；"开始历险"→ emit begin（页面 hide + 启动游戏），"返回星图"→ emit back。
import { ref, onMounted, onBeforeUnmount } from 'vue'
import IntroBackground from './IntroBackground.vue'

const emit = defineEmits<{ (e: 'begin'): void; (e: 'back'): void }>()

// 穿越旁白：一段一段渐渐浮现（宇宙漂浮感）
const INTRO_LINES = [
  '你记得最后一眼，是手机屏的冷光——高楼、车流、一条推送：黄巾起义，波及八州。',
  '再睁眼，是雨夜，是泥沟，是粗麻衣。你到了一个三国——一个好像不太对劲的三国。',
  '你将会经历未知的冒险，希望你忘记之前的一切，因为你已经顾不得许多了，只当是你从来没有过那些。',
]

let introTimer = 0
const visibleLines = ref(0)      // 已浮现的段落数（每段间隔渐显）
const introDone = ref(false)     // 旁白全浮现后置 true（显示规则 + 开始按钮）

function playIntro() {
  introDone.value = false
  visibleLines.value = 0
  let i = 0
  const step = () => {
    i++
    visibleLines.value = i
    if (i >= INTRO_LINES.length) {
      // 全部浮现后稍停，再出现规则与开始
      introTimer = window.setTimeout(() => { introDone.value = true }, 1800)
      return
    }
    introTimer = window.setTimeout(step, 2800)  // 每段间隔（放缓，从容漂浮）
  }
  introTimer = window.setTimeout(step, 900)     // 标题先现，旁白稍候
}

function skipIntro() {
  // 跳过开场：显示规则 + 开始按钮（视频背景继续循环）
  window.clearTimeout(introTimer)
  visibleLines.value = INTRO_LINES.length
  introDone.value = true
}

function begin() {
  window.clearTimeout(introTimer)
  emit('begin')
}

onMounted(playIntro)
onBeforeUnmount(() => window.clearTimeout(introTimer))
</script>

<style scoped>
.intro-overlay {
  position: fixed;
  inset: 0;
  z-index: 500;
  display: flex;
  align-items: flex-start;   /* 顶部对齐：标题固定最上方 */
  justify-content: center;
  background: #0a0a0c;   /* 兜底暗底（IntroBackground 视频覆盖其上） */
}
.intro-content {
  position: relative;
  z-index: 2;
  max-width: 760px;
  width: 90%;
  padding: 220px 32px 40px;  /* 顶部给固定标题留足空间，段落从标题下方开始 */
  text-align: center;
}
.intro-back {
  position: fixed;        /* 固定于视口左上角，不随剧情板块移动 */
  top: 24px;
  left: 28px;
  z-index: 510;
  font-size: 0.85rem;
  letter-spacing: 0.25em;
  color: rgba(226, 232, 240, 0.55);
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 8px 12px;
  transition: color 0.3s;
}
.intro-back:hover { color: #f1f5f9; }
.intro-skip {
  position: fixed;
  top: 28px;
  right: 32px;
  z-index: 510;
  font-size: 0.8rem;
  letter-spacing: 0.2em;
  color: rgba(226, 232, 240, 0.5);
  background: transparent;
  border: 1px solid rgba(226, 232, 240, 0.22);
  border-radius: 999px;
  padding: 6px 16px;
  cursor: pointer;
  transition: all 0.3s;
}
.intro-skip:hover {
  color: #f1f5f9;
  border-color: rgba(232, 200, 140, 0.6);
  background: rgba(232, 200, 140, 0.12);
}
/* 标题：固定钉在视口最上方中央，不随段落移动 */
.intro-title {
  position: fixed;
  top: 88px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 520;
  font-family: "Noto Serif SC", "STKaiti", "KaiTi", serif;
  font-size: 2.5rem;
  font-weight: 700;
  letter-spacing: 0.5em;
  margin-right: -0.5em;
  white-space: nowrap;
  color: rgba(250, 248, 242, 0.96);
  text-shadow: 0 2px 14px rgba(0, 0, 0, 0.6);
  pointer-events: none;
}
/* 旁白：一段一段渐渐浮现，微浮上移（宇宙漂浮感），无金线无边框 */
.intro-lines {
  max-width: 640px;
  margin: 0 auto;
  min-height: 190px;
}
.intro-line {
  font-family: "Noto Serif SC", "STKaiti", "KaiTi", serif;
  margin: 0 0 16px;
  font-size: 1.0rem;
  line-height: 1.9;
  letter-spacing: 0.1em;
  color: rgba(248, 246, 240, 0.88);
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.85);
  animation: intro-line-float 4.2s ease-out forwards;
}
@keyframes intro-line-float {
  0%   { opacity: 0; transform: translateY(18px); }
  20%  { opacity: 1; transform: translateY(0); }
  100% { opacity: 1; transform: translateY(0); }
}
.intro-rules {
  margin-top: 24px;
  max-width: 640px;
  background: rgba(10, 10, 14, 0.55);
  border: 1px solid rgba(232, 200, 140, 0.3);
  border-radius: 12px;
  padding: 18px 24px;
  display: grid;
  gap: 10px;
  text-align: left;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
.rule-row {
  font-size: 0.92rem;
  line-height: 1.6;
  color: rgba(245, 239, 226, 0.9);
  letter-spacing: 0.04em;
}
.rule-mark {
  display: inline-block;
  width: 7px;
  height: 7px;
  background: #e8c88c;
  margin-right: 12px;
  vertical-align: middle;
  border-radius: 1px;
}
.intro-begin {
  margin-top: 30px;
  font-family: "Noto Serif SC", "STKaiti", "KaiTi", serif;
  font-size: 1.15rem;
  letter-spacing: 0.4em;
  text-indent: 0.4em;
  padding: 14px 48px;
  color: #1a1815;
  background: linear-gradient(180deg, #f0dcae, #d2b478);
  border: 1px solid #e8c88c;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 6px 24px rgba(232, 200, 140, 0.25);
}
.intro-begin:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 32px rgba(232, 200, 140, 0.4);
}
/* 页面 <transition name="intro-fade"> 包本组件根 → 过渡类放本组件 scoped 才能命中根元素 */
.intro-fade-enter-active { transition: opacity 0.8s; }
.intro-fade-leave-active { transition: opacity 0.4s; }
.intro-fade-enter-from, .intro-fade-leave-to { opacity: 0; }
/* 内部规则区过渡（与页面错误横幅同名过渡类，各自 scoped 独立；transform 对齐原版） */
.error-fade-enter-active,
.error-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.error-fade-enter-from,
.error-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-8px);
}
</style>
