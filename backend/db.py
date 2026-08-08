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
