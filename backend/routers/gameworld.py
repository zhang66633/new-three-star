import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from game_world.validator import validate
from game_world.nodes import NODE_DATA, MAIN_NODES
from game_world.story_state import StoryState
from game_world.director import direct, advance
from game_world.writer import write

router = APIRouter()


class NarrativeRequest(BaseModel):
    world_id: str
    action: str = ""  # user's choice or free text, empty = start new game
    history: list = []  # previous messages [{role, content}]
    start_node: str = ""  # 首turn指定起始节点（如"官渡之战"），空=默认曹操献刀
    identity: str = ""  # 已废弃：身份改由节点"观众身份"字段配死，此字段仅为兼容旧前端保留
    state: dict = {}  # 故事状态，前端持有并回传，首轮为空


def _detect_node(context: str) -> str:
    """从上下文中检测最近涉及的主线节点（state 缺失时的兜底）。"""
    found = ""
    for node in MAIN_NODES:
        if node in context:
            found = node  # 取最后出现的
    return found


# v3.2: 自由输入意图检测（关键词匹配）
def _detect_intent(action: str) -> str:
    """检测自由输入的意图类型。"""
    action_lower = action.strip()
    # 探索/观察
    if any(kw in action_lower for kw in ["看", "观察", "环顾", "打量", "查看", "周围", "附近", "哪里"]):
        return "explore"
    # 对话
    if any(kw in action_lower for kw in ["问", "说", "告诉", "回答", "对", "跟"]):
        return "talk"
    # 使用道具
    if any(kw in action_lower for kw in ["用", "拿出", "掏出", "取出", "拔", "使"]):
        return "use_item"
    # 逃跑/回避
    if any(kw in action_lower for kw in ["跑", "逃", "离开", "退", "躲", "溜"]):
        return "flee"
    # 攻击/对抗
    if any(kw in action_lower for kw in ["打", "杀", "刺", "砍", "攻击", "动手"]):
        return "attack"
    return "other"


# v3.2: 根据意图更新叙事旗标和玩家倾向
def _update_flags(state: StoryState, action: str, intent: str):
    """根据玩家行动更新状态旗标。Ink 式 state-accumulation。"""
    # 记录选择历史
    state.choice_history.append({
        "turn": state.turn,
        "action": action[:100],
        "intent": intent,
        "scene": state.scene_index,
        "node": state.node,
    })

    # 根据意图设置旗标
    if intent == "attack":
        state.flags["acted_aggressively"] = True
        state.corruption = min(100, state.corruption + 5)  # 暴力增加腐败
    elif intent == "flee":
        state.flags["avoided_conflict"] = True
    elif intent == "talk":
        state.flags["talked_to_npc"] = True
    elif intent == "explore":
        state.flags["explored_area"] = True

    # 检测特定事件
    if "董卓" in action:
        state.flags["defied_dong_zhuo"] = True
        state.corruption = min(100, state.corruption + 10)
    if "曹操" in action:
        state.flags["interacted_with_cao_cao"] = True
    if "杀" in action or "刺" in action:
        state.flags["attempted_violence"] = True
        state.corruption = min(100, state.corruption + 15)

    # 计算玩家倾向（最近3次选择中最多的意图）
    recent = [c["intent"] for c in state.choice_history[-3:]]
    if recent:
        from collections import Counter
        dominant = Counter(recent).most_common(1)[0][0]
        attitude_map = {
            "attack": "aggressive",
            "flee": "cautious",
            "talk": "diplomatic",
            "explore": "curious",
            "use_item": "pragmatic",
        }
        state.player_attitude = attitude_map.get(dominant, state.player_attitude)


def _key_error_stream():
    """缺少API密钥时的友好提示流。"""
    async def gen():
        msg = "请先回到星图，点击'设置'星球，填入你自己的DeepSeek密钥。"
        yield f"data: {json.dumps({'type': 'chunk', 'content': f'[ERR] {msg}'}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    return gen()


@router.post("/gameworld/narrative")
async def narrative(req: NarrativeRequest, request: Request):
    """互动叙事引擎：Director定拍 → Writer渲染 → Validator验收 → 代码推进state。
    节拍推进、道具/台词锁定全在代码里，LLM 只写本拍文字。"""
    # 每个玩家用自己的DeepSeek密钥（X-API-Key头），服务端不兜底
    api_key = request.headers.get("x-api-key", "").strip()
    if not api_key:
        return StreamingResponse(_key_error_stream(), media_type="text/event-stream")
    # DeepSeek 模型选择（设置星球下拉，随 X-DEEPSEEK-MODEL 头传入）
    ds_model = request.headers.get("x-deepseek-model", "").strip()
    is_first_turn = len(req.history) == 0
    state = StoryState.from_dict(req.state)

    # 判定当前节点：首turn用 start_node；其后优先用 state（代码持有的真相源）；
    # state 无节点时（兼容未升级前端）从全历史检测
    if is_first_turn:
        node = req.start_node or "曹操献刀"
    else:
        node = state.node
        if not node:
            ctx = " ".join(m.get("content", "") for m in req.history) + " " + req.action
            node = _detect_node(ctx)
    # 兜底：节点无效则回到开场节点
    state.node = node if node in NODE_DATA else "曹操献刀"

    # v3.2: 如果不是首轮，跟踪玩家选择和意图
    if not is_first_turn and req.action:
        intent = _detect_intent(req.action)
        _update_flags(state, req.action, intent)

    brief = direct(state, req.action)

    async def generate():
        try:
            draft = await write(brief, state, req.history, req.action, is_first_turn, api_key=api_key, model=ds_model or None)
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
