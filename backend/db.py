import aiosqlite
import os
from contextlib import asynccontextmanager

# 可经 NEW_THREE_DB 环境变量覆盖（docker-compose 挂持久卷到 /data，防容器重建清空存档）
DB_PATH = os.getenv("NEW_THREE_DB", os.path.join(os.path.dirname(__file__), "worlds.db"))


@asynccontextmanager
async def _db():
    """打开连接 + WAL/busy_timeout：并发写等锁而非直接 'database is locked'。

    WAL 允许读写并发；busy_timeout 5s 让并发写者排队等待；synchronous=NORMAL 在 WAL 下足够安全且更快。
    """
    db = await aiosqlite.connect(DB_PATH)
    try:
        cur = await db.execute("PRAGMA journal_mode=WAL")
        await cur.fetchone()
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute("PRAGMA synchronous=NORMAL")
        yield db
    finally:
        await db.close()


async def init_db():
    async with _db() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS worlds (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                tagline TEXT NOT NULL,
                concept TEXT NOT NULL,
                graph_json TEXT NOT NULL,
                color TEXT DEFAULT '#aabbff',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 自由沙盒：玩家档案表（独立于世界档案，见自由沙盒重构设计 §五）
        await db.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id TEXT PRIMARY KEY,
                world_id TEXT NOT NULL,        -- 绑定世界档案 id
                player_json TEXT NOT NULL,     -- 玩家数据快照（资产/属性/关系/声誉/成就）
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 自由沙盒：世界档案表（独立推进的世界状态）
        await db.execute("""
            CREATE TABLE IF NOT EXISTS world_states (
                id TEXT PRIMARY KEY,
                world_json TEXT NOT NULL,      -- 世界状态快照（日期/事件队列/NPC状态/位置）
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def save_world(world_id: str, name: str, tagline: str, concept: str, graph_json: str, color: str = "#aabbff"):
    async with _db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO worlds (id, name, tagline, concept, graph_json, color) VALUES (?, ?, ?, ?, ?, ?)",
            (world_id, name, tagline, concept, graph_json, color),
        )
        await db.commit()


async def get_all_worlds():
    async with _db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, name, tagline, concept, color, created_at FROM worlds ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_world_graph(world_id: str):
    async with _db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT graph_json FROM worlds WHERE id = ?", (world_id,))
        row = await cursor.fetchone()
        return dict(row)["graph_json"] if row else None


# ═════════ 自由沙盒：玩家档案 + 世界档案（见自由沙盒重构设计 §五）═════════

async def save_player(pid: str, world_id: str, player_json: str):
    """存档玩家档案（独立表，每回合快照覆盖）。"""
    async with _db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO players (id, world_id, player_json, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (pid, world_id, player_json),
        )
        await db.commit()


async def get_player(pid: str):
    """读玩家档案（None = 无此档）。"""
    async with _db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT player_json, world_id FROM players WHERE id = ?", (pid,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def save_world_state(wid: str, world_json: str):
    """存档世界档案（独立表，每回合快照覆盖）。"""
    async with _db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO world_states (id, world_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (wid, world_json),
        )
        await db.commit()


async def get_world_state(wid: str):
    """读世界档案（None = 无此档）。"""
    async with _db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT world_json FROM world_states WHERE id = ?", (wid,))
        row = await cursor.fetchone()
        return dict(row)["world_json"] if row else None


async def delete_player(pid: str):
    """删除玩家档案 + 关联世界档案（新开历险时放弃旧档，防两表累积孤儿档）。"""
    async with _db() as db:
        await db.execute("DELETE FROM players WHERE id = ?", (pid,))
        await db.execute("DELETE FROM world_states WHERE id = ?", (pid,))
        await db.commit()
