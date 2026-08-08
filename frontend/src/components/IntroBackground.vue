<template>
  <div class="intro-bg" aria-hidden="true">
    <!-- 高清墨彩视频背景（现成素材，全屏循环，无蒙版——如漂浮宇宙） -->
    <video class="bg-video" autoplay muted loop playsinline preload="auto" :src="bgVideo"></video>
  </div>
</template>

<script setup lang="ts">
// IntroBackground —— 开场背景（现成高清视频版）
// 黑底彩墨流动视频全屏循环、无蒙版，质感由专业实拍保证，如漂浮宇宙。
import bgVideo from '../assets/intro/intro_bg.mp4'
</script>

<style scoped>
.intro-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  background: #0a0a0c;
}
.bg-video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  transform: scale(1.06);   /* 微放大消除循环边缘 */
}
</style>
