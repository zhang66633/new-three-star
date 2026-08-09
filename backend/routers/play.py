# -*- coding: utf-8 -*-
"""
/api/play —— 叙事游戏主接口（新三国 星空 · SSE 流式）
======================================================
协议（Phase 4 定型）:
  data: {"type":"scene","scene":{...}}        # 场景切换时
  data: {"type":"chunk","content":"..."}      # 叙事分块（40字/块）
  data: {"type":"state","state":{...}}        # 完整 GameState 快照
  data: {"type":"options","options":[...]}    # 选项（tension 标注）
  data: {"type":"phase","report":{...}}       # 8PHASE 校验报告（调试）
  data: {"type":"done"}

实现：先让引擎完整跑完（narrate→validate→rewrite→corrector→remember），
再按**最终校验后的 narrative** 分块流式发送。这样用户看到的是重写后的定稿，
而不是被校验丢弃的失败草稿（早期边生成边发会让 rewrite 的草稿错位到前端）。
前端在生成期间展示"天意正在推演"思维链阶段，chunk 到达后再转流式。
"""
import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from engine.graph import run_step

logger = logging.getLogger(__name__)

router = APIRouter()

# 世界档案字段（自由沙盒 §五）：世界侧独立推进的状态，save_player 时拆写 world_states 表
_WORLD_STATE_KEYS = ("world_date", "world_events", "location_state", "rumor_unlocked")


class PlayRequest(BaseModel):
    action: str = Field(default="", max_length=500)  # 防超大 action 消耗 token
    game_state: dict = Field(default_factory=dict)
    tension: int = Field(default=0, ge=0, le=100)    # 玩家所选选项的历史干预度


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


async def _step_events(req: PlayRequest):
    """生成 SSE 事件流——协议顺序: scene → chunk* → state → options → phase → done"""
    from engine.state import from_dict
    from engine.director import choose_scene

    # ── SSE keepalive（每 15s 发心跳注释，防 nginx/proxy 60s 超时）──
    events: asyncio.Queue = asyncio.Queue()
    DONE = object()
    keepalive_active = True

    async def keepalive():
        while keepalive_active:
            await asyncio.sleep(15)
            if keepalive_active:
                events.put_nowait(("__keepalive__", None))

    # ── 1. 场景事件（先于 LLM 生成，确保 scene 在 chunk 之前到达前端）──
    try:
        pre_state = from_dict(req.game_state)
        pre_plan = choose_scene(pre_state)
    except Exception as e:
        logger.exception("choose_scene 失败")
        yield _sse({"type": "err", "content": "世界短暂失序，请重试"})
        yield _sse({"type": "done"})
        return
    yield _sse({
        "type": "scene",
        "scene": {
            "scene_id": pre_plan.scene_id,
            "chapter_label": pre_plan.chapter_label,
            "title": pre_plan.title,
            "location": pre_plan.location,
            "atmo": pre_plan.atmo,
            "music": pre_plan.music,
        },
    })

    async def run_and_finish():
        try:
            result = await run_step(req.game_state, req.action, req.tension)  # 不传 stream_cb：引擎完整跑完
            await events.put(("__result__", result))
        except Exception as e:
            logger.exception("play/step 引擎异常")
            await events.put(("__error__", "生成失败，请重试"))  # 不向客户端泄漏内部异常
        finally:
            await events.put(DONE)

    runner = asyncio.create_task(run_and_finish())
    keeper = asyncio.create_task(keepalive())
    try:
        while True:
            item = await events.get()
            if item is DONE:
                break
            kind, payload = item
            if kind == "__keepalive__":
                yield ": heartbeat\n\n"
            elif kind == "__result__":
                result = payload
                last = result.get("last_output") or {}
                # 按最终校验后的 narrative 分块流式发送
                narrative = last.get("narrative", "")
                for i in range(0, len(narrative), 40):
                    yield _sse({"type": "chunk", "content": narrative[i:i + 40]})
                # 状态（记忆+人物）先于选项
                yield _sse({"type": "state", "state": result})
                yield _sse({"type": "options", "options": last.get("options", [])})
                if last.get("phase_report"):
                    yield _sse({"type": "phase", "report": last["phase_report"]})
                yield _sse({"type": "done"})
            elif kind == "__error__":
                yield _sse({"type": "err", "content": payload})
                yield _sse({"type": "done"})
            else:
                yield payload
    finally:
        # 客户端断连/异常时也清理：取消 keepalive；runner 未完成则取消（停止占用 LLM 额度），
        # 而非干等它跑完（避免断连后仍空转约 2 分钟）
        keepalive_active = False
        keeper.cancel()
        if not runner.done():
            runner.cancel()
        for t in (keeper, runner):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass


@router.post("/play/step")
async def play_step(req: PlayRequest):
    """SSE 流式：引擎完整跑完 → 最终叙事分块实时透出，末尾 state/options/done。"""
    return StreamingResponse(
        _step_events(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class PlayerSaveRequest(BaseModel):
    pid: str = Field(default="", max_length=64)
    game_state: dict = Field(default_factory=dict)


@router.post("/play/save_player")
async def play_save_player(req: PlayerSaveRequest):
    """自由沙盒自动快照：完整 GameState → players 表（每拍前端保存，覆盖式）。

    自由沙盒 §五：玩家档案独立于世界档案——这里把世界侧字段拆写 world_states 表，
    加载时 load_player 合并（world_states 权威覆盖世界字段）。
    """
    if not req.pid:
        return {"ok": False, "content": "缺少玩家标识"}
    from db import save_player, save_world_state
    gs = req.game_state or {}
    # 世界档案 = 世界侧独立推进的状态（日期/事件队列/位置/传闻解锁），不随玩家档案走
    world_json = {k: gs.get(k) for k in _WORLD_STATE_KEYS if k in gs}
    await save_world_state(req.pid, json.dumps(world_json, ensure_ascii=False))
    await save_player(req.pid, "default", json.dumps(gs, ensure_ascii=False))
    return {"ok": True}


class PlayerLoadRequest(BaseModel):
    pid: str = Field(default="", max_length=64)


@router.post("/play/load_player")
async def play_load_player(req: PlayerLoadRequest):
    """断点续玩：读玩家档案 + 合并世界档案（world_states 权威覆盖世界字段；无档返回 has_save=False）。

    玩家档案为主快照，世界档案独立持久化（日期/事件/位置随世界走），加载时世界侧以
    world_states 为准——即使玩家档案的世界字段被旧逻辑污染，也以独立世界档案覆盖。
    """
    if not req.pid:
        return {"ok": False, "has_save": False}
    from db import get_player, get_world_state
    row = await get_player(req.pid)
    if row is None:
        return {"ok": False, "has_save": False}
    state = json.loads(row["player_json"])
    wj = await get_world_state(req.pid)
    if wj:
        world = json.loads(wj)
        for k in _WORLD_STATE_KEYS:
            if k in world:
                state[k] = world[k]
    return {"ok": True, "has_save": True, "state": state}


class PlayerDeleteRequest(BaseModel):
    pid: str = Field(default="", max_length=64)


@router.post("/play/delete_player")
async def play_delete_player(req: PlayerDeleteRequest):
    """新开历险：删除旧玩家档案（放弃当前进度），防 players 表累积孤儿档。"""
    if not req.pid:
        return {"ok": False}
    from db import delete_player
    await delete_player(req.pid)
    return {"ok": True}
