<template>
  <button
    class="audio-toggle"
    :class="{ muted }"
    @click="toggleMute"
    :title="muted ? '开启音效' : '关闭音效'"
  >
    <span class="audio-icon">{{ muted ? '✕' : '♪' }}</span>
  </button>
</template>

<script setup lang="ts">
import { inject, type Ref } from 'vue'

const muted = inject<Ref<boolean>>('audioMuted')!
const toggleMute = inject<() => void>('toggleMute')!
</script>

<style scoped>
.audio-toggle {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 1000;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 1px solid rgba(160, 160, 200, 0.2);
  background: rgba(10, 10, 18, 0.8);
  color: var(--text-muted);
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
  backdrop-filter: blur(8px);
}

.audio-toggle:hover {
  border-color: var(--accent-gold);
  color: var(--accent-gold);
}

.audio-toggle.muted {
  opacity: 0.5;
}
</style>
