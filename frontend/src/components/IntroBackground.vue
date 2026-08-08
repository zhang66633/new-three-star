<template>
  <div class="intro-bg" aria-hidden="true">
    <img class="ink-img" :src="inkMountains" alt="" draggable="false" />
    <div class="ink-veil"></div>
    <div class="mist mist-1"></div>
    <div class="mist mist-2"></div>
    <div class="mist mist-3"></div>
  </div>
</template>

<script setup lang="ts">
// IntroBackground —— 水墨画风开场背景
// 水墨山岚图 + 深墨暗场 + 缓慢雾气漂移（动态但含蓄，贴合水墨留白意境）
import inkMountains from '../assets/atmo/ink_mountains.png'
</script>

<style scoped>
.intro-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  background: #0a0a0c; /* 深墨底 */
}
.ink-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.9;
  animation: ink-breathe 42s ease-in-out infinite alternate;
  will-change: transform;
}
@keyframes ink-breathe {
  from { transform: scale(1); }
  to { transform: scale(1.05); }
}
/* 深墨暗场：上淡下浓，中心微亮，衬托文字 */
.ink-veil {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 50% 42%, rgba(12, 12, 15, 0.35), rgba(8, 8, 10, 0.82) 80%),
    linear-gradient(180deg, rgba(8, 8, 10, 0.4), rgba(8, 8, 10, 0.85));
}
/* 墨雾漂移：多层半透明雾，缓慢流动（水墨呼吸感） */
.mist {
  position: absolute;
  border-radius: 50%;
  filter: blur(64px);
  pointer-events: none;
  will-change: transform;
}
.mist-1 {
  width: 58vw; height: 30vh; left: -12vw; top: 32%;
  background: radial-gradient(circle, rgba(168, 178, 190, 0.28), transparent 70%);
  animation: mist-drift 28s ease-in-out infinite alternate;
}
.mist-2 {
  width: 50vw; height: 26vh; right: -10vw; top: 12%;
  background: radial-gradient(circle, rgba(206, 211, 220, 0.2), transparent 70%);
  animation: mist-drift 34s ease-in-out infinite alternate-reverse;
}
.mist-3 {
  width: 66vw; height: 32vh; left: 18%; bottom: -6%;
  background: radial-gradient(circle, rgba(128, 138, 152, 0.18), transparent 70%);
  animation: mist-drift 40s ease-in-out infinite alternate;
}
@keyframes mist-drift {
  from { transform: translateX(0) translateY(0); }
  to { transform: translateX(7vw) translateY(2vh); }
}
@media (prefers-reduced-motion: reduce) {
  .ink-img, .mist { animation: none; }
}
</style>
