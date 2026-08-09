import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "worlds.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
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
        # 名场面目标机制存档表：关键名场面开始前自动存档（覆盖式，保留最近一档）
        await db.execute("""
            CREATE TABLE IF NOT EXISTS saves (
                id TEXT PRIMARY KEY,
                label TEXT DEFAULT '',
                state_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO worlds (id, name, tagline, concept, graph_json, color) VALUES (?, ?, ?, ?, ?, ?)",
            (world_id, name, tagline, concept, graph_json, color),
        )
        await db.commit()


async def get_all_worlds():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, name, tagline, concept, color, created_at FROM worlds ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_world_graph(world_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT graph_json FROM worlds WHERE id = ?", (world_id,))
        row = await cursor.fetchone()
        return dict(row)["graph_json"] if row else None


# ═════════ 名场面存档（服务端持久化）═════════

async def save_game(save_id: str, state_json: str, label: str = ""):
    """存档：GameState JSON → saves 表（覆盖式，保留最近一档）。"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO saves (id, label, state_json, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (save_id, label, state_json),
        )
        await db.commit()


async def get_game(save_id: str):
    """读档：返回存档的 GameState JSON（None = 无此档）。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT state_json FROM saves WHERE id = ?", (save_id,))
        row = await cursor.fetchone()
        return dict(row)["state_json"] if row else None


# ═════════ 自由沙盒：玩家档案 + 世界档案（见自由沙盒重构设计 §五）═════════

async def save_player(pid: str, world_id: str, player_json: str):
    """存档玩家档案（独立表，每回合快照覆盖）。"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO players (id, world_id, player_json, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (pid, world_id, player_json),
        )
        await db.commit()


async def get_player(pid: str):
    """读玩家档案（None = 无此档）。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT player_json, world_id FROM players WHERE id = ?", (pid,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def save_world_state(wid: str, world_json: str):
    """存档世界档案（独立表，每回合快照覆盖）。"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO world_states (id, world_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (wid, world_json),
        )
        await db.commit()


async def get_world_state(wid: str):
    """读世界档案（None = 无此档）。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT world_json FROM world_states WHERE id = ?", (wid,))
        row = await cursor.fetchone()
        return dict(row)["world_json"] if row else None


async def delete_player(pid: str):
    """删除玩家档案（新开历险时放弃旧档，防 players 表累积孤儿档）。"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM players WHERE id = ?", (pid,))
        await db.commit()
