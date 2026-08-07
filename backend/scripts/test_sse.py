# -*- coding: utf-8 -*-
"""SSE 流式验证脚本：逐行读取，统计事件（无读超时问题）"""
import json
import socket
import time
import urllib.request
from collections import Counter

socket.setdefaulttimeout(600)  # 10 分钟

req = urllib.request.Request(
    'http://localhost:8001/api/play/step',
    data=json.dumps({'action': '', 'game_state': {}, 'tension': 0}).encode('utf-8'),
    headers={'Content-Type': 'application/json'})

t0 = time.time()
events = []
chunks = []
first_t = None
with urllib.request.urlopen(req) as r:
    for raw in r:
        line = raw.decode('utf-8').strip()
        if line.startswith('data: '):
            try:
                ev = json.loads(line[6:])
                events.append(ev['type'])
                if ev['type'] == 'chunk':
                    if first_t is None:
                        first_t = time.time() - t0
                    chunks.append(ev['content'])
                if ev['type'] == 'done':
                    break
            except Exception:
                pass

print(f'总耗时: {time.time()-t0:.1f}s | 首 chunk: {first_t:.1f}s')
print(f'事件: {dict(Counter(events))}')
print(f'chunk 数: {len(chunks)} | 含围栏: {any("```" in c for c in chunks)}')
if chunks:
    print(f'首 chunk: {chunks[0][:40]}...')
    print(f'末 chunk: {chunks[-1][-40:]}')
print('done 收到:', 'done' in events)
