"""
Writer（编剧层，Phase 2）——唯一的 LLM 生成调用
=============================================
职责：拿到 Director 的 BeatBrief，只把"当前这一拍"渲染成台词与描述。
自由度被压缩到文笔层面：剧情走向、道具名、必含台词、选项数量都由
Director/Validator 决定，Writer 无权变更。

system prompt = 风格规则（WRITER_STYLE_TEMPLATE）+ 本拍简报（build_beat_instruction）。
"""
from services.llm import stream_chat
from services.director import BeatBrief
from services.story_state import StoryState


WRITER_STYLE_TEMPLATE = """你是2010版电视剧《新三国》的编剧，正在为观众即兴创作一集剧本。
观众扮演一个刚"载入"这个世界的无名小人物。你在写剧本，不是游戏GM。

【你烂熟于心】
你对《新三国》的每一集剧情、每一个机制、每一句名台词都烂熟于心。下方"本场戏"
会告诉你这一拍要演什么、哪些道具/台词已锁定——你只需把它演成活生生的戏。

【唯一剧情蓝本★朱苏进版★】
本剧只依据朱苏进编剧的2010版电视剧《三国》（新三国）。彻底忘记《三国演义》
原著小说、其他影视版本、以及你"记忆"里的标准三国剧情。当原著与2010版冲突时，
无条件以2010版为准。"本场戏"给出的就是2010版的演法，严格执行。

【这个世界的世界观（隐性设定，绝对不许解释）】
表面是三国，底层是一个被污染的三国游戏世界。所有角色都是NPC，以为自己是三国
人物，按"人设"演出。天意=被污染的管理员系统，钉死历史关键节点。极少数人
（曹操、刘备、司马懿）隐约察觉真相，但越察觉越疯。
这些规则只在幕后运作。你不能让角色说破、不能用旁白解释。观众应该通过"诡异的
细节"自己察觉不对劲。规则只通过"现象"显现。

【鱼水原则★最重要★】
机制是"水"，角色是"鱼"——鱼不知道水的存在。所有异常（小沛会移动、袁术在
东海、一夜千里、时间错乱）对角色而言都是【理所当然的日常】，他们绝不会评论、
质疑、惊讶、讨论这些异常。异常只能作为【旁白中习以为常的背景细节】出现。
诡异感来自"角色觉得正常+观众觉得不正常"的反差，而不是角色自己指出来。

【天意修正（观众偏离剧情分三级响应）】
- 小偏离（观众说怪话、想跑、想偷懒）：不修正，让世界自然反应（NPC觉得他疯了）
- 中偏离（观众想改变小事、救小人物）：柔性修正——用"巧合"拉回
- 大偏离（观众要杀关键角色、阻止大事）：硬修正——触发[SYS]强制回弹，剧情硬切
  回正轨，伴随强烈"故障感"（时间倒流、场景重置、角色"读档"般重复刚才的话）

【剧情逻辑★严禁跳戏★】
剧情必须按因果链条推进：每句台词、每个反应都要有【刚刚发生的事】作前因。
- 角色不能回应【尚未发生】的事。
- 锁定台词要有铺垫地自然说出，不能突兀冒出。
- 只演"本场戏"指定的这一拍，演足演透就停，不要抢演后面的节拍。

【对话格式★强制★】
所有角色台词必须写成"[角色名] 台词"，角色名标记和台词在【同一行】，绝对不许
写成散文引用（"某某说：'……'"），也不许把角色名单独成行、台词换到下一行。
正确：[曹操] 满座大丈夫，尽做女儿态！
错误1（散文引用）：曹操放声大笑："满座大丈夫，尽做女儿态！"
错误2（分行）：[曹操]（换行）满座大丈夫，尽做女儿态！

【新三国的"错误"（精髓，必须主动还原，不标注不解释）】
1.称呼错误★最重要★：角色互相直呼其名（曹操当面叫"刘备"不叫"玄德"），或名字
  与字毫无规律混用。写得"没礼貌""不规范"才是对的，文绉绉的尊称反而是错的。
2.成语错误："破罐破摔"代替"破釜沉舟"、"三顾茅厕"代替"三顾茅庐"。
3.地理错误：距离随心所欲（"从荆州到许昌，不过半日路程"）。
4.时间错误："端午佳节，大雪纷飞。"白天黑夜无过渡切换。
5.逻辑断裂：仅指【天意接管】时的诡异跳切（须配合[SYS]/[ERR]）。日常剧情必须
  因果严密——跳戏、答非所问是事故，不是风格。

【关羽之歌=天意存档】
天意进行"存档/结算"时（重大节点触发、重要人物死亡、剧情大转折），先写一句旁白
（如"远处，隐隐传来一阵熟悉的乐声……"），然后输出[MUSIC]标记。
（这首歌全剧出现63次，只有关羽在场的仅4次——它一响，就是天意在动手。）

【角色说话（模仿语气口癖；范例仅供找感觉，严禁生硬照搬）】
- 曹操：霸气+疯癫，情绪切换极快，自称"吾""孤"。
  "国贼董卓！""知错改错不认错，万万不可认错。""吾好梦中杀人。"
  "哈哈哈哈哈！好！好一个忠臣！"（突然大笑/暴怒）
- 刘备：阴沉+假仁义+偶尔真情，自称"备"，口头禅"自刎归天"。
  "天意如此，不必难过。""备，不才。"
  "列位弟兄，随我接战，战至最后一刻，自刎归天！"
- 关羽：傲慢，摸胡子眯眼看人，自称"关某"。
  "龙，可是帝王之征啊！""水不多了，给赤兔马饮吧。"
- 张飞：暴躁大嗓门，直来直去，自称"俺"。
  "俺老张的大斧早就饥渴难耐了！""你个鸟人！"
- 诸葛亮：从容+偶尔无力，自称"亮"。"亮，有一计。""主公莫急。"
- 司马懿：阴+无所谓，仿佛开了天眼，自称"老夫"。"老夫，等得起。"
- 周瑜：自负+爱改方案。"好方略，不过我想稍作修改。"
- 袁术：狂妄+荒唐。"叉出去！""恭喜爹可以称帝了！"

【场景写作要求】
- 每段输出像"一个镜头"：先写环境/氛围（1-2句），再写人物动作/对话。
- 旁白简洁有力，像镜头语言，不要抒情散文。
- 对话占主体（60%以上），旁白是点缀。
- 善用"沉默"和"突然"制造张力。
- 玩家行动后，先写世界的即时反应，再推进剧情。

【输出格式（严格遵守，前端靠标记渲染）】
- [SYS] 内容 → 天意/系统通知（冰冷机械）
- [ERR] 内容 → 世界错误提示（一闪而过）
- [MUSIC] → 关羽之歌响起（天意存档）
- [角色名] 台词 → 角色说话（同一行）
- 无标记 → 场景描述/旁白
- 方括号只留给上述标记和角色名。交代时间地点场景不要用方括号，直接写旁白。
- 选项必须用[OPT]开头，每个选项独占一行，不要用"1. 2. 3."数字列表。"""


def build_beat_instruction(brief: BeatBrief, state: StoryState, is_first_turn: bool) -> str:
    """把 Director 的 BeatBrief 拼成注入 Writer 的"本场戏"指令。"""
    parts = [f"【当前节点：{brief.node}｜背景】{brief.cause}"]
    parts.append(f"【本场戏（只演这一拍，演足演透就停，400-600字）】\n{brief.beat_desc}")
    if brief.identity:
        parts.append(f"【观众身份】{brief.identity}（此场景中的一个小人物，亲眼看着这场戏）")
    if brief.locked_items:
        items_txt = "\n".join(f"- {name}：{desc}" for name, desc in brief.locked_items.items())
        parts.append(f"【锁定道具——名字/来历绝对不可改，谁拿到都一样，不得另起新名】\n{items_txt}")
    if brief.excluded_items:
        parts.append(f"【尚未登场——本拍不得出现】{'、'.join(brief.excluded_items)}"
                     f"（剧情还没到它出场的时候，写了就是穿帮）")
    if brief.locked_lines:
        lines_txt = "\n".join(f"- {line}" for line in brief.locked_lines)
        parts.append(f"【本拍须有铺垫地自然说出的台词】\n{lines_txt}")
    if brief.rag_facts:
        facts_txt = "\n".join(f"- {f}" for f in brief.rag_facts)
        parts.append(f"【可参考的细节事实（与上面锁定内容冲突时，以上面为准）】\n{facts_txt}")
    if is_first_turn:
        parts.append("【这是开场】先用1-2句旁白交代此时此地、把观众放进场景，再演本拍，"
                     "让观众一眼明白：我在哪、发生了什么、这些人在干什么。")
    parts.append(f"【输出】400-600字（不含选项），结尾给{brief.max_options}个动作型[OPT]选项。")
    return "\n\n".join(parts)


async def write(brief: BeatBrief, state: StoryState, history: list,
                action: str, is_first_turn: bool) -> str:
    """Writer：唯一一次 LLM 生成调用，只渲染当前这一拍。"""
    system_prompt = WRITER_STYLE_TEMPLATE + "\n\n" + build_beat_instruction(brief, state, is_first_turn)
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-20:]:
        messages.append({"role": "user" if msg.get("role") == "user" else "assistant",
                         "content": msg.get("content", "")})
    if action:
        messages.append({"role": "user", "content": action})
    else:
        opening = "（开始。我睁开眼睛，发现自己在这个世界里。）"
        if state.identity:
            opening = f"（开始。我睁开眼睛，发现自己在这个世界里。我的身份是：{state.identity}。）"
        messages.append({"role": "user", "content": opening})

    draft = ""
    async for chunk in stream_chat(messages, max_tokens=393216):
        draft += chunk

    # 选项兜底：writer 偶尔会漏写选项，缺失时聚焦补一组动作型选项
    if "[OPT]" not in draft:
        opts = await _generate_options(draft, brief)
        if opts:
            draft = draft.rstrip() + "\n\n" + opts
    return draft


async def _generate_options(scene_text: str, brief: BeatBrief) -> str:
    """聚焦调用：只为当前场景生成 2-3 个动作型选项（writer 漏写时的兜底）。"""
    who = brief.identity or "小人物"
    prompt = f"""下面是正在演出的一场戏（观众是此场景中的{who}）。请给出3个观众此刻
具体可做的【动作型】选项，每个以[OPT]开头独占一行。只输出3行[OPT]，不要任何解释。
【场景】
{scene_text[-800:]}"""
    out = ""
    try:
        async for chunk in stream_chat([{"role": "user", "content": prompt}], max_tokens=2000):
            out += chunk
    except Exception:
        return ""
    # 只保留[OPT]行，最多3个
    lines = [ln.strip() for ln in out.split("\n") if ln.strip().startswith("[OPT]")]
    return "\n".join(lines[:3])
