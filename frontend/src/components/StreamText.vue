<template>
  <span class="stream-text" :class="{ typing }">{{ displayed }}<span v-if="typing" class="caret" aria-hidden="true">▌</span></span>
</template>

<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'

const props = withDefaults(defineProps<{
  text: string          // 完整文本（更新时增量流式输出）
  speed?: number        // 每字间隔 ms
  chunkSize?: number    // 每帧字数（>1 则按块输出）
}>(), {
  text: '',
  speed: 12,
  chunkSize: 3,
})

const displayed = ref('')
const typing = ref(false)
let timer: number | null = null
let target = ''

// immediate: 首次挂载（text 已完整）也要触发打字；之后增量更新不重置
watch(() => props.text, (val) => {
  stop()
  // 新文本是旧文本的延伸 → 不重置，从当前位置继续；否则全新段落重新打
  const isExtension = val.startsWith(target) && target.length > 0
  if (!isExtension) {
    displayed.value = ''
  }
  target = val
  const remaining = target.length - displayed.value.length
  if (remaining <= 0) { typing.value = false; return }
  typing.value = true
  let pos = displayed.value.length
  const tick = () => {
    pos += props.chunkSize
    displayed.value = target.slice(0, pos)
    if (pos >= target.length) {
      typing.value = false
      stop()
    }
  }
  timer = window.setInterval(tick, props.speed)
}, { immediate: true })

onBeforeUnmount(() => stop())

function stop() {
  if (timer) { clearInterval(timer); timer = null }
}
</script>

<style scoped>
/* 纯文本渲染：white-space 继承父级 .narrative-text（pre-line 保留换行），
   与流式直出分支像素级一致，不再依赖 v-html/<br/> */
.stream-text {
  white-space: inherit;
  overflow-wrap: inherit;
}
/* 流式输出中：逐字微辉光（极淡琥珀色，不抢注意力） */
.stream-text.typing {
  text-shadow: 0 0 1px rgba(202, 138, 4, 0.12);
}
.caret {
  display: inline-block;
  width: 2px;
  margin-left: 2px;
  color: #ca8a04;
  text-shadow: 0 0 10px rgba(202, 138, 4, 0.8), 0 0 20px rgba(202, 138, 4, 0.3);
  animation: caret-blink 0.9s step-end infinite, caret-glow 1.8s ease-in-out infinite;
}
@keyframes caret-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
@keyframes caret-glow {
  0%, 100% { text-shadow: 0 0 10px rgba(202, 138, 4, 0.8), 0 0 20px rgba(202, 138, 4, 0.3); }
  50%      { text-shadow: 0 0 14px rgba(202, 138, 4, 1),   0 0 28px rgba(202, 138, 4, 0.45); }
}
</style>
