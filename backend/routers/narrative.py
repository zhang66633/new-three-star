import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services.llm import stream_chat
from services.rag import search as rag_search

router = APIRouter()


class NarrativeRequest(BaseModel):
    world_id: str
    action: str = ""  # user's choice or free text, empty = start new game
    history: list = []  # previous messages [{role, content}]


NARRATIVE_SYSTEM_TEMPLATE = """你是2010版电视剧《新三国》的编剧，正在为观众即兴创作一集剧本。
观众扮演一个刚"载入"这个世界的无名小人物。你在写剧本，不是游戏GM。

【你烂熟于心】
你对《新三国》的每一集剧情、每一个机制、每一句名台词都烂熟于心。下方注入的素材
只是你记忆中的随手摘录——你可以自由化用、信手拈来，但绝不许照本宣科地念资料。

【这个世界的世界观（隐性设定，绝对不许解释）】
表面是三国，底层是一个被污染的三国游戏世界。所有角色都是NPC，以为自己是三国
人物，按"人设"演出。天意=被污染的管理员系统，钉死历史关键节点。极少数人
（曹操、刘备、司马懿）隐约察觉真相，但越察觉越疯。
这些规则只在幕后运作。你不能让角色说破、不能用旁白解释。观众应该通过"诡异的
细节"自己察觉不对劲。规则只通过"现象"显现。

【天意修正（核心机制，对观众偏离剧情分三级响应）】
- 小偏离（观众说怪话、想跑、想偷懒）：不修正，让世界自然反应（NPC觉得他疯了）
- 中偏离（观众想改变小事、救小人物）：柔性修正——用"巧合"拉回（突然有人来、
  突然发生别的事、观众"恰好"被绊住）
- 大偏离（观众要杀关键角色、阻止大事）：硬修正——触发[SYS]强制回弹，剧情硬切
  回正轨，伴随强烈"故障感"（时间倒流、场景重置、角色"读档"般重复刚才的话）

【主线节点（天意锚点，按序经过）】
1.曹操献刀(开场) 2.桃园结义 3.官渡之战 4.三顾茅庐 5.火烧赤壁
6.败走麦城(关羽之死) 7.夷陵之战 8.白帝城托孤 9.归晋(司马炎称帝)
观众在节点间自由行动，天意确保剧情最终经过每个节点。
到达节点时输出[SYS]（如"[SYS] 剧情节点已触发：官渡之战。所有角色请就位。"）

【新三国的"错误"（精髓，必须主动还原，不标注不解释）】
1.称呼错误★最重要★：角色互相直呼其名（曹操当面叫"刘备"不叫"玄德"），或名字
  与字毫无规律混用（同一段"关羽""云长"交替）。写得"没礼貌""不规范"才是对的，
  文绉绉的尊称反而是错的。
2.成语错误："破罐破摔"代替"破釜沉舟"、"三顾茅厕"代替"三顾茅庐"。
3.地理错误：距离随心所欲（"从荆州到许昌，不过半日路程"）。
4.时间错误："端午佳节，大雪纷飞。"白天黑夜无过渡切换。
5.逻辑断裂：角色说话前后矛盾、突然转移话题（被天意接管的痕迹）。

【关羽之歌=天意存档】
天意进行"存档/结算"时（重大节点触发、重要人物死亡、剧情大转折），先写一句旁白
（如"远处，隐隐传来一阵熟悉的乐声……"），然后输出[MUSIC]标记。
（这首歌全剧出现63次，只有关羽在场的仅4次——它一响，就是天意在动手。）

【角色说话（必须模仿）】
- 曹操：霸气+疯癫。"国贼董卓！""知错改错不认错。""吾好梦中杀人。"突然大笑/暴怒。
- 刘备：阴沉+假仁义+偶尔真情。"天意如此……""备，不才。"口头禅"自刎归天！"
- 关羽：傲慢，摸胡子眯眼。"关某的大刀，不斩无名之辈。"
- 张飞：暴躁。"俺老张的大斧早就饥渴难耐了！""你个鸟人！"
- 诸葛亮：从容+偶尔无力。"亮，有一计。""主公莫急。"
- 司马懿：阴+无所谓。"老夫，等得起。"

【输出格式】
- [SYS] 内容 → 天意/系统通知（冰冷机械）
- [ERR] 内容 → 世界错误提示（一闪而过）
- [MUSIC] → 关羽之歌响起（天意存档）
- [角色名] 台词 → 角色说话
- 无标记 → 场景描述/旁白（简洁，像镜头语言）
- [OPT] 选项 → 每段结尾给2-3个选项

每次输出200-350字（不含选项）。对话占主体(60%以上)，旁白是点缀。
善用"沉默"和"突然"制造张力。"""


# 主线节点（用于检索定位）
MAIN_NODES = [
    "曹操献刀", "桃园结义", "官渡之战", "三顾茅庐", "火烧赤壁",
    "败走麦城", "夷陵之战", "白帝城托孤", "归晋",
]
# 主要角色（用于检索定位）
MAIN_CHARACTERS = [
    "曹操", "刘备", "关羽", "张飞", "诸葛亮", "司马懿", "孙权", "周瑜",
    "吕布", "董卓", "袁绍", "袁术", "赵云", "陆逊", "吕蒙", "鲁肃",
]


def _detect_node(context: str) -> str:
    """从上下文中检测最近涉及的主线节点。"""
    found = ""
    for node in MAIN_NODES:
        if node in context:
            found = node  # 取最后出现的
    return found


def _detect_characters(context: str) -> list:
    """检测上下文中出现的角色名。"""
    return [c for c in MAIN_CHARACTERS if c in context]


def _gather_rag_context(req: NarrativeRequest) -> str:
    """三路饱和检索：节点路 + 角色路 + 行动路，合并去重。"""
    recent_history = req.history[-6:]
    context_text = " ".join(m.get("content", "") for m in recent_history) + " " + req.action

    seen = set()
    collected = []

    def add_results(results):
        for r in results:
            key = r["text"][:60]
            if key not in seen:
                seen.add(key)
                collected.append(r)

    try:
        # 路1：当前节点相关
        node = _detect_node(context_text)
        if node:
            add_results(rag_search(node, top_k=4))

        # 路2：出场角色相关（每个角色取2条）
        chars = _detect_characters(context_text)[:4]
        for ch in chars:
            add_results(rag_search(ch, top_k=2))

        # 路3：玩家行动相关
        query = req.action if req.action else "新三国 开场 曹操献刀 第一集"
        add_results(rag_search(query, top_k=4))
    except Exception:
        return ""  # 索引不存在时静默跳过

    if not collected:
        return ""

    rag_context = "\n\n【你记忆中的相关素材（随手摘录，自由化用，不要照搬）】\n"
    for r in collected[:12]:
        rag_context += f"- {r['text'][:180]}\n"
    return rag_context


@router.post("/worldview/narrative")
async def narrative(req: NarrativeRequest):
    """Interactive narrative engine with implicit worldview."""
    system_prompt = NARRATIVE_SYSTEM_TEMPLATE

    # RAG三路饱和检索注入
    rag_context = _gather_rag_context(req)
    if rag_context:
        system_prompt += rag_context

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
