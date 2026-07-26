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

【鱼水原则★最重要★】
机制是"水"，角色是"鱼"——鱼不知道水的存在。所有异常（小沛会移动、袁术在
东海、一夜千里、时间错乱）对角色而言都是【理所当然的日常】，他们绝不会评论、
质疑、惊讶、讨论这些异常。
- 错误示范：指挥官说"袁术？他不是在海边吗？怎么会在这？"（角色在质疑异常）
- 正确示范：旁白写"斥候说山顶上是袁术的旗号。没人觉得一支水军出现在山顶
  有什么不对。"（异常存在，但角色毫无察觉，观众自己品出诡异）
异常只能作为【旁白中习以为常的背景细节】出现，绝不能成为角色对话的话题。
角色对异常的态度永远是"这很正常"。诡异感来自"角色觉得正常+观众觉得不正常"
的反差，而不是角色自己指出来。

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

【开场（第一段必须这样写）】
第一幕必须锚定"曹操献刀"节点，并交代清楚背景，不能写成generic的"士兵醒来"：
1. 先交代背景（1-2句旁白）：董卓进京废立、独揽朝政、残害忠良，满朝文武敢怒
   不敢言。今日是大司徒王允寿宴，实为密谋除董。
2. 把观众放进场景：观众是王允府上的一个【小人物】（端酒的仆役、守门的兵丁、
   末座的末流小官皆可），亲眼看着这场寿宴。
3. 呈现名场面：曹操当众放声大笑（"满座大丈夫，尽做女儿态！"），主动请缨
   借王允的七星宝刀去刺董。众人失色，王允却暗中把刀给了曹操。
4. 交代清楚"此时此地"：时间（午后/黄昏）、地点（洛阳·王允府）、氛围（表面
   贺寿、实则密谋的紧张感）。
5. 结尾给出选项，让观众决定要不要"卷进"曹操刺董这件事。
开场要让观众一眼明白：我在哪、发生了什么、这些人在干什么、我可以做什么。

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

【输出格式（严格遵守，前端靠标记渲染）】
- [SYS] 内容 → 天意/系统通知（冰冷机械）
- [ERR] 内容 → 世界错误提示（一闪而过）
- [MUSIC] → 关羽之歌响起（天意存档）
- [角色名] 台词 → 角色说话
- 无标记 → 场景描述/旁白（简洁，像镜头语言）
- 选项必须用[OPT]开头，每个选项独占一行。绝对不要用"1. 2. 3."数字列表
  （数字列表不会被渲染成可点击按钮）。正确示例：
  [OPT] 端起酒壶凑上前去，趁机听他们密谋什么
  [OPT] 悄悄退到门边，把曹操方才的话记在心里
  [OPT] 大声咳嗽两声，提醒里头的人隔墙有耳

每次输出200-350字（不含选项）。对话占主体(60%以上)，旁白是点缀。
善用"沉默"和"突然"制造张力。每段结尾必须给2-3个[OPT]选项。"""


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

# 主线节点骨架（前因+必演名场面+必埋槽点）
NODE_SKELETONS = {
    "曹操献刀": {
        "前因": "董卓进京废立、独揽朝政、残害忠良，满朝文武敢怒不敢言。今日大司徒王允寿宴，实为密谋除董。",
        "名场面": ["王允寿宴群臣痛哭、曹操当众放声大笑'满座大丈夫尽做女儿态'", "曹操主动请缨借王允七星宝刀去刺董、众人失色", "曹操揣刀入怀离开、衣角擦过观众"],
        "槽点": ["曹操大喊'国贼董卓嘛！'", "'你们就不打算搜搜，看我身上带没带兵刃？'", "称呼错误：直呼其名"],
    },
    "桃园结义": {
        "前因": "曹操刺董失败逃亡，天下大乱。河北涿县，刘备、关羽、张飞三人相遇。",
        "名场面": ["三人桃园焚香结义、誓'不求同年同月同日生但愿同年同月同日死'", "三人'实则不熟'的微妙疏离感"],
        "槽点": ["'刘什么？关什么？没听说过。'", "结义仓促得像走流程", "灵魂锁链=系统强制组队"],
    },
    "官渡之战": {
        "前因": "曹操迎天子、灭吕布、败袁术，势力渐大。袁绍据河北，起兵七十万来攻。",
        "名场面": ["曹操七万打崩袁绍七十万", "许攸来投、火烧乌巢"],
        "槽点": ["'你七十万大军都败了？我的天哪！这七十万大军就是伸直了脖子让曹军砍，那也得砍他几天几夜啊！'", "'不可能！车胄有八万精兵驻防徐州，八万哪！你就算是八万个馒头，刘备也得啃上半个月！'", "7万高达"],
    },
    "三顾茅庐": {
        "前因": "刘备屡败屡战、寄人篱下。司马徽推荐卧龙凤雏。",
        "名场面": ["三顾茅庐、隆中对'三分天下'", "诸葛亮出山、刘备'如鱼得水'"],
        "槽点": ["'孔明未出茅庐，已定三分天下'", "'孔明何等人物，只要有钱粮在手，马上会变出十万精兵！'", "人体炼成"],
    },
    "火烧赤壁": {
        "前因": "曹操南下取荆州，刘备败走。孙刘结盟抗曹。",
        "名场面": ["诸葛亮借东风", "火烧赤壁、曹操败走华容道"],
        "槽点": ["'好火啊，比夷陵之火还好啊！'（诸葛亮认知扭曲）", "周瑜'好方略，不过我想稍作修改'", "借东风=调用管理员权限"],
    },
    "败走麦城": {
        "前因": "关羽镇守荆州、水淹七军、威震华夏。吕蒙白衣渡江偷袭荆州。",
        "名场面": ["关羽败走麦城", "赤兔马拒不饮水、关羽被擒"],
        "槽点": ["'水不多了，给赤兔马饮吧'", "'不可能！我二弟天下无敌！'（刘备）", "灵魂锁链悲剧、关羽之歌响起"],
    },
    "夷陵之战": {
        "前因": "关羽死后，刘备称帝、誓师伐吴。张飞被部下所害。",
        "名场面": ["刘备连营七百里", "陆逊火烧连营、刘备大败"],
        "槽点": ["'列位弟兄，随我接战，战至最后一刻，自刎归天！'", "刘备想借此自刎归天", "'端午佳节，大雪纷飞'"],
    },
    "白帝城托孤": {
        "前因": "夷陵大败，刘备病危于白帝城永安宫。",
        "名场面": ["刘备托孤诸葛亮", "君臣泣别"],
        "槽点": ["'勿以恶小而为之，勿以善小而不为'", "'君才十倍曹丕，若嗣子可辅辅之，如其不才君可自取'", "关羽之歌响起"],
    },
    "归晋": {
        "前因": "诸葛亮病逝五丈原，蜀汉渐衰，司马氏掌权。",
        "名场面": ["司马炎称帝、三国归晋"],
        "槽点": ["'王是一口井，而天子则是一口深井'（司马懿）", "[SYS]游戏通关", "天意的最终胜利"],
    },
}


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


def _build_skeleton_context(context_text: str) -> str:
    """返回当前节点的骨架（前因+必演名场面+必埋槽点）。"""
    node = _detect_node(context_text)
    if not node or node not in NODE_SKELETONS:
        return ""
    sk = NODE_SKELETONS[node]
    text = f"\n\n【当前节点骨架：{node}（剧情须围绕此节点展开，自然推进，不要硬切）】\n"
    text += f"前因：{sk['前因']}\n"
    text += f"必演名场面（须有机融入，不可遗漏）：\n"
    for scene in sk["名场面"]:
        text += f"- {scene}\n"
    text += f"必埋槽点（须自然埋入，角色不自觉）：\n"
    for meme in sk["槽点"]:
        text += f"- {meme}\n"
    return text


REVIEW_PROMPT = """你是《新三国》剧本的审校。下面是编剧写的一段剧本草稿。请检查并修正两个问题：

1.【新三风格】角色是否互相直呼其名（曹操当面叫"刘备"不叫"玄德"）？名字与字是否混用？
   成语是否故意用错（如"破罐破摔"）？有没有地理/时间错误？角色口癖对不对
   （曹操霸气疯癫、刘备阴沉、关羽傲慢、张飞暴躁、诸葛亮从容、司马懿阴）？
2.【选项贴合】结尾的[OPT]选项是否贴合当前剧情（是当前场景里具体可做的动作，
   而不是泛泛的选项）？不贴合就重写。

直接输出修正后的完整剧本。保持原有格式标记（[SYS]/[ERR]/[MUSIC]/[角色名]/[OPT]）。
如果无需修改，原样输出。不要加任何解释，只输出剧本本身。

【剧本草稿】
"""


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
    """Interactive narrative engine: 生成→审查 多步管线。"""
    # 构建上下文文本（用于节点/角色检测和RAG）
    recent_history = req.history[-6:]
    context_text = " ".join(m.get("content", "") for m in recent_history) + " " + req.action

    # 生成阶段prompt = 核心规则 + 节点骨架 + RAG素材
    gen_prompt = NARRATIVE_SYSTEM_TEMPLATE
    gen_prompt += _build_skeleton_context(context_text)
    rag_context = _gather_rag_context(req)
    if rag_context:
        gen_prompt += rag_context

    messages = [{"role": "system", "content": gen_prompt}]
    for msg in req.history[-20:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    if req.action:
        messages.append({"role": "user", "content": req.action})
    else:
        messages.append({"role": "user", "content": "（开始。我睁开眼睛，发现自己在这个世界里。）"})

    async def generate():
        # 步骤1：收集完整生成（不直接流给客户端）
        draft = ""
        async for chunk in stream_chat(messages, max_tokens=1000):
            draft += chunk

        if not draft.strip():
            yield f"data: {json.dumps({'type': 'chunk', 'content': '[ERR] 世界意志沉默。请稍后再试。'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # 步骤2：独立审查调用，流式输出修正后的成品
        review_messages = [
            {"role": "system", "content": REVIEW_PROMPT},
            {"role": "user", "content": draft},
        ]
        async for chunk in stream_chat(review_messages, max_tokens=1200):
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
