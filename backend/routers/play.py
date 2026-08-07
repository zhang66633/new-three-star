# -*- coding: utf-8 -*-
"""
/api/play —— 叙事游戏主接口（新三国 星空）
============================================
Phase 1: POST /api/play/step 返回非流式 JSON
Phase 4: 改为 SSE 流式（scene/chunk/player/state/options/phase/done）
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from engine.graph import run_step

router = APIRouter()


class PlayRequest(BaseModel):
    action: str = ""
    game_state: dict = Field(default_factory=dict)


@router.post("/play/step")
async def play_step(req: PlayRequest):
    """跑一轮叙事。Phase 1 返回非流式 JSON。"""
    result = await run_step(req.game_state, req.action)
    last = result.get("last_output") or {}
    return {
        "narrative": last.get("narrative", ""),
        "options": last.get("options", []),
        "state_updates": last.get("state_updates", {}),
        "game_state": result,
    }
