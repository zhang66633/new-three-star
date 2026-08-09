<template>
  <transition name="briefing-fade">
    <div v-if="visible" class="briefing-overlay" @click="close">
      <div class="briefing-panel" @click.stop>
        <div class="briefing-title">天 下 动 态</div>
        <div class="briefing-sub">你离开的这段时间，世间发生了这些……</div>
        <p v-if="briefing" class="briefing-syn">{{ briefing }}</p>
        <div class="briefing-list" v-if="events.length">
          <div v-for="e in events" :key="e.event_id" class="briefing-item"
            :class="{ 'briefing-strong': e.related_to_player === 'strong' }">
            <span class="briefing-date">{{ e.date }}</span>
            <span v-if="e.related_to_player === 'strong'" class="briefing-tag">与你有关</span>
            <span class="briefing-text">{{ e.event }}</span>
          </div>
        </div>
        <button class="briefing-close" @click="close">继续前行</button>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
// WorldBriefing —— 世界简报面板（自由沙盒：玩家到达新地点/周期时弹出未读事件）
// 展示 world_events 中未读的强相关事件，其余弱相关折叠。
import { ref, watch } from 'vue'
import type { WorldEvent } from '../types/play'

const props = defineProps<{
  events: WorldEvent[]
  briefing?: string
}>()
const emit = defineEmits<{ (e: 'read'): void }>()

const visible = ref(false)

// 有合成简报（A3）或未读强相关事件时弹出
watch(() => [props.events, props.briefing] as const, () => {
  const hasStrong = (props.events || []).some(e => !e.seen && e.related_to_player === 'strong')
  if (props.briefing || hasStrong) {
    visible.value = true
  }
}, { immediate: true, deep: true })

function close() {
  visible.value = false
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
