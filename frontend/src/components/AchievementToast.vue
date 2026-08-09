<template>
  <!-- 成就解锁提示（临时浮层，堆叠渐显；父组件定时移除） -->
  <transition-group name="ach-toast" tag="div" class="ach-toasts" aria-live="polite">
    <div v-for="a in achievements" :key="a" class="ach-toast">
      <span class="ach-icon">✦</span>
      <div class="ach-body">
        <span class="ach-title">成就解锁</span>
        <span class="ach-name">{{ ACH_NAMES[a] ?? a }}</span>
      </div>
    </div>
  </transition-group>
</template>

<script setup lang="ts">
// AchievementToast —— 成就解锁临时提示（PlayPage 集成）
// 接收新解锁成就 id 队列，堆叠渲染为上方浮层；生命周期由父组件定时清空。
import { ACH_NAMES } from '../utils/achievements'

defineProps<{ achievements: string[] }>()
</script>

<style scoped>
.ach-toasts {
  position: fixed;
  top: 74px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 200;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  pointer-events: none;
}
.ach-toast {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 18px;
  background: rgba(10, 10, 18, 0.9);
  border: 1px solid rgba(232, 200, 140, 0.35);
  border-left: 3px solid #e8c88c;
  border-radius: 0 10px 10px 0;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}
.ach-icon {
  color: #e8c88c;
  font-size: 1rem;
  animation: ach-spin 2.4s linear infinite;
}
@keyframes ach-spin {
  to { transform: rotate(360deg); }
}
.ach-body {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.ach-title {
  font-size: 0.6rem;
  letter-spacing: 0.25em;
  color: rgba(202, 138, 4, 0.7);
}
.ach-name {
  font-size: 0.9rem;
  letter-spacing: 0.08em;
  color: #f1f5f9;
}
.ach-toast-enter-active { transition: opacity 0.35s ease, transform 0.35s cubic-bezier(0.16, 1, 0.3, 1); }
.ach-toast-leave-active { transition: opacity 0.4s ease, transform 0.4s ease; }
.ach-toast-enter-from, .ach-toast-leave-to { opacity: 0; transform: translateY(-10px); }
</style>
