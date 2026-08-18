// usePlaySse —— /api/play/step 调用 + 事件解析
// 复用现有 getReader+TextDecoder 手写 SSE 解析骨架（已验证可靠）

import { ref } from 'vue'
import type { GameState, OptionSpec, StreamEvent } from '../types/play'
import { apiKeyHeaders } from '../apiKey'

const API_BASE = import.meta.env.VITE_API_BASE || ''

export interface StartNode {
  id: string
  kind: 'chapter' | 'scene'
  name: string
  date: string
  world_date: { year: number; month: number; day: number }
  location: string
}

/** 拉取开局可选剧情节点（8 篇章起始 + 名场面事件） */
export async function fetchStartNodes(): Promise<StartNode[]> {
  try {
    const resp = await fetch(`${API_BASE}/api/play/nodes`)
    const data = await resp.json()
    return (data && data.nodes) || []
  } catch {
    return []
  }
}

export function usePlaySse() {
  const isStreaming = ref(false)
  const error = ref('')
  let abortCtrl: AbortController | null = null   // 当前回合的 AbortController（新回合/卸载时中止旧连接）

  /** 中止当前回合的 SSE 连接（组件卸载或新回合接管时调用），中止时跳过 onError/onDone 副作用 */
  function abort() {
    if (abortCtrl) {
      abortCtrl.abort()
      abortCtrl = null
    }
    isStreaming.value = false
  }

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
      onBriefing?: (ev: StreamEvent & { type: 'briefing' }) => void
      onState: (state: GameState) => void
      onOptions: (options: OptionSpec[]) => void
      onPhase?: (report: StreamEvent & { type: 'phase' }) => void
      onDone: () => void
      onError?: (msg: string) => void
    },
  ): Promise<void> {
    // 新回合接管：中止仍在飞的上一连接（防旧回合回调交错覆盖新状态）
    if (abortCtrl) abortCtrl.abort()
    const ctrl = new AbortController()
    abortCtrl = ctrl
    isStreaming.value = true
    error.value = ''
    let doneCalled = false
    const fireDone = () => {
      if (!doneCalled) {
        doneCalled = true
        handlers.onDone()
      }
    }

    let receivedAny = false   // 已收到任意事件 → 流中途断裂不再自动重试（防同回合文本重复/串戏）
    const MAX_RETRIES = 2
    let attempt = 0
    let resp: Response

    try {
      // 断线自动重连（仅限尚未收到任何数据的连接阶段）：网络错误退避重试 ≤2 次
      while (true) {
        try {
          resp = await fetch(`${API_BASE}/api/play/step`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...apiKeyHeaders() },
            body: JSON.stringify({ action, game_state: gameState, tension }),
            signal: ctrl.signal,
          })
          break
        } catch (e) {
          if (ctrl.signal.aborted) return
          if (receivedAny || attempt >= MAX_RETRIES) throw e
          attempt += 1
          error.value = `连接中断，正在重连（${attempt}/${MAX_RETRIES}）…`
          await new Promise<void>((r) => setTimeout(r, 1200 * attempt))
          if (ctrl.signal.aborted) return
        }
      }
      error.value = ''

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
            fireDone()
            continue
          }
          try {
            const ev = JSON.parse(payload) as StreamEvent
            receivedAny = true
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
              case 'briefing':
                handlers.onBriefing?.(ev as StreamEvent & { type: 'briefing' })
                break
              case 'state':
                handlers.onState(ev.state)
                break
              case 'options':
                handlers.onOptions(ev.options)
                break
              case 'phase':
                handlers.onPhase?.(ev)
                break
              case 'done':
                fireDone()
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
      // 尾部残留行处理（统一走 switch，state/options 也可能在流尾被截断）
      if (buffer.trim()) {
        const trimmed = buffer.trim()
        if (trimmed.startsWith('data: ')) {
          const payload = trimmed.slice(6)
          try {
            const ev = JSON.parse(payload) as StreamEvent
            receivedAny = true
            switch (ev.type) {
              case 'chunk':
                handlers.onChunk(ev.content)
                break
              case 'scene':
                handlers.onScene?.(ev as StreamEvent & { type: 'scene' })
                break
              case 'player':
                handlers.onPlayer?.(ev.content)
                break
              case 'briefing':
                handlers.onBriefing?.(ev as StreamEvent & { type: 'briefing' })
                break
              case 'state':
                handlers.onState(ev.state)
                break
              case 'options':
                handlers.onOptions(ev.options)
                break
              case 'phase':
                handlers.onPhase?.(ev as StreamEvent & { type: 'phase' })
                break
              case 'done':
                fireDone()
                break
              case 'err':
                handlers.onError?.(ev.content)
                break
            }
          } catch { /* ignore */ }
        }
      }
      // 未收到 done 也视为完成
      fireDone()
    } catch (e) {
      // 中止（被新回合接管或组件卸载）→ 静默退出，不触发 onError/onDone 副作用
      if (ctrl.signal.aborted) return
      error.value = e instanceof Error ? e.message : String(e)
      handlers.onError?.(error.value)
    } finally {
      // 只有仍是最新回合才复位 isStreaming（防旧回合 finally 误关新回合的状态）
      if (abortCtrl === ctrl) abortCtrl = null
      if (!abortCtrl) isStreaming.value = false
    }
  }

  return { playStep, isStreaming, abort }
}
