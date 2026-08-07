// SSE 流式验证（Node 客户端，无 urllib 的 chunked 问题）
const http = require('node:http')

const body = JSON.stringify({ action: '', game_state: {}, tension: 0 })

const req = http.request({
  hostname: 'localhost',
  port: 8001,
  path: '/api/play/step',
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
}, (res) => {
  console.log('status:', res.statusCode)
  let buf = ''
  let chunkCount = 0
  let firstChunkT = null
  const t0 = Date.now()
  const events = {}

  res.on('data', (d) => {
    buf += d.toString()
    const lines = buf.split('\n')
    buf = lines.pop()
    for (const l of lines) {
      if (!l.startsWith('data: ')) continue
      try {
        const ev = JSON.parse(l.slice(6))
        events[ev.type] = (events[ev.type] || 0) + 1
        if (ev.type === 'chunk') {
          chunkCount++
          if (firstChunkT === null) firstChunkT = ((Date.now() - t0) / 1000).toFixed(1)
        }
      } catch {}
    }
  })
  res.on('end', () => {
    console.log('stream end at', ((Date.now() - t0) / 1000).toFixed(1) + 's')
    console.log('events:', JSON.stringify(events))
    console.log('first chunk at:', firstChunkT + 's')
  })
})

req.on('error', (e) => console.error('error:', e.message))
req.write(body)
req.end()
