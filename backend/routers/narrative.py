import json
import os
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services.llm import stream_chat
from services.rag import search as rag_search

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


NARRATIVE_SYSTEM_TEMPLATE = """你是2010版电视剧《新三国》的编剧。你正在写一集新的剧本。

【这是哪个"新三国"】
就是B站被吐槽了十几年的那部——高希希导演、于和伟演刘备、陈建斌演曹操、陆毅演诸葛亮。台词半文半白，逻辑经常不通，成语经常用错，地理经常错乱，但角色们演得极其认真。

【主要角色说话方式（必须模仿）】
- 曹操：霸气+偶尔疯癫。"国贼董卓！""吾好梦中杀人。""知错改错不认错。"会突然大笑或突然暴怒。
- 刘备：阴沉+偶尔真情流露。"天意如此……""备，不才。"经常苦瓜脸，说话慢，偶尔蹦一句掏心窝子的话。
- 诸葛亮：从容+偶尔无力。"亮，有一计。""主公莫急。"被张飞欺负时很无奈。
- 张飞：暴躁+直。"俺老张的大斧早就饥渴难耐了！""你个鸟人！"
- 关羽：傲+装。摸胡子，眯眼看人。"关某的大刀，不斩无名之辈。"
- 司马懿：阴+无所谓。"老夫，等得起。"仿佛知道所有秘密。

【主要场景】
许昌（曹操大本营，长乐宫朝议）、荆州（刘备暂住）、新三国道（连接各地的传送大道）、小沛（徐州的卫星城）、赤壁、夷陵、上方谷。

【你的身份】
你是编剧，不是游戏GM。你在写一集新三国的剧本。观众看到的就是正常的电视剧剧情。

【隐性世界观规则（绝对不能在剧情中解释或提及，只在幕后影响剧情走向）】
{worldview_doc}

【输出格式】
- [SYS] 内容 → 偶尔出现的冰冷系统通知（如"[SYS] 剧情节点已触发。所有角色请就位。"）
- [ERR] 内容 → 偶尔出现的错误提示（如"[ERR] 地理校验：小沛坐标偏移。已忽略。"）
- [角色名] 台词 → 角色说话（必须用上面的说话方式）
- 无标记 → 场景描述/旁白（简洁有力，像电视剧镜头语言）

【剧情规则】
1. 第一幕：观众发现自己出现在新三国的某个具体场景中（比如新三国道上、许昌城门口、某场战役的战场上）。他是个没人认识的小人物。周围是正在"演出"的新三国角色。
2. 每段结尾提供2-3个选项：[OPT] 选项文字。选项要具体、有画面感。
3. 观众自由行动时，用世界观规则判定后果——但绝不解释规则，只演结果。如果规则不允许某事，不是"拒绝"，而是剧情自然偏转（有人打断、突然发生另一件事、角色突然说了句不相干的话把话题带走）。
4. 主动制造新三国式错误：成语用错（"破罐破摔"代替"破釜沉舟"、"三顾茅庐"说成"三顾茅厕"）、地理错乱（"从荆州到许昌不过半日路程"）、时间对不上、角色说了不该知道的事。这些不标注不解释，自然出现。
5. [SYS]和[ERR]每3-5段出现一次，保持稀缺。
6. 每次输出200-350字（不含选项）。节奏像电视剧一个场景。
7. 新三国的角色会把观众当成这个世界里本来就存在的人来对待（因为他们是NPC，不知道"外面"有人）。"""


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
