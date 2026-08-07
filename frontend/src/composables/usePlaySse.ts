// usePlaySse —— /api/play/step 调用 + 事件解析
// 复用现有 getReader+TextDecoder 手写 SSE 解析骨架（已验证可靠）

import { ref } from 'vue'
import type { GameState, OptionSpec, StreamEvent } from '../types/play'

const API_BASE = import.meta.env.VITE_API_BASE || ''

export function usePlaySse() {
  const isStreaming = ref(false)
  const error = ref('')

  /**
   * 发一轮请求，通过回调消费事件
   * @param action 玩家动作（'' = 开局）
   * @param gameState 前端持有的状态
   * @param tension 所选选项的干预度（0-100）
   * @param handlers 事件回调
   */
  async function playStep(
    action: string,
    gameState: GameState,
    tension: number,
    handlers: {
      onChunk: (text: string) => void
      onScene?: (scene: StreamEvent & { type: 'scene' }) => void
      onPlayer?: (text: string) => void
      onState: (state: GameState) => void
      onOptions: (options: OptionSpec[]) => void
      onDone: () => void
      onError?: (msg: string) => void
    },
  ): Promise<void> {
    isStreaming.value = true
    error.value = ''

    try {
      const resp = await fetch(`${API_BASE}/api/play/step`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, game_state: gameState, tension }),
      })

      if (!resp.ok || !resp.body) {
        throw new Error(`请求失败: ${resp.status}`)
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // 按行解析（保留最后不完整行）
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue
          const payload = trimmed.slice(6)
          if (payload === '[DONE]') {
            handlers.onDone()
            continue
          }
          try {
            const ev = JSON.parse(payload) as StreamEvent
            switch (ev.type) {
              case 'chunk':
                handlers.onChunk(ev.content)
                break
              case 'scene':
                handlers.onScene?.(ev)
                break
              case 'player':
                handlers.onPlayer?.(ev.content)
                break
              case 'state':
                handlers.onState(ev.state)
                break
              case 'options':
                handlers.onOptions(ev.options)
                break
              case 'done':
                handlers.onDone()
                break
              case 'err':
                handlers.onError?.(ev.content)
                break
            }
          } catch {
            // 非 JSON 行忽略
          }
        }
      }
      // 尾部残留行处理
      if (buffer.trim()) {
        const trimmed = buffer.trim()
        if (trimmed.startsWith('data: ')) {
          const payload = trimmed.slice(6)
          try {
            const ev = JSON.parse(payload) as StreamEvent
            if (ev.type === 'done') handlers.onDone()
            if (ev.type === 'chunk') handlers.onChunk((ev as { content: string }).content)
          } catch { /* ignore */ }
        }
      }
      // 未收到 done 也视为完成
      handlers.onDone()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      handlers.onError?.(error.value)
    } finally {
      isStreaming.value = false
    }
  }

  return { playStep, isStreaming, error }
}
