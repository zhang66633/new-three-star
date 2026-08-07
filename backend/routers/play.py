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

实现：引擎先完整跑完（收集 chunks），再分块流式发送——
validate 需完整叙事判定，真流式（边生成边发）需重构校验，后置优化。
"""
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from engine.graph import run_step

router = APIRouter()


class PlayRequest(BaseModel):
    action: str = ""
    game_state: dict = Field(default_factory=dict)
    tension: int = 0  # 玩家所选选项的历史干预度（0-100）


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _chunk_text(text: str, size: int = 40) -> list[str]:
    """把文本切成 40 字/块（SSE chunk 粒度）"""
    return [text[i:i + size] for i in range(0, len(text), size)] or [""]


async def _step_events(req: PlayRequest):
    """生成 SSE 事件流：引擎跑完 → 分块流式发送"""
    # 引擎内收集 chunks（on_chunk 回调）
    collected: list[str] = []

    def on_chunk(text: str):
        # 过滤 markdown 围栏
        if "```" in text:
            text = text.replace("```json", "").replace("```", "")
        if text.strip():
            collected.append(text)

    result = await run_step(req.game_state, req.action, req.tension, stream_cb=on_chunk)

    last = result.get("last_output") or {}
    ps = result.get("meta", {}).get("plan_summary", {})

    # 1. 场景事件（含 music 标记，前端据此触发关羽之歌等）
    if ps:
        yield _sse({
            "type": "scene",
            "scene": {
                "scene_id": ps.get("scene_id", ""),
                "chapter_label": ps.get("chapter_label", ""),
                "title": ps.get("title", ""),
                "location": ps.get("location", ""),
                "music": ps.get("music", ""),
            },
        })

    # 2. 叙事分块（用解析后的最终叙事，比原始 chunks 更干净）
    final_text = last.get("narrative", "") or "".join(collected)
    for piece in _chunk_text(final_text):
        yield _sse({"type": "chunk", "content": piece})

    # 3. state 快照
    yield _sse({"type": "state", "state": result})

    # 4. options
    yield _sse({"type": "options", "options": last.get("options", [])})

    # 5. phase 报告（调试）
    if last.get("phase_report"):
        yield _sse({"type": "phase", "report": last["phase_report"]})

    # 6. done
    yield _sse({"type": "done"})


@router.post("/play/step")
async def play_step(req: PlayRequest):
    """SSE 流式：叙事分块实时透出，末尾 state/options/done。"""
    return StreamingResponse(
        _step_events(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
