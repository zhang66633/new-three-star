<template>
  <div class="stream-text" :class="{ typing }">
    <span v-html="displayHtml"></span>
    <span v-if="typing" class="caret" aria-hidden="true">▌</span>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onBeforeUnmount, computed } from 'vue'

const props = withDefaults(defineProps<{
  text: string          // 完整文本（更新时增量流式输出）
  speed?: number        // 每字间隔 ms
  chunkSize?: number    // 每帧字数（>1 则按块输出）
}>(), {
  text: '',
  speed: 24,
  chunkSize: 1,
})

const displayed = ref('')
const typing = ref(false)
let timer: number | null = null
let target = ''

watch(() => props.text, (val) => {
  stop()
  target = val
  // 全量重建（新段落）
  displayed.value = ''
  typing.value = true
  let pos = 0
  const tick = () => {
    pos += props.chunkSize
    displayed.value = target.slice(0, pos)
    if (pos >= target.length) {
      typing.value = false
      stop()
    }
  }
  timer = window.setInterval(tick, props.speed)
})

onBeforeUnmount(() => stop())

function stop() {
  if (timer) { clearInterval(timer); timer = null }
}

// 简单转义 + 保留换行/标点样式
const displayHtml = computed(() => {
  const esc = displayed.value
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\n/g, '<br/>')
  return esc
})
</script>

<style scoped>
.stream-text {
  font-family: var(--font-body);
  line-height: 1.9;
  letter-spacing: 0.04em;
  color: rgba(248, 250, 252, 0.92);
  word-break: break-word;
}
.caret {
  display: inline-block;
  width: 2px;
  height: 1.15em;
  margin-left: 2px;
  vertical-align: text-bottom;
  background: #ca8a04;
  box-shadow: 0 0 8px rgba(202, 138, 4, 0.7);
  animation: caret-blink 0.9s step-end infinite;
}
@keyframes caret-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
