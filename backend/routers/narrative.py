import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services.validator import validate
from knowledge.nodes import NODE_DATA, MAIN_NODES
from services.story_state import StoryState
from services.director import direct, advance
from services.writer import write

router = APIRouter()


class NarrativeRequest(BaseModel):
    world_id: str
    action: str = ""  # user's choice or free text, empty = start new game
    history: list = []  # previous messages [{role, content}]
    start_node: str = ""  # 首turn指定起始节点（如"官渡之战"），空=默认曹操献刀
    identity: str = ""  # 首turn指定观众身份（如"谋士""武将"），空=AI随机分配
    state: dict = {}  # 故事状态，前端持有并回传，首轮为空


def _detect_node(context: str) -> str:
    """从上下文中检测最近涉及的主线节点（state 缺失时的兜底）。"""
    found = ""
    for node in MAIN_NODES:
        if node in context:
            found = node  # 取最后出现的
    return found


@router.post("/worldview/narrative")
async def narrative(req: NarrativeRequest):
    """互动叙事引擎：Director定拍 → Writer渲染 → Validator验收 → 代码推进state。
    节拍推进、道具/台词锁定全在代码里，LLM 只写本拍文字。"""
    is_first_turn = len(req.history) == 0
    state = StoryState.from_dict(req.state)

    # 判定当前节点：首turn用 start_node；其后优先用 state（代码持有的真相源）；
    # state 无节点时（兼容未升级前端）从全历史检测
    if is_first_turn:
        node = req.start_node or "曹操献刀"
        state.identity = req.identity
    else:
        node = state.node
        if not node:
            ctx = " ".join(m.get("content", "") for m in req.history) + " " + req.action
            node = _detect_node(ctx)
    # 兜底：节点无效则回到开场节点
    state.node = node if node in NODE_DATA else "曹操献刀"

    brief = direct(state, req.action)

    async def generate():
        try:
            draft = await write(brief, state, req.history, req.action, is_first_turn)
        except Exception:
            draft = ""

        if not draft.strip():
            yield f"data: {json.dumps({'type': 'chunk', 'content': '[ERR] 世界意志沉默。请稍后再试。'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # 确定性验收：道具名强制、选项截断、角色名纠错、名字混用、分行合并
        final_text = validate(draft, state.node)
        # 代码推进状态（一轮一拍 + 道具登记）
        new_state = advance(state, brief)

        chunk_size = 40
        for i in range(0, len(final_text), chunk_size):
            yield f"data: {json.dumps({'type': 'chunk', 'content': final_text[i:i+chunk_size]}, ensure_ascii=False)}\n\n"
        # 回传新状态，前端保存后下轮带回
        yield f"data: {json.dumps({'type': 'state', 'state': new_state.to_dict()}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
