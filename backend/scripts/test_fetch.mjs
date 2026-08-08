// 浏览器同款 fetch 测试 SSE（Node 18+ 全局 fetch 行为与浏览器一致）
const BASE = process.env.BASE || 'http://localhost:5173'

async function main() {
  const t0 = Date.now()
  try {
    const resp = await fetch(`${BASE}/api/play/step`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: '', game_state: {}, tension: 0 }),
    })
    console.log('status:', resp.status)
    console.log('content-type:', resp.headers.get('content-type'))

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let chunkCount = 0
    let eventCount = 0
    let firstChunkAt = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()
      for (const l of lines) {
        const trimmed = l.trim()
        if (!trimmed.startsWith('data: ')) continue
        eventCount++
        try {
          const ev = JSON.parse(trimmed.slice(6))
          if (ev.type === 'chunk') {
            chunkCount++
            if (firstChunkAt === null) firstChunkAt = ((Date.now() - t0) / 1000).toFixed(1)
          }
          if (ev.type === 'done') {
            console.log(`done 收到，总耗时 ${((Date.now() - t0) / 1000).toFixed(1)}s`)
          }
        } catch {}
      }
    }
    console.log(`事件总数: ${eventCount}, chunk 数: ${chunkCount}, 首 chunk: ${firstChunkAt}s`)
  } catch (e) {
    console.error('FETCH ERROR:', e.message)
  }
}

main()
