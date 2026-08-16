import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import graph, worlds, play, archive
from db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="新三国·星空 叙事游戏", version="3.0.0", lifespan=lifespan)

# ── CORS：收敛为已知前端来源（默认本地开发 + 可配置生产域名）──
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    # X-API-Key：BYOK（用户自带 LLM 密钥）经该请求头传递，必须放行预检
    allow_headers=["Content-Type", "X-API-Key"],
)

# ── 简单限流（每 IP 窗口内最大请求数，防 LLM 额度被无限消耗）──
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "30"))        # 窗口内最大请求数
RATE_WINDOW = int(os.getenv("RATE_WINDOW", "60"))      # 窗口秒数
_rate_hits: dict[str, list[float]] = {}


def _client_ip(request: Request) -> str:
    """真实客户端 IP：nginx/vite 代理后直连 peer 恒为 127.0.0.1，会退化为全局单桶。

    仅在直连 peer 是本机 loopback（可信代理）时采信 X-Forwarded-For 最左项，
    防客户端绕过代理直连时伪造头规避限流。
    """
    peer = request.client.host if request.client else "unknown"
    if peer in ("127.0.0.1", "::1"):
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            first = fwd.split(",")[0].strip()
            if first:
                return first
    return peer


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    # healthcheck 豁免（容器健康检查频繁轮询，不计入玩家限流，防误 429）
    if request.url.path == "/api/health":
        return await call_next(request)
    client = _client_ip(request)
    now = time.time()
    # 清理窗口外记录（.get 而非 defaultdict：空键不驻留，防内存随 IP 累积）
    hits = [t for t in _rate_hits.get(client) or [] if t >= now - RATE_WINDOW]
    if len(hits) >= RATE_LIMIT:
        return JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后再试"})
    hits.append(now)
    _rate_hits[client] = hits
    return await call_next(request)


app.include_router(graph.router, prefix="/api")
app.include_router(worlds.router, prefix="/api")
app.include_router(play.router, prefix="/api")
app.include_router(archive.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "new-three-explorer"}


if __name__ == "__main__":
    import uvicorn
    # reload=True：后端代码改动自动重启（watchfiles），开发期免手动重启。
    # 用 import-string 形式（"main:app"）而非 app 对象，reload 才能正确工作。
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
