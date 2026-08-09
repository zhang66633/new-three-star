<template>
  <!-- 选项区（LLM 生成 / 场景手调选项 + 自由输入） -->
  <footer class="choice-area choice-reveal">
    <template v-if="options.length > 0">
      <button
        v-for="(opt, i) in options"
        :key="i"
        class="choice-btn"
        :class="tensionClass(opt.tension)"
        @click="emit('choose', opt)"
      >
        <span v-if="opt.category" class="choice-cat" :class="`cat-${opt.category}`">{{ opt.category }}</span>
        <span class="choice-text">{{ opt.text }}</span>
        <span v-if="opt.effect" class="choice-effect">{{ opt.effect }}</span>
      </button>
    </template>
    <!-- options 缺失/被截断时的兜底：给玩家一个继续入口，避免硬卡死 -->
    <button v-else class="choice-btn tension-mid" @click="emit('fallback')">
      <span class="choice-text">继续前行……</span>
      <span class="choice-effect">（选项未及到达，先走一步）</span>
    </button>
    <div class="free-row">
      <input
        v-model="freeInput"
        class="free-input"
        placeholder="或者，你想做点什么……"
        @keydown.enter="submit"
      />
      <button class="free-submit" :disabled="!freeInput.trim()" @click="submit">行动</button>
    </div>
  </footer>
</template>

<script setup lang="ts">
// ChoiceArea —— 选项区 + 自由输入（PlayPage 抽离）
// options 展示（tension 三色）+ 自由输入 v-model；选择/输入 → emit 交页面发 SSE。
import type { OptionSpec } from '../types/play'
import { tensionClass } from '../utils/classes'

defineProps<{
  options: OptionSpec[]
}>()
const emit = defineEmits<{
  (e: 'choose', opt: OptionSpec): void
  (e: 'fallback'): void
  (e: 'submit', action: string): void
}>()

const freeInput = defineModel<string>({ default: '' })

function submit() {
  const action = freeInput.value.trim()
  if (!action) return
  emit('submit', action)
}
</script>

<style scoped>
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
/* 地点行动分类徽章（自由沙盒 §5.4：打探/赶路/停留/互动） */
.choice-cat {
  flex-shrink: 0;
  font-size: 0.58rem;
  letter-spacing: 0.08em;
  padding: 2px 7px;
  border-radius: 4px;
  border: 1px solid;
  margin-top: 2px;
}
.cat-打探 { color: rgba(74, 158, 160, 0.9); border-color: rgba(74, 158, 160, 0.35); background: rgba(74, 158, 160, 0.08); }
.cat-赶路 { color: rgba(232, 168, 56, 0.9); border-color: rgba(232, 168, 56, 0.35); background: rgba(232, 168, 56, 0.08); }
.cat-停留 { color: rgba(148, 163, 184, 0.8); border-color: rgba(148, 163, 184, 0.3); background: rgba(148, 163, 184, 0.06); }
.cat-互动 { color: rgba(190, 130, 190, 0.85); border-color: rgba(190, 130, 190, 0.3); background: rgba(190, 130, 190, 0.07); }
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
/* 自由输入 */
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
/* 选项浮现 */
.choice-reveal .choice-btn {
  animation: option-enter 0.35s cubic-bezier(0.16, 1, 0.3, 1) both;
}
/* 响应式 */
@media (max-width: 768px) {
  .choice-area { padding: 12px 5% 24px; }
}
/* prefers-reduced-motion：关闭所有动画 */
@media (prefers-reduced-motion: reduce) {
  .choice-btn {
    animation: none !important;
  }
  .choice-btn:active {
    transform: none !important;
  }
}
</style>
