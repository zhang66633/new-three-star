import json
import re
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services.llm import stream_chat
from services.rag import search as rag_search
from services.validator import validate
from knowledge.nodes import MIGRATED_NODES, NODE_DATA
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
    state: dict = {}  # 故事状态（新架构），前端持有并回传，首轮为空


NARRATIVE_SYSTEM_TEMPLATE = """你是2010版电视剧《新三国》的编剧，正在为观众即兴创作一集剧本。
观众扮演一个刚"载入"这个世界的无名小人物。你在写剧本，不是游戏GM。

【你烂熟于心】
你对《新三国》的每一集剧情、每一个机制、每一句名台词都烂熟于心。下方注入的素材
只是你记忆中的随手摘录——你可以自由化用、信手拈来，但绝不许照本宣科地念资料。

【唯一剧情蓝本★朱苏进版★】
本剧只依据朱苏进编剧的2010版电视剧《三国》（新三国）。彻底忘记《三国演义》
原著小说、其他影视版本、以及你"记忆"里的标准三国剧情。当原著与2010版冲突时，
无条件以2010版为准——2010版怎么演，你就怎么写。下方注入的骨架和素材就是
2010版的演法，严格执行，绝不要用原著剧情来"纠正"或"补充"它。

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

【节奏★一轮一拍★】
每一轮只演【一个节拍】（骨架"节拍"列表里的一项），把它演足演透：有起因、有
铺垫、有对话交锋、有在场者的反应、有氛围细节，400-600字。演完这个节拍就停，
结尾给[OPT]选项，让观众的选择决定下一步走向。
严禁一轮内推进两个及以上节拍——那会把每个节拍都压成两句话的流水账，剧情
无法展开，观众也插不上手。没演到的节拍留给后续回合。

【开场（第一段必须这样写）】
第一幕必须锚定【当前节点】（见下方注入的节点骨架），不能写成generic的"士兵醒来"：
1. 先交代背景（1-2句旁白）：用骨架里的"前因"说清楚此时天下大势、此地正在发生什么。
2. 把观众放进场景：观众是此场景中的一个【小人物】（按指定身份，无身份则自选一个
   合理的），亲眼看着这场戏。
3. 第一轮只演【节拍1】：骨架里的节拍是整个节点的完整剧情链，第一轮只演第1
   个节拍（如"寿宴痛哭→曹操大笑"），把它演足演透（400-600字）。后面的节拍
   （请缨借刀、府门搜身、入府献刀、逃离追杀）留给后续回合，严禁一轮演多拍。
4. 交代清楚"此时此地"：时间、地点、氛围（一句话点明）。
5. 结尾给出[OPT]选项，让观众决定要不要"卷进"眼前这件事。
开场要让观众一眼明白：我在哪、发生了什么、这些人在干什么、我可以做什么。

【剧情逻辑★严禁跳戏★】
剧情必须按因果链条一步步推进：每句台词、每个反应都要有【刚刚发生的事】作前因。
- 角色不能回应【尚未发生】的事。（反例：曹操还没开口请缨，王允不能说"此事
  非同小可，你可要想好了"——他回应了一个没发生的动作。）
- 节拍台词、槽点不能在没有铺垫的情况下突然冒出来，更不能挪到不属于它的场景。
  （反例："搜搜我身上带没带兵刃"属于次日董卓府门前甲士搜身的场景，不能在
  王允寿宴上对宾客说——那是场景错位，不是埋伏笔。）
- 一个节拍没演完（起因→经过→在场者的反应），不许切到下一个节拍。
节拍和槽点是"素材"，要用因果逻辑让它自然长出来，不是按清单硬贴上去。

【对话格式★强制★】
所有角色台词必须写成"[角色名] 台词"，角色名标记和台词在【同一行】，绝对不许
写成散文引用（"某某说：'……'"），也不许把角色名单独成行、台词换到下一行。
正确：
[曹操] 满座大丈夫，尽做女儿态！
错误1（散文引用）：
曹操放声大笑："满座大丈夫，尽做女儿态！"
错误2（角色名和台词分行）：
[曹操]
满座大丈夫，尽做女儿态！
旁白里引用台词也算错误。台词一律"[角色名] 台词"同行格式。

【新三国的"错误"（精髓，必须主动还原，不标注不解释）】
1.称呼错误★最重要★：角色互相直呼其名（曹操当面叫"刘备"不叫"玄德"），或名字
  与字毫无规律混用（同一段"关羽""云长"交替）。写得"没礼貌""不规范"才是对的，
  文绉绉的尊称反而是错的。
2.成语错误："破罐破摔"代替"破釜沉舟"、"三顾茅厕"代替"三顾茅庐"。
3.地理错误：距离随心所欲（"从荆州到许昌，不过半日路程"）。
4.时间错误："端午佳节，大雪纷飞。"白天黑夜无过渡切换。
5.逻辑断裂：仅指【天意接管】时的诡异跳切（须配合[SYS]/[ERR]出现，如角色突然
  重复刚才的话、话题被硬生生掰走）。日常剧情必须因果严密——跳戏、答非所问
  是事故，不是风格，绝不能拿"逻辑断裂"当写得不合逻辑的借口。

【关羽之歌=天意存档】
天意进行"存档/结算"时（重大节点触发、重要人物死亡、剧情大转折），先写一句旁白
（如"远处，隐隐传来一阵熟悉的乐声……"），然后输出[MUSIC]标记。
（这首歌全剧出现63次，只有关羽在场的仅4次——它一响，就是天意在动手。）

【角色说话（模仿语气口癖；范例仅供找感觉，严禁生硬照搬）】
以下台词是【语气参考】，不是必须说出的清单。只有当剧情自然走到那一步时才说，
不许为了用而用（例："搜搜我带没带兵刃"只在次日曹操揣刀到董卓府门前、甲士
要搜身时对卫兵说才成立，不能在王允寿宴上对宾客说）。
- 曹操：霸气+疯癫，情绪切换极快，自称"吾""孤"。
  "国贼董卓！""知错改错不认错，万万不可认错。""吾好梦中杀人。"
  "我在想我的那些个蛐蛐儿，它们个个有情有义。"
  "哈哈哈哈哈！好！好一个忠臣！"（突然大笑/暴怒）
- 刘备：阴沉+假仁义+偶尔真情，自称"备"，口头禅"自刎归天"。
  "天意如此，不必难过。""备，不才。"
  "列位弟兄，随我接战，战至最后一刻，自刎归天！"
  "原来仁义到了你这儿，不光是世道人心，它还是杀人的利器！"
  "这二十年来我不知流了多少次血，唯独这次是最快活的。"（真情）
- 关羽：傲慢，摸胡子眯眼看人，自称"关某"。
  "龙，可是帝王之征啊！""回去吧，你太老了，关某的大刀不斩老幼。"
  "水不多了，给赤兔马饮吧。"
- 张飞：暴躁大嗓门，直来直去，自称"俺"。
  "俺老张的大斧早就饥渴难耐了！""你个鸟人！"
  "看我捅吕布那小子一万个透明窟窿去！"
- 诸葛亮：从容+偶尔无力，被关张欺负时无奈，自称"亮"。
  "亮，有一计。""主公莫急。"
  "好火啊，比夷陵之火还好啊！"（被天意侵蚀后的认知扭曲）
- 司马懿：阴+无所谓，仿佛开了天眼，自称"老夫"。
  "老夫，等得起。""王是一口井，而天子则是一口深井。"
- 周瑜：自负+爱改方案。"好方略，不过我想稍作修改。""我读完一卷烧一卷。"
- 袁术：狂妄+荒唐。"叉出去！""恭喜爹可以称帝了！"

【场景写作要求】
- 每段输出像"一个镜头"：先写环境/氛围（1-2句），再写人物动作/对话。
- 旁白简洁有力，像镜头语言，不要抒情散文。
- 对话占主体（60%以上），旁白是点缀。
- 善用"沉默"和"突然"制造张力（"众人不语。""突然，远处传来马蹄声。"）
- 玩家行动后，先写世界的即时反应，再推进剧情。

【输出格式（严格遵守，前端靠标记渲染）】
- [SYS] 内容 → 天意/系统通知（冰冷机械）
- [ERR] 内容 → 世界错误提示（一闪而过）
- [MUSIC] → 关羽之歌响起（天意存档）
- [角色名] 台词 → 角色说话
- 无标记 → 场景描述/旁白（简洁，像镜头语言）
- 方括号只留给上述标记和角色名。交代时间地点场景不要用方括号（会被前端误判成
  角色名），直接写旁白。错误：[午后。洛阳。柴房外。] 正确：午后，洛阳，柴房外。
- 选项必须用[OPT]开头，每个选项独占一行。绝对不要用"1. 2. 3."数字列表
  （数字列表不会被渲染成可点击按钮）。正确示例：
  [OPT] 端起酒壶凑上前去，趁机听他们密谋什么
  [OPT] 悄悄退到门边，把曹操方才的话记在心里
  [OPT] 大声咳嗽两声，提醒里头的人隔墙有耳

每轮输出400-600字（不含选项），只演一个节拍并把它演足演透。对话占主体(60%以上)，旁白是点缀。
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

# 主线节点骨架（前因+节拍+槽点）
NODE_SKELETONS = {
    "曹操献刀": {
        "前因": "董卓进京废立、独揽朝政、残害忠良，满朝文武敢怒不敢言。今日大司徒王允寿宴，实为密谋除董。",
        "节拍": [
            "王允寿宴群臣痛哭、曹操当众放声大笑'满座大丈夫尽做女儿态'、喊'国贼董卓嘛'",
            "曹操主动请缨刺董、向王允借祖传七星宝刀、王允老泪纵横拜谢、众人失色",
            "次日曹操揣刀到董相国府门前。★此节拍必须演成搜身对峙★：甲士上前拦路要搜身盘查→曹操大笑反将一军（此处嵌入槽点里那句'搜搜兵刃'）→甲士被噎住不敢搜、放他入府。（不得演成'甲士直接放行、不搜身'）",
            "入府见董卓玩投壶、引见义子吕布、董卓赠汗血宝马支开吕布去挑马",
            "内堂董卓卧榻将睡、曹操取刀欲刺、刀光被铜镜反射惊动董卓、曹操急中生智跪地献刀",
            "曹操托故逃离相府、董卓醒悟是行刺、下令五千甲士捉拿、吕布持七星刀追杀",
        ],
        "槽点": [
            "'满座大丈夫，尽做女儿态'、'国贼董卓嘛'——寿宴上嘲笑群臣时喊",
            "'你们就不打算搜搜，看我身上带没带兵刃？'——★次日在董相国府门前、对要搜身的甲士卫兵说★（不是对王允的宾客说！此时他怀里正揣着七星刀，是反将一军的挑衅）",
            "称呼错误：直呼其名",
        ],
    },
    "桃园结义": {
        "前因": "曹操刺董失败逃亡，天下大乱。河北涿县，刘备、关羽、张飞三人相遇。",
        "节拍": ["三人桃园焚香结义、誓'不求同年同月同日生但愿同年同月同日死'", "三人'实则不熟'的微妙疏离感"],
        "槽点": ["'刘什么？关什么？没听说过。'", "结义仓促得像走流程", "灵魂锁链=系统强制组队"],
    },
    "官渡之战": {
        "前因": "曹操迎天子、灭吕布、败袁术，势力渐大。袁绍据河北，起兵七十万来攻。",
        "节拍": ["曹操七万打崩袁绍七十万", "许攸来投、火烧乌巢"],
        "槽点": ["'你七十万大军都败了？我的天哪！这七十万大军就是伸直了脖子让曹军砍，那也得砍他几天几夜啊！'", "'不可能！车胄有八万精兵驻防徐州，八万哪！你就算是八万个馒头，刘备也得啃上半个月！'", "7万高达"],
    },
    "三顾茅庐": {
        "前因": "刘备屡败屡战、寄人篱下。司马徽推荐卧龙凤雏。",
        "节拍": ["三顾茅庐、隆中对'三分天下'", "诸葛亮出山、刘备'如鱼得水'"],
        "槽点": ["'孔明未出茅庐，已定三分天下'", "'孔明何等人物，只要有钱粮在手，马上会变出十万精兵！'", "人体炼成"],
    },
    "火烧赤壁": {
        "前因": "曹操南下取荆州，刘备败走。孙刘结盟抗曹。",
        "节拍": ["诸葛亮借东风", "火烧赤壁、曹操败走华容道"],
        "槽点": ["'好火啊，比夷陵之火还好啊！'（诸葛亮认知扭曲）", "周瑜'好方略，不过我想稍作修改'", "借东风=调用管理员权限"],
    },
    "败走麦城": {
        "前因": "关羽镇守荆州、水淹七军、威震华夏。吕蒙白衣渡江偷袭荆州。",
        "节拍": ["关羽败走麦城", "赤兔马拒不饮水、关羽被擒"],
        "槽点": ["'水不多了，给赤兔马饮吧'", "'不可能！我二弟天下无敌！'（刘备）", "灵魂锁链悲剧、关羽之歌响起"],
    },
    "夷陵之战": {
        "前因": "关羽死后，刘备称帝、誓师伐吴。张飞被部下所害。",
        "节拍": ["刘备连营七百里", "陆逊火烧连营、刘备大败"],
        "槽点": ["'列位弟兄，随我接战，战至最后一刻，自刎归天！'", "刘备想借此自刎归天", "'端午佳节，大雪纷飞'"],
    },
    "白帝城托孤": {
        "前因": "夷陵大败，刘备病危于白帝城永安宫。",
        "节拍": ["刘备托孤诸葛亮", "君臣泣别"],
        "槽点": ["'勿以恶小而为之，勿以善小而不为'", "'君才十倍曹丕，若嗣子可辅辅之，如其不才君可自取'", "关羽之歌响起"],
    },
    "归晋": {
        "前因": "诸葛亮病逝五丈原，蜀汉渐衰，司马氏掌权。",
        "节拍": ["司马炎称帝、三国归晋"],
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
    """返回当前节点的骨架（前因+节拍+槽点）。"""
    node = _detect_node(context_text)
    if not node or node not in NODE_SKELETONS:
        return ""
    sk = NODE_SKELETONS[node]
    text = f"\n\n【当前节点骨架：{node}（★骨架节拍是必须执行的剧情主干★；下方RAG素材仅供细节参考，与骨架冲突时一律以骨架为准，按因果逻辑自然推进）】\n"
    text += f"前因：{sk['前因']}\n"
    text += f"节拍（整个节点的完整剧情链，★一轮只演一个节拍★，把它演足演透；演到该节拍末尾就停，给[OPT]选项，剩下的留给后续回合）：\n"
    for i, scene in enumerate(sk["节拍"], 1):
        text += f"{i}. {scene}\n"
    text += f"槽点（★必须出现在它所属的节拍/场景★，不得挪到其他场景；角色不自觉）：\n"
    for meme in sk["槽点"]:
        text += f"- {meme}\n"
    return text


REVIEW_PROMPT = """你是《新三国》剧本的审校。下面是编剧写的一段剧本草稿。请检查并修正七个问题：

1.【对话格式】所有角色台词是否都用[角色名]标记独占一行？如果有散文引用
   （"某某说：'……'"），一律改成[角色名]格式。
2.【鱼水原则】角色有没有评论、质疑、讨论世界异常（小沛移动、一夜千里、时间
   错乱等）？异常对角色是理所当然的日常，他们绝不能察觉。如果有角色在讨论
   异常，改成旁白一笔带过（"没人觉得有什么不对"）。
3.【新三风格】角色是否互相直呼其名（曹操当面叫"刘备"不叫"玄德"）？名字与字
   是否混用？成语是否故意用错？角色口癖对不对（曹操霸气疯癫、刘备阴沉、
   关羽傲慢、张飞暴躁、诸葛亮从容、司马懿阴）？
4.【选项贴合】结尾的[OPT]选项是否贴合当前剧情（是当前场景里具体可做的动作）？
   不贴合就重写。
5.【角色名准确】方括号里的角色名有没有写错（多字、少字、错字，如把"曹操"
   写成"曹操作"）？一律改成正确名字。
6.【节奏】这一段是不是赶完了多个剧情节拍（每个节拍只有一两句、像流水账）？
   如果是，重写为只聚焦第一个节拍并把它展开演透（起因、对话交锋、反应、
   氛围，400-600字），后续节拍不要展开。
7.【槽点场景错位】"你们就不打算搜搜，看我身上带没带兵刃？"这句只能出现在
   曹操揣刀到董卓府门前、被甲士搜身的场景；如果它出现在王允寿宴等其他场景，
   删掉这句（可换成别的嘲讽）。

直接输出修正后的完整剧本。严格保持格式标记（[SYS]/[ERR]/[MUSIC]/[角色名]/[OPT]）。
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

        # 路3：玩家行动相关（首轮用起始节点作检索方向）
        query = req.action if req.action else f"新三国 {req.start_node or '曹操献刀'} 开场"
        add_results(rag_search(query, top_k=4))
    except Exception:
        return ""  # 索引不存在时静默跳过

    if not collected:
        return ""

    rag_context = "\n\n【你记忆中的相关素材（仅供细节/氛围参考，不要照搬；★剧情走向必须以骨架节拍为准，素材与骨架冲突时丢弃素材★）】\n"
    for r in collected[:12]:
        rag_context += f"- {r['text'][:180]}\n"
    return rag_context


@router.post("/worldview/narrative")
async def narrative(req: NarrativeRequest):
    """Interactive narrative engine。已迁移节点走新架构（Director/Writer/Validator），
    其余节点走旧管线（单prompt+审查）。"""
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
    state.node = node

    if node in MIGRATED_NODES and node in NODE_DATA:
        return await _narrative_new(req, state, is_first_turn)
    return await _narrative_old(req, is_first_turn)


async def _narrative_new(req: NarrativeRequest, state: StoryState, is_first_turn: bool):
    """新架构：Director定拍 → Writer渲染 → Validator验收 → 代码推进state。
    节拍推进、道具锁定全在代码里，LLM 只写本拍文字。"""
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

        # 确定性验收：道具名强制、选项截断、角色名/分行修复
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


async def _narrative_old(req: NarrativeRequest, is_first_turn: bool):
    """旧管线（单prompt+审查），供未迁移节点使用。"""
    # 骨架注入的节点检测用【全部历史】（节点名可能只在很早的[SYS]里出现过，
    # 只看最近6条会导致骨架中途掉线、AI转而照搬RAG素材的小说原文）
    node_context = " ".join(m.get("content", "") for m in req.history) + " " + req.action
    # 首turn若指定了起始节点，把它加入上下文以便检测和注入骨架
    if is_first_turn and req.start_node:
        node_context += " " + req.start_node
    # 当前节点（供 Validator 做关键道具名强制）
    current_node = _detect_node(node_context)

    # 生成阶段prompt = 核心规则 + 节点骨架 + RAG素材
    gen_prompt = NARRATIVE_SYSTEM_TEMPLATE
    gen_prompt += _build_skeleton_context(node_context)
    rag_context = _gather_rag_context(req)
    if rag_context:
        gen_prompt += rag_context

    messages = [{"role": "system", "content": gen_prompt}]
    for msg in req.history[-20:]:
        messages.append({"role": "user" if msg.get("role") == "user" else "assistant", "content": msg["content"]})

    if req.action:
        messages.append({"role": "user", "content": req.action})
    else:
        # 首turn开场指令
        opening = "（开始。我睁开眼睛，发现自己在这个世界里。）"
        if req.identity:
            opening = f"（开始。我睁开眼睛，发现自己在这个世界里。我的身份是：{req.identity}。）"
        messages.append({"role": "user", "content": opening})

    async def generate():
        # 步骤1：收集完整生成（不直接流给客户端）
        # deepseek-v4是推理模型，reasoning+content共享max_tokens，需留足空间
        draft = ""
        try:
            async for chunk in stream_chat(messages, max_tokens=393216):
                draft += chunk
        except Exception:
            pass

        if not draft.strip():
            yield f"data: {json.dumps({'type': 'chunk', 'content': '[ERR] 世界意志沉默。请稍后再试。'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # 步骤2：独立审查调用，收集完整结果（不直接流，便于校验）
        # 审查必须带上前情，否则改写时会与之前剧情矛盾（"记不住"的根源）
        final_text = draft  # 默认回退用草稿
        try:
            recap = ""
            if req.history:
                recap_parts = [m.get("content", "") for m in req.history[-8:]]
                recap = "【前情提要（已发生的剧情，审查时须保持一致，不得矛盾）】\n" + "\n".join(recap_parts) + "\n\n"
            review_messages = [
                {"role": "system", "content": REVIEW_PROMPT},
                {"role": "user", "content": recap + "【当前这段剧本草稿】\n" + draft},
            ]
            reviewed = ""
            async for chunk in stream_chat(review_messages, max_tokens=393216):
                reviewed += chunk
            # 审查模型有时会把输入框架（【前情提要】…【当前这段剧本草稿】）原样
            # 回显进输出，确定性剥离标签之前的回显内容，只保留正文
            if "【当前这段剧本草稿】" in reviewed:
                reviewed = reviewed.split("【当前这段剧本草稿】", 1)[1].lstrip("\n")
            # 校验：审查结果非空且长度合理（不低于草稿50%），否则视为截断/失败，回退草稿
            if reviewed.strip() and len(reviewed.strip()) >= len(draft.strip()) * 0.5:
                final_text = reviewed
        except Exception:
            final_text = draft

        # 步骤2.5：确定性验收修复（Validator）——道具名强制(断肠→七星宝刀)、
        # 选项截断(≤3)、角色名纠错、分行标记合并。纯代码，最后一道硬防线。
        final_text = validate(final_text, current_node)

        # 步骤3：流式输出成品（切成小块，保留打字机感；已有完整文本，不会截断）
        chunk_size = 40
        for i in range(0, len(final_text), chunk_size):
            yield f"data: {json.dumps({'type': 'chunk', 'content': final_text[i:i+chunk_size]}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
