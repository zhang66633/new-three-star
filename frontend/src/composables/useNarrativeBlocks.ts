// useNarrativeBlocks —— 叙事流式块状态管理（PlayPage 抽离）
// 流式叙事以"块"为单位累积：场景分隔块 / streaming 直出块 / 完成块 / 打字机揭示块。
// SSE 各回调调用本 composable 的更新函数，NarrativeArea 组件只做展示 + 自滚动。
import { ref } from 'vue'

export interface NarrativeBlock {
  text: string
  isScene?: boolean
  sceneTitle?: string
  isPlayerPov?: boolean
  streaming?: boolean  // 当前流式接收中（直出 + 光标）
  reveal?: boolean     // 最新完成块（打字机揭示一次）
}

export function useNarrativeBlocks() {
  const narrativeBlocks = ref<NarrativeBlock[]>([])
  const currentStreamText = ref('')

  /** 首 chunk：确保最后有一个 streaming 块接收流式文本（分隔块/静态块后追加） */
  function ensureStreamingBlock() {
    const blocks = narrativeBlocks.value
    const last = blocks[blocks.length - 1]
    if (!last || last.isScene || !last.streaming) {
      blocks.push({ text: '', streaming: true })
    }
  }

  function updateLastBlock() {
    const blocks = narrativeBlocks.value
    for (let i = blocks.length - 1; i >= 0; i--) {
      const b = blocks[i]
      if (b.isScene) continue
      if (b.streaming) { b.text = currentStreamText.value; break }
      // 无 streaming 块（罕见）：追加
      blocks.push({ text: currentStreamText.value, streaming: true })
      break
    }
  }

  /** 定格流式块为完成态；reveal=true 时只让最新完成块跑打字机，其余定格静态 */
  function freezeLastBlock(reveal: boolean) {
    const blocks = narrativeBlocks.value
    let target: NarrativeBlock | null = null
    for (let i = blocks.length - 1; i >= 0; i--) {
      const b = blocks[i]
      if (!b.isScene && b.streaming) { target = b; break }
    }
    if (target) {
      target.streaming = false
      if (reveal) {
        for (const b of blocks) if (b !== target) b.reveal = false
        target.reveal = true
      } else {
        target.reveal = false
      }
    }
  }

  /** 回合结束：定稿 + 清流式累积（streaming 态已用快速 StreamText 打完，不触发二次打字） */
  function finalizeBlock() {
    freezeLastBlock(false)
    currentStreamText.value = ''
  }

  /** 新开局重置 */
  function resetBlocks() {
    narrativeBlocks.value = []
    currentStreamText.value = ''
  }

  return {
    narrativeBlocks,
    currentStreamText,
    ensureStreamingBlock,
    updateLastBlock,
    freezeLastBlock,
    finalizeBlock,
    resetBlocks,
  }
}
