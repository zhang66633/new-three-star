<template>
  <div class="settings-overlay" @click.self="emit('close')">
    <div class="settings-card">
      <h2 class="settings-title">⚙ API 配置</h2>
      <p class="settings-desc">
        密钥只存你的浏览器，用于本次生成，服务器不保存。
        <b>DeepSeek</b>（叙事）必填；<b>Qwen</b>（主控）可选，不填则主控回退 DeepSeek。
      </p>

      <!-- DeepSeek 板块 -->
      <div class="provider-block">
        <div class="provider-head">
          <span class="provider-name">DeepSeek</span>
          <span class="provider-role">叙事生成</span>
          <span class="provider-status" :class="hasKey ? 'ok' : 'warn'">{{ hasKey ? '已配置' : '未配置' }}</span>
        </div>
        <input
          v-model="keyInput"
          :type="showKey ? 'text' : 'password'"
          class="key-input"
          placeholder="sk-… 粘贴你的 DeepSeek API 密钥"
          autocomplete="off"
          spellcheck="false"
          @keydown.enter="save"
        />
        <div class="provider-row">
          <label class="key-label" for="ds-model">模型</label>
          <select id="ds-model" v-model="modelInput" class="key-select">
            <option v-for="m in DEEPSEEK_MODELS" :key="m" :value="m">{{ m }}</option>
          </select>
          <button class="btn-ghost" @click="showKey = !showKey">{{ showKey ? '隐藏' : '显示' }}</button>
        </div>
        <div class="key-actions">
          <span class="key-mask">{{ hasKey ? maskKey : '' }}</span>
          <a class="key-link" href="https://platform.deepseek.com/api_keys" target="_blank" rel="noopener noreferrer">去 DeepSeek 申请密钥 ↗</a>
        </div>
      </div>

      <!-- Qwen 板块 -->
      <div class="provider-block">
        <div class="provider-head">
          <span class="provider-name">Qwen</span>
          <span class="provider-role">主控（校验/修正/记忆）</span>
          <span class="provider-status" :class="hasQwenKey ? 'ok' : 'warn'">{{ hasQwenKey ? '已配置' : '未配置' }}</span>
        </div>
        <input
          v-model="qwenInput"
          :type="showQwenKey ? 'text' : 'password'"
          class="key-input"
          placeholder="sk-… 粘贴你的 Qwen（阿里云百炼）API 密钥（可选）"
          autocomplete="off"
          spellcheck="false"
          @keydown.enter="save"
        />
        <div class="provider-row">
          <label class="key-label" for="qwen-model">模型</label>
          <select id="qwen-model" v-model="qwenModelInput" class="key-select">
            <option v-for="m in QWEN_MODELS" :key="m" :value="m">{{ m }}</option>
          </select>
          <button class="btn-ghost" @click="showQwenKey = !showQwenKey">{{ showQwenKey ? '隐藏' : '显示' }}</button>
        </div>
        <div class="key-actions">
          <span class="key-mask">{{ hasQwenKey ? maskQwenKey : '' }}</span>
          <a class="key-link" href="https://bailian.console.aliyun.com/" target="_blank" rel="noopener noreferrer">去阿里云百炼申请密钥 ↗</a>
        </div>
      </div>

      <div class="btn-row">
        <button class="btn-save" :disabled="!keyInput.trim() && !qwenInput.trim()" @click="save">保存</button>
        <button class="btn-clear" :disabled="!hasKey && !hasQwenKey" @click="clear">清除</button>
        <button class="btn-close" @click="emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getApiKey, setApiKey, clearApiKey, getQwenApiKey, setQwenApiKey, clearQwenApiKey, getDeepSeekModel, setDeepSeekModel, getQwenModel, setQwenModel, DEEPSEEK_MODELS, QWEN_MODELS } from '../apiKey'

const emit = defineEmits<{ (e: 'close'): void }>()

const keyInput = ref('')
const showKey = ref(false)
const hasKey = ref(false)
const qwenInput = ref('')
const showQwenKey = ref(false)
const hasQwenKey = ref(false)
const modelInput = ref(getDeepSeekModel())
const qwenModelInput = ref(getQwenModel())

const maskKey = computed(() => {
  const k = getApiKey()
  if (!k) return ''
  return k.length > 10 ? k.slice(0, 6) + '…' + k.slice(-4) : '••••••••'
})

const maskQwenKey = computed(() => {
  const k = getQwenApiKey()
  if (!k) return ''
  return k.length > 10 ? k.slice(0, 6) + '…' + k.slice(-4) : '••••••••'
})

onMounted(() => {
  const k = getApiKey()
  hasKey.value = !!k
  keyInput.value = k
  const q = getQwenApiKey()
  hasQwenKey.value = !!q
  qwenInput.value = q
})

function save() {
  const v = keyInput.value.trim()
  if (v) { setApiKey(v); hasKey.value = true }
  const q = qwenInput.value.trim()
  if (q) { setQwenApiKey(q); hasQwenKey.value = true }
  setDeepSeekModel(modelInput.value)
  setQwenModel(qwenModelInput.value)
  emit('close')
}

function clear() {
  clearApiKey(); hasKey.value = false; keyInput.value = ''
  clearQwenApiKey(); hasQwenKey.value = false; qwenInput.value = ''
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
  width: min(92vw, 400px);
  max-height: 86vh;
  overflow-y: auto;
  background: rgba(16, 16, 26, 0.96);
  border: 1px solid rgba(251, 191, 36, 0.35);
  border-radius: 14px;
  padding: 22px 20px;
  color: #ececf2;
  box-shadow: 0 0 60px rgba(251, 191, 36, 0.12);
  font-family: 'Noto Serif SC', serif;
}
.settings-title { margin: 0 0 10px; font-size: 19px; color: #fbbf24; letter-spacing: 2px; }
.settings-desc { margin: 0 0 16px; font-size: 12.5px; line-height: 1.7; color: rgba(236,236,242,0.7); }
.provider-block {
  border: 1px solid rgba(236,236,242,0.1);
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 14px;
  background: rgba(3,3,6,0.4);
}
.provider-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.provider-name { font-size: 14px; font-weight: 600; color: #f1f5f9; }
.provider-role { font-size: 11px; color: rgba(236,236,242,0.45); flex: 1; }
.provider-status { font-size: 11px; padding: 1px 8px; border-radius: 999px; }
.provider-status.ok { color: #34d399; background: rgba(52,211,153,0.12); }
.provider-status.warn { color: #fbbf24; background: rgba(251,191,36,0.12); }
.key-input {
  width: 100%;
  box-sizing: border-box;
  padding: 9px 12px;
  font-size: 13.5px;
  background: rgba(3,3,6,0.8);
  border: 1px solid rgba(236,236,242,0.2);
  border-radius: 8px;
  color: #ececf2;
  outline: none;
}
.key-input:focus { border-color: #fbbf24; }
.provider-row { display: flex; align-items: center; gap: 8px; margin: 8px 0 6px; }
.key-label { font-size: 12px; color: rgba(236,236,242,0.55); white-space: nowrap; }
.key-select {
  flex: 1;
  box-sizing: border-box;
  padding: 7px 10px;
  font-size: 13px;
  background: rgba(3,3,6,0.8);
  border: 1px solid rgba(236,236,242,0.2);
  border-radius: 8px;
  color: #ececf2;
  outline: none;
  cursor: pointer;
}
.key-select:focus { border-color: #fbbf24; }
.key-actions { display: flex; align-items: center; justify-content: space-between; margin-top: 4px; }
.key-mask { font-size: 11.5px; color: rgba(148,163,184,0.7); }
.btn-ghost { background: none; border: none; color: rgba(236,236,242,0.55); font-size: 12px; cursor: pointer; }
.btn-ghost:hover { color: #ececf2; }
.key-link { font-size: 12px; color: #93c5fd; text-decoration: none; }
.key-link:hover { text-decoration: underline; }
.btn-row { display: flex; gap: 10px; margin-top: 4px; }
.btn-row button { flex: 1; padding: 10px 0; font-size: 14px; border-radius: 8px; cursor: pointer; border: none; }
.btn-save { background: #fbbf24; color: #1a1815; font-weight: 600; }
.btn-save:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-clear { background: rgba(236,236,242,0.1); color: #ececf2; }
.btn-clear:disabled { opacity: 0.3; cursor: not-allowed; }
.btn-close { background: rgba(236,236,242,0.06); color: rgba(236,236,242,0.6); }
</style>
