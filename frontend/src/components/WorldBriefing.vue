<template>
  <transition name="briefing-fade">
    <div v-if="visible" class="briefing-overlay" @click="close">
      <div class="briefing-panel" @click.stop>
        <div class="briefing-title">天 下 动 态</div>
        <div class="briefing-sub">你离开的这段时间，世间发生了这些……</div>
        <p v-if="briefing" class="briefing-syn">{{ briefing }}</p>
        <!-- 强相关事件：与你有关，高亮 -->
        <div class="briefing-list" v-if="strongEvents.length">
          <div v-for="e in strongEvents" :key="e.event_id" class="briefing-item briefing-strong">
            <span class="briefing-date">{{ e.date }}</span>
            <span class="briefing-tag">与你有关</span>
            <span class="briefing-text">{{ e.event }}</span>
          </div>
        </div>
        <!-- 弱相关事件：折叠区（B-⑦：不再丢弃，默认收起） -->
        <button v-if="weakEvents.length" class="briefing-more" @click="showWeak = !showWeak">
          {{ showWeak ? '收起其他 ·' : `查看其他 ${weakEvents.length} 条 ·` }}
        </button>
        <div v-if="showWeak" class="briefing-list briefing-weak">
          <div v-for="e in weakEvents" :key="e.event_id" class="briefing-item">
            <span class="briefing-date">{{ e.date }}</span>
            <span class="briefing-text">{{ e.event }}</span>
          </div>
        </div>
        <button class="briefing-close" @click="close">继续前行</button>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
// WorldBriefing —— 世界简报面板（自由沙盒：先出简报，后进场景叙事 B-⑧）
// 受控组件：visible 由父（PlayPage 收到 SSE briefing 事件）控制；weak 折叠展示（B-⑦）。
import { ref, computed, watch } from 'vue'
import type { WorldEvent } from '../types/play'

const props = defineProps<{
  visible: boolean
  events: WorldEvent[]
  briefing?: string
}>()
const emit = defineEmits<{ (e: 'read'): void }>()

const showWeak = ref(false)

// 每次弹出时重置折叠态
watch(() => props.visible, (v) => { if (v) showWeak.value = false })

const strongEvents = computed(() => (props.events || []).filter(e => e.related_to_player === 'strong'))
const weakEvents = computed(() => (props.events || []).filter(e => e.related_to_player === 'weak'))

function close() {
  emit('read')  // 通知父组件标记已读
}
</script>

<style scoped>
.briefing-overlay {
  position: fixed;
  inset: 0;
  z-index: 600;
  background: rgba(4, 4, 6, 0.7);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
}
.briefing-panel {
  width: min(560px, 90vw);
  max-height: 72vh;
  overflow-y: auto;
  background: rgba(12, 12, 18, 0.92);
  border: 1px solid rgba(210, 180, 120, 0.3);
  border-radius: 14px;
  padding: 26px 30px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.6);
}
.briefing-title {
  font-family: "Noto Serif SC", "STKaiti", serif;
  font-size: 1.3rem;
  letter-spacing: 0.4em;
  color: #e8c88c;
  text-align: center;
  margin-bottom: 6px;
}
.briefing-sub {
  font-size: 0.78rem;
  color: rgba(226, 232, 240, 0.55);
  text-align: center;
  letter-spacing: 0.05em;
  margin-bottom: 18px;
}
.briefing-syn {
  font-size: 0.95rem;
  line-height: 1.8;
  color: rgba(240, 220, 174, 0.92);
  background: rgba(255, 255, 255, 0.04);
  border-left: 3px solid rgba(232, 200, 140, 0.45);
  border-radius: 0 8px 8px 0;
  padding: 12px 16px;
  margin: 0 0 14px;
  letter-spacing: 0.02em;
}
.briefing-list {
  display: grid;
  gap: 12px;
}
.briefing-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 0.88rem;
  line-height: 1.6;
  color: rgba(226, 232, 240, 0.88);
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.03);
  border-left: 3px solid rgba(148, 163, 184, 0.3);
  border-radius: 0 8px 8px 0;
}
.briefing-item.briefing-strong {
  border-left-color: #e8c88c;
  background: rgba(232, 200, 140, 0.07);
}
.briefing-date {
  font-size: 0.75rem;
  color: rgba(148, 163, 184, 0.7);
  flex-shrink: 0;
  padding-top: 2px;
}
.briefing-tag {
  font-size: 0.7rem;
  color: #e8c88c;
  border: 1px solid rgba(232, 200, 140, 0.4);
  border-radius: 10px;
  padding: 0 8px;
  flex-shrink: 0;
  margin-top: 1px;
}
.briefing-text { flex: 1; }
.briefing-more {
  display: block;
  margin: 12px auto 0;
  background: none;
  border: 1px dashed rgba(148, 163, 184, 0.25);
  color: rgba(148, 163, 184, 0.6);
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  border-radius: 8px;
  padding: 5px 16px;
  cursor: pointer;
  transition: all 0.25s;
}
.briefing-more:hover {
  color: rgba(202, 168, 100, 0.85);
  border-color: rgba(202, 138, 4, 0.4);
}
.briefing-weak {
  margin-top: 10px;
  opacity: 0.85;
}
.briefing-close {
  display: block;
  margin: 20px auto 0;
  font-family: "Noto Serif SC", "STKaiti", serif;
  font-size: 0.95rem;
  letter-spacing: 0.2em;
  color: #1a1815;
  background: linear-gradient(180deg, #f0dcae, #d2b478);
  border: none;
  border-radius: 999px;
  padding: 10px 36px;
  cursor: pointer;
  transition: all 0.3s;
}
.briefing-close:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(232, 200, 140, 0.3); }
.briefing-fade-enter-active, .briefing-fade-leave-active { transition: opacity 0.4s ease; }
.briefing-fade-enter-from, .briefing-fade-leave-to { opacity: 0; }
</style>
