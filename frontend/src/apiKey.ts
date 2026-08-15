// API 密钥的浏览器端存取。
// 每个玩家用自己的 DeepSeek 密钥：存在 localStorage，随请求 X-API-Key 头发给后端。
// 后端不保存，只用于向 DeepSeek 转发生成请求。

const KEY_STORE = 'sg_deepseek_key'

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

/** 给 fetch 追加的请求头；未配置密钥时不带 X-API-Key（后端会提示先配置）。 */
export function apiKeyHeaders(): Record<string, string> {
  const k = getApiKey()
  return k ? { 'X-API-Key': k } : {}
}
