<template>
  <div class="settings-overlay" @click.self="emit('close')">
    <div class="settings-card">
      <h2 class="settings-title">⚙ API 密钥</h2>
      <p class="settings-desc">
        每个玩家填入<b>自己的</b> DeepSeek 密钥。密钥只存在你的浏览器里、用于本次生成，
        服务器不保存。没有密钥无法生成剧情。
      </p>

      <p class="settings-status" :class="hasKey ? 'ok' : 'warn'">
        <span v-if="hasKey">已配置：{{ maskKey }}</span>
        <span v-else>尚未配置</span>
      </p>

      <input
        v-model="keyInput"
        :type="showKey ? 'text' : 'password'"
        class="key-input"
        placeholder="sk-… 粘贴你的 DeepSeek API 密钥"
        autocomplete="off"
        spellcheck="false"
        @keydown.enter="save"
      />

      <div class="key-actions">
        <button class="btn-ghost" @click="showKey = !showKey">
          {{ showKey ? '隐藏' : '显示' }}
        </button>
        <a
          class="key-link"
          href="https://platform.deepseek.com/api_keys"
          target="_blank"
          rel="noopener noreferrer"
        >去 DeepSeek 申请密钥 ↗</a>
      </div>

      <div class="btn-row">
        <button class="btn-save" :disabled="!keyInput.trim()" @click="save">保存</button>
        <button class="btn-clear" :disabled="!hasKey" @click="clear">清除</button>
        <button class="btn-close" @click="emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getApiKey, setApiKey, clearApiKey } from '../apiKey'

const emit = defineEmits<{ (e: 'close'): void }>()

const keyInput = ref('')
const showKey = ref(false)
const hasKey = ref(false)

const maskKey = computed(() => {
  const k = getApiKey()
  if (!k) return ''
  return k.length > 10 ? `${k.slice(0, 6)}…${k.slice(-4)}` : '••••••••'
})

onMounted(() => {
  const k = getApiKey()
  hasKey.value = !!k
  keyInput.value = k
})

function save() {
  const v = keyInput.value.trim()
  if (v) {
    setApiKey(v)
    hasKey.value = true
  }
  emit('close')
}

function clear() {
  clearApiKey()
  hasKey.value = false
  keyInput.value = ''
  emit('close')
}
</script>

<style scoped>
.settings-overlay {
  position: fixed;
  inset: 0;
  z-index: 120;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(3, 3, 6, 0.78);
  backdrop-filter: blur(6px);
}

.settings-card {
  width: min(92vw, 380px);
  background: rgba(16, 16, 26, 0.96);
  border: 1px solid rgba(251, 191, 36, 0.35);
  border-radius: 14px;
  padding: 24px 22px;
  color: #ececf2;
  box-shadow: 0 0 60px rgba(251, 191, 36, 0.12);
  font-family: 'Noto Serif SC', serif;
}

.settings-title {
  margin: 0 0 10px;
  font-size: 20px;
  color: #fbbf24;
  letter-spacing: 2px;
}

.settings-desc {
  margin: 0 0 14px;
  font-size: 13px;
  line-height: 1.7;
  color: rgba(236, 236, 242, 0.7);
}

.settings-status {
  margin: 0 0 10px;
  font-size: 13px;
}
.settings-status.ok { color: #34d399; }
.settings-status.warn { color: #fbbf24; }

.key-input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  font-size: 14px;
  background: rgba(3, 3, 6, 0.8);
  border: 1px solid rgba(236, 236, 242, 0.2);
  border-radius: 8px;
  color: #ececf2;
  outline: none;
}
.key-input:focus {
  border-color: #fbbf24;
}

.key-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 8px 0 16px;
}

.btn-ghost {
  background: none;
  border: none;
  color: rgba(236, 236, 242, 0.55);
  font-size: 12px;
  cursor: pointer;
}
.btn-ghost:hover { color: #ececf2; }

.key-link {
  font-size: 12px;
  color: #93c5fd;
  text-decoration: none;
}
.key-link:hover { text-decoration: underline; }

.btn-row {
  display: flex;
  gap: 10px;
}
.btn-row button {
  flex: 1;
  padding: 10px 0;
  font-size: 14px;
  border-radius: 8px;
  border: 1px solid rgba(236, 236, 242, 0.2);
  background: rgba(236, 236, 242, 0.06);
  color: #ececf2;
  cursor: pointer;
  font-family: inherit;
}
.btn-row button:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.btn-save {
  border-color: rgba(52, 211, 153, 0.5) !important;
  color: #34d399 !important;
}
.btn-clear {
  border-color: rgba(248, 113, 113, 0.4) !important;
  color: #f87171 !important;
}
</style>
