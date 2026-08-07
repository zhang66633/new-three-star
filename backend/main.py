from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import graph, worldview, worlds, narrative, tianyi, play, archive
from db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="新三国世界观探索器", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graph.router, prefix="/api")
app.include_router(worldview.router, prefix="/api")
app.include_router(worlds.router, prefix="/api")
app.include_router(narrative.router, prefix="/api")
app.include_router(tianyi.router, prefix="/api")
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
