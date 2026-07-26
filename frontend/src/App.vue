<template>
  <router-view v-slot="{ Component }">
    <transition name="page-fade" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
  <AudioController />
</template>

<script setup lang="ts">
import { ref, provide, onMounted } from 'vue'
import AudioController from './components/AudioController.vue'
import guanyuSong from './assets/关羽之歌.m4a'

const muted = ref(false)
let audio: HTMLAudioElement | null = null

onMounted(() => {
  audio = new Audio(guanyuSong)
  audio.volume = 0.4
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
</style>
