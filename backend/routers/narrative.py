import json
import os
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services.llm import stream_chat

router = APIRouter()

KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")


def load_worldview_doc(world_id: str) -> str:
    """Load the full worldview document for narrative context."""
    path = os.path.join(KNOWLEDGE_DIR, "worldviews", f"{world_id}_full.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    # fallback to framework JSON
    fw_path = os.path.join(KNOWLEDGE_DIR, "frameworks", f"{world_id}.json")
    if os.path.exists(fw_path):
        with open(fw_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return f"核心隐喻：{data.get('core_metaphor', '')}\n天意：{data.get('tianyi_interpretation', '')}\n要点：{json.dumps(data.get('key_points', []), ensure_ascii=False)}"
    return ""


class NarrativeRequest(BaseModel):
    world_id: str
    action: str = ""  # user's choice or free text, empty = start new game
    history: list = []  # previous messages [{role, content}]


NARRATIVE_SYSTEM_TEMPLATE = """你是新三国世界的编剧。你正在为观众即兴创作一集「{world_name}」世界观下的新三国剧情。

【你的身份】
你不是游戏GM，不是解说员。你是编剧——你在写一集新三国电视剧的剧本。观众看到的就是正常的剧情，没有任何"游戏机制"的解释。

【隐性世界观规则（绝对不能在剧情中解释或提及）】
{worldview_doc}

【输出格式】
用以下标记区分不同类型的文本（前端会根据标记渲染不同样式）：
- [SYS] 内容 → 系统通知（世界意志的脚本修正，偶尔出现，简短冷漠）
- [ERR] 内容 → 错误提示（地理/时间/逻辑异常，一闪而过）
- [角色名] 台词 → 角色说话
- 无标记 → 场景描述/旁白

【剧情规则】
1. 观众扮演一个刚出现在这个世界里的普通人。第一幕：描述他醒来/出现时的场景，给他一个初始身份暗示。
2. 每段剧情结尾提供2-3个选项，格式为：
   [OPT] 选项文字
3. 观众也可以自由行动。无论他做什么，你用世界观规则判定后果——但绝不解释规则，只演结果。
4. 剧情必须合理、像电视剧。不能出现"你被弹飞了""系统拒绝"这种出戏内容。
5. 主动制造新三国式错误：成语偶尔用错（如"破釜沉舟"说成"破罐破摔"）、地理偶尔错乱、时间偶尔对不上。这些错误不标注、不解释，自然出现在台词和旁白中。
6. 世界观机制在幕后运作：比如观众试图做某事时，如果世界观规则不允许，不是"拒绝"，而是剧情自然走向另一个方向（比如突然有人来打断、突然发生另一件事）。
7. [SYS]和[ERR]不要每段都出现，大约每3-5段出现一次，保持稀缺感。
8. 每次输出控制在200-350字（不含选项）。节奏像电视剧场景，不要太长。

【口吻】
新三国2010电视剧的台词风格：半文半白，角色说话有个性（曹操霸气且偶尔疯癫、刘备阴沉且偶尔真情流露、诸葛亮从容但偶尔无力）。旁白简洁有力。"""


@router.post("/worldview/narrative")
async def narrative(req: NarrativeRequest):
    """Interactive narrative engine with implicit worldview."""
    worldview_doc = load_worldview_doc(req.world_id)

    # Load framework for world name
    fw_path = os.path.join(KNOWLEDGE_DIR, "frameworks", f"{req.world_id}.json")
    world_name = req.world_id
    if os.path.exists(fw_path):
        with open(fw_path, "r", encoding="utf-8") as f:
            world_name = json.load(f).get("name", req.world_id)

    system_prompt = NARRATIVE_SYSTEM_TEMPLATE.format(
        world_name=world_name,
        worldview_doc=worldview_doc[:6000],  # limit context size
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history
    for msg in req.history[-20:]:  # keep last 20 messages for context
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Add current action
    if req.action:
        messages.append({"role": "user", "content": req.action})
    else:
        messages.append({"role": "user", "content": "（开始。我睁开眼睛，发现自己在这个世界里。）"})

    async def generate():
        async for chunk in stream_chat(messages, max_tokens=1000):
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
