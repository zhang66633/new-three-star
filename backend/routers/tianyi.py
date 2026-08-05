"""
天意路由（v3.1）—— 玩家 = 天意，输入 prompt 改写世界
========================================================
融入天意理论、梗文化、角色人设。新增路由，与旧 narrative 并存。
"""
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services.engine import process
from services.story_state import StoryState
from services.writer_tianyi import write
from knowledge.nodes import NODE_DATA

router = APIRouter()


class TianyiRequest(BaseModel):
    action: str = ""          # 天意注入的 prompt
    history: list = []
    state: dict = {}
    start_node: str = ""      # 首轮指定起始节点，空=默认曹操献刀


@router.post("/tianyi")
async def tianyi(req: TianyiRequest):
    is_first_turn = len(req.history) == 0
    state = StoryState.from_dict(req.state)

    if is_first_turn:
        state.node = req.start_node if req.start_node in NODE_DATA else "曹操献刀"
        state.scene_index = 0

    print(f"[Tianyi] turn={state.turn} node={state.node} beat={state.scene_index} "
          f"deviation={state.deviation}% corruption={state.tianyi_corruption} "
          f"injection={req.action[:60]}")

    context = process(state, req.action)

    async def generate():
        try:
            draft = await write(state, req.history, req.action, context=context)
        except Exception:
            draft = ""

        if not draft.strip():
            yield f"data: {json.dumps({'type': 'chunk', 'content': '[ERR] 世界无响应。天意暂时无法连接。'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # 流式输出：按40字分块发送
        chunk_size = 40
        for i in range(0, len(draft), chunk_size):
            yield f"data: {json.dumps({'type': 'chunk', 'content': draft[i:i+chunk_size]}, ensure_ascii=False)}\n\n"

        # 回传状态 + PHASE 校验链
        state_dict = state.to_dict()
        state_dict["special_event"] = context.special_event
        state_dict["phase"] = context.phase_checks
        yield f"data: {json.dumps({'type': 'state', 'state': state_dict}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")