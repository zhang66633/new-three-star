// API 密钥的浏览器端存取（BYOK 双 key）。
// DeepSeek（叙事）：存在 localStorage，随请求 X-API-Key 头发给后端。
// Qwen（主控：校验/修正/记忆/简报）：存在 localStorage，随请求 X-QWEN-API-Key 头发给后端。
// 后端不保存，只用于向对应服务转发生成请求。Qwen key 可选——不填则主控回退 DeepSeek（单模型模式）。

const KEY_STORE = 'sg_deepseek_key'
const QWEN_KEY_STORE = 'sg_qwen_key'

export function getApiKey(): string {
  try {
    return localStorage.getItem(KEY_STORE) || ''
  } catch {
    return ''
  }
}

export function setApiKey(key: string): void {
  try {
    localStorage.setItem(KEY_STORE, key.trim())
  } catch {
    /* 隐私模式等场景忽略 */
  }
}

export function clearApiKey(): void {
  try {
    localStorage.removeItem(KEY_STORE)
  } catch {
    /* ignore */
  }
}

export function getQwenApiKey(): string {
  try {
    return localStorage.getItem(QWEN_KEY_STORE) || ''
  } catch {
    return ''
  }
}

export function setQwenApiKey(key: string): void {
  try {
    localStorage.setItem(QWEN_KEY_STORE, key.trim())
  } catch {
    /* ignore */
  }
}

export function clearQwenApiKey(): void {
  try {
    localStorage.removeItem(QWEN_KEY_STORE)
  } catch {
    /* ignore */
  }
}

/** 给 fetch 追加的请求头；未配置密钥时不带头（后端会提示先配置）。 */
export function apiKeyHeaders(): Record<string, string> {
  const k = getApiKey()
  const q = getQwenApiKey()
  const h: Record<string, string> = {}
  if (k) h['X-API-Key'] = k
  if (q) h['X-QWEN-API-Key'] = q
  return h
}
