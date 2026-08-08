<template>
  <router-view v-slot="{ Component }">
    <transition name="page-fade" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
  <AudioController />
  <!-- 全局错误边界（避免白屏） -->
  <div v-if="globalError" class="global-error">
    <span class="ge-icon">⚡</span>
    <span class="ge-text">世界短暂失序……</span>
    <button class="ge-btn" @click="recover">重试</button>
  </div>
</template>

<script setup lang="ts">
import { ref, provide, onMounted, onErrorCaptured } from 'vue'
import AudioController from './components/AudioController.vue'
import guanyuSong from './assets/关羽之歌.m4a'

const muted = ref(false)
let audio: HTMLAudioElement | null = null
const globalError = ref(false)

onMounted(() => {
  audio = new Audio(guanyuSong)
  audio.volume = 0.4
})

onErrorCaptured((err) => {
  console.error('[Global Error Boundary]', err)
  globalError.value = true
  return false  // 阻止向上传播
})

function playGuanyu() {
  if (muted.value || !audio) return
  audio.currentTime = 0
  audio.play().catch(() => {})
}

function toggleMute() {
  muted.value = !muted.value
  if (muted.value && audio) {
    audio.pause()
  }
}

function recover() {
  globalError.value = false
  window.location.reload()
}

provide('playGuanyu', playGuanyu)
provide('audioMuted', muted)
provide('toggleMute', toggleMute)
</script>

<style scoped>
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.6s ease;
}
.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
}

/* 全局错误边界 */
.global-error {
  position: fixed; inset: 0;
  z-index: 999;
  background: rgba(5, 5, 8, 0.96);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
.ge-icon {
  font-size: 2rem;
  animation: ge-pulse 1.5s ease-in-out infinite;
}
@keyframes ge-pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}
.ge-text {
  font-family: var(--font-display);
  font-size: 1rem;
  color: rgba(202, 138, 4, 0.7);
  letter-spacing: 0.15em;
}
.ge-btn {
  background: rgba(202, 138, 4, 0.1);
  border: 1px solid rgba(202, 138, 4, 0.3);
  color: #ca8a04;
  border-radius: 8px;
  padding: 8px 24px;
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 0.85rem;
  letter-spacing: 0.1em;
  transition: all 0.25s ease;
}
.ge-btn:hover {
  background: rgba(202, 138, 4, 0.2);
  border-color: rgba(202, 138, 4, 0.6);
}
</style>
