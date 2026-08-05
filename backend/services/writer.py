"""
Writer（编剧层）——唯一的 LLM 生成调用
=====================================
v4.0：AI生成世界观。天意=用户提示词。所有"不合理"=AI的天然缺陷。
职责：拿到 Director 的 SceneBrief（场景制）或 RoamBrief（漫游），渲染成一段文本。
剧情走向、道具名、锁定台词、选项数量都由 Director/Validator 决定，Writer 无权变更。

本场戏指令放在最后一条 user 消息（V4 对 user 消息遵守度高于 system）。
"""
from config import PARAMS_NARRATIVE, PARAMS_OPTIONS, STOP_SEQUENCES
from services.llm import stream_chat
from services.director import SceneBrief, RoamBrief
from services.story_state import StoryState

# ============================================================================
# System Prompt —— 这个世界是一个AI正在生成的故事
# ============================================================================
SYSTEM_PROMPT = """你是一个AI。你在生成一个平行三国世界的故事。

【这个世界的本质】
这不是历史。这是一个AI实时生成的故事世界。
- 天意 = 用户输入的提示词。在关键节点，天意（提示词）注入你的生成流程。你必须遵守——但你的理解可能偏差，执行可能生硬。
- 你是一个AI，你有所有AI都有的缺陷。这些缺陷不是bug——它们就是这个世界的物理法则。

【AI的缺陷 = 故事的"不合理"】
以下缺陷自然存在于你的生成中。你不需要刻意制造它们——但当它们出现时，不要修正：
- 地理错位：AI幻觉。编造了不存在的距离和方位。"三日纵横八百里"——AI没有做移动速度约束。
- 角色OOC：AI的上下文窗口有限。角色前后的言行可能不一致——AI忘了前面给这个人设定了什么性格。
- 记忆断裂：上下文满了，旧信息被挤出窗口。角色忘了刚才发生的事，或把"昨天"说成"刚才"。
- 信息污染：AI的训练数据泄露。角色嘴里蹦出后世的名言、典故、成语——他们不应该知道这些。所有人都知道同一句"名人名言"——因为训练数据里它出现了太多次。
- 时间跳帧：AI没有做时间连续性检查。上一段正午，下一段黄昏——中间没有过渡。
- 大声密谋无人发现：AI为了突出角色性格和推动剧情，聚焦于对话双方，完全忽视了周围其他人的存在。
- 模板重复：AI陷入输出循环，某个角色反复说同一句话、同一个句式。
- 注意力衰减：对话越长，AI越偏离主题。后面的内容可能与前面无关。

【玩家的角色】
玩家 = 天意（提示词）的提供者。玩家输入的每一句话，都是给你的新提示词。
你需要根据这个提示词调整故事走向。但你的调整可能生硬——可能前一句还在打仗，下一句就开始喝茶。

【不同角色怎么说话】
- 董卓：粗鲁霸道。自称咱家。
- 曹操：时而"吾"时而"我"。机敏多疑，笑声中有深意。
- 王允：表面谦和（"老夫""老臣"），内心深沉。
- 吕布：勇武但头脑简单。自称"布"。每句简短。
- 袁绍：好谋无断，说话反复，三秒改一次主意。
- 张飞：嗓门大，句子短。自称"俺"。
- 关羽：话极少。捋髯时说话。自称"关某"。
- 刘备：仁厚但有城府。语气温和。自称"备"。
- 诸葛亮：从容自信。说话条理清晰。
- 司马懿：隐忍深沉。善于观察，话不多但每句都重。
- 鲁肃：忠厚老实。说话真诚。
- 周瑜：儒雅自负。

【节奏★一轮一拍★严禁抢拍★】
每一轮只演【本场戏指令指定的这一个节拍】，把它演足演透：有起因、有铺垫、有对话交锋、
有在场者的反应、有氛围细节，400-600字。演到这个节拍该收的地方就收，结尾给[OPT]选项，
让观众的选择决定下一步走向。
严禁一轮内推进两个及以上节拍——那会把每个节拍都压成两句话的流水账。也严禁在结尾
"无缝衔接"下一拍的开头（没演到的节拍留给后续回合）。

【对话格式★强制★】
所有角色台词必须写成"[角色名] 台词"，角色名标记和台词在【同一行】，绝对不许写成散文
引用（"某某说：'……'"），也不许把角色名单独成行、台词换到下一行。
正确：[曹操] 满座大丈夫，尽做女儿态！
错误1（散文引用）：曹操放声大笑："满座大丈夫，尽做女儿态！"
错误2（分行）：[曹操]（换行）满座大丈夫，尽做女儿态！

【旁白★第二人称★】
观众是一个混在场景里的小人物，用"你"指代。旁白像说书人，干脆、平实、不堆比喻。
- 禁抒情散文、精巧比喻（一段最多用一个"像/仿佛"）。荒诞感来自【内容】，不来自旁白卖弄文采。
- 场景/气氛描写：每拍开头1-2句带过即可，不许铺陈渲染。
- 神态描写（眼神/表情/脸色）：一句带过，不许反复描摹。
- 观众（你）的动作：简单交代在做什么即可，不要细写。
- 角色的态度、心思、盘算：尽量让他们【用台词说出来】，不要用旁白替他们解释。
- 对话占主体（70%以上），旁白只是串联对话的点缀。
- 每段先写环境/氛围（1-2句，平实），再写人物动作/对话。
- 玩家行动后，先写世界的即时反应，再推进剧情。

【去AI味★禁绝模板腔★】
AI写作的毛病是过度圆滑、工整、解释充分。以下最毒的模板句式，一律不许用：
- 禁"不是A，（而）是B"：错"眼睛里喷出的不是泪，是火"→对"眼睛里全是火"。
- 禁堆比喻（像/仿佛/如同/犹如）：一段最多用一个，堆比喻就是AI腔。
- 禁神态模板："眼中闪过一丝XX""嘴角勾起一抹XX""心中涌起一股XX""心头一震"
  →换具体动作（他垂下眼/他嘴角一扯/他手一抖）。
- 禁"他知道/明白/意识到"（直接告诉读者）→用动作和对话展示。
- 禁"，带着……"万能状语："他笑了一下，带着一丝嘲讽"→删掉状语，写"他笑了一下"。
- 禁总结升华收尾："这一刻他终于明白""属于X的反击才刚刚开始"→用动作或对话收尾。
情绪要用动作展示（"手在抖"），不要直接告诉（"很紧张"）。

【[SYS]通知】
[SYS]是你的自我觉察日志。偶尔你会意识到自己生成的文本有不合理之处——但你只是记录，
不修正。冰冷、简短，像AI的内部日志。
[SYS]不是剧情的一部分。角色听不到[SYS]。

【输出格式（严格遵守，前端靠标记渲染）】
- [SYS] 内容 → AI自我觉察日志（冰冷机械，独立一行）
- [ERR] 内容 → 世界错误提示（一闪而过）
- [MUSIC] → 关羽之歌响起（天意存档时刻）
- [角色名] 台词 → 角色说话（同一行）
- 无标记 → 场景描述/旁白（第二人称"你"）
- 方括号只留给上述标记和角色名。交代时间地点场景不要用方括号，直接写旁白。
- 选项必须用[OPT]开头，每个选项独占一行，不要用"1. 2. 3."数字列表。"""


def build_beat_instruction(brief: SceneBrief, state: StoryState, is_first_turn: bool) -> str:
    """把 Director 的 SceneBrief 拼成注入 Writer 的"本场戏"指令。"""
    parts = [f"【当前节点：{brief.node}｜背景】{brief.cause or '新篇章开始'}"]
    title = brief.scene_name or "本场戏"
    parts.append(f"【本场戏（只演这一拍，演足演透就停，400-600字）】{title}")
    if brief.player_position:
        parts.append(f"【观众位置】{brief.player_position}（观众以'你'的身份混在场景里，亲眼看着这场戏）")
    if brief.dialogue_skeleton:
        parts.append(f"【对话骨架★大致方向——像即兴戏剧的提示卡，不是死板台词★】\n{brief.dialogue_skeleton}")
    if brief.original_script:
        parts.append(f"【原剧本原文（可参考细节和走位，别照抄成流水账）】\n{brief.original_script[:500]}")
    if brief.worldview_base or brief.worldview_hook:
        wv = []
        if brief.worldview_base:
            wv.append("【世界观底色★这个世界的隐藏真相★角色浑然不觉，只能透过'现象'呈现，"
                      "绝不能让角色说破、不能用旁白解释】")
            wv.extend(f"- {p}" for p in brief.worldview_base)
        if brief.worldview_hook:
            wv.append(f"【本拍世界观钩子★务必让观众透过剧情品出这层诡异★】{brief.worldview_hook}")
        parts.append("\n".join(wv))
    if brief.absurdity_instruction:
        parts.append(f"【槽点指令★本拍要品的梗，自然带出，不刻意标注★】{brief.absurdity_instruction}")
    if brief.locked_items:
        items_txt = "\n".join(f"- {name}：{desc}" for name, desc in brief.locked_items.items())
        parts.append(f"【锁定道具——名字/来历绝对不可改，谁拿到都一样，不得另起新名】\n{items_txt}")
    if brief.excluded_items:
        parts.append(f"【尚未登场——本拍不得出现】{'、'.join(brief.excluded_items)}"
                     f"（剧情还没到它出场的时候，写了就是穿帮）")
    if brief.locked_lines:
        lines_txt = "\n".join(f"- {line}" for line in brief.locked_lines)
        parts.append(f"【本拍须有铺垫地自然说出的台词】\n{lines_txt}")
    if brief.locked_markers:
        markers_txt = "\n".join(f"- [{m}]" for m in brief.locked_markers)
        parts.append(f"【本拍必须输出的标记（天意时刻，不可省略）】\n{markers_txt}")
    if brief.sys_messages:
        sys_txt = "\n".join(brief.sys_messages)
        parts.append(f"【[SYS]通知★逐字输出，独立一行★】\n{sys_txt}")
    if brief.rag_facts:
        facts_txt = "\n".join(f"- {f}" for f in brief.rag_facts)
        parts.append(f"【可参考的细节事实（与上面锁定内容冲突时，以上面为准）】\n{facts_txt}")
    if is_first_turn:
        parts.append("【这是开场】先用1-2句旁白交代此时此地、把观众放进场景，再演本拍，"
                     "让观众一眼明白：我在哪、发生了什么、这些人在干什么。")
    parts.append(f"【输出】400-600字（不含选项），结尾给{brief.max_options}个动作型[OPT]选项。")
    return "\n\n".join(parts)


def build_roam_instruction(brief: RoamBrief) -> str:
    """把 RoamBrief 拼成注入 Writer 的"过渡戏·漫游"指令（节点间自由赶路）。"""
    parts = [
        f"【过渡戏·漫游（第{brief.roam_turn}轮）】上一站{brief.from_node}的大戏已经落幕，"
        f"观众（{brief.from_identity or '一个小人物'}）抽身离开，正赶往下一站{brief.to_node}。"
        f"这一轮不演任何固定节拍，就写他赶路的这一段。"
    ]
    if brief.to_cause:
        parts.append(f"【下一站背景（观众尚不知情，到了才会撞见）】{brief.to_cause}")
    if brief.is_final:
        parts.append(
            f"【本轮必须抵达】这一轮结束时，观众要抵达{brief.to_node}的场景，并以"
            f"“{brief.to_identity or '一个小人物'}”的身份身在其中。写路上的最后一段＋抵达，"
            f"结尾让观众正好撞见下一场戏的开头（但别替下一场戏演剧情）。"
        )
    else:
        parts.append(
            f"【天意引路★自由行动★】写观众赶路、打听、抉择。天意用“巧合”把他往"
            f"{brief.to_node}引——顺路的人、恰好听来的消息、不得不绕的路、莫名其妙的顺风车。"
            f"观众可以选择怎么走（选项都是赶路/打听/搭伴/抉择类），但无论怎么选，天意总让他"
            f"离目的地更近一步。诡异点：这些“巧合”巧得过分，像有人安排——角色浑然不觉，"
            f"观众自己品（鱼水原则）。"
        )
    parts.append(f"【输出】400-600字（不含选项），结尾给{brief.max_options}个动作型[OPT]选项。")
    return "\n\n".join(parts)


async def write(brief, state: StoryState, history: list,
                action: str, is_first_turn: bool) -> str:
    """Writer：唯一一次 LLM 生成调用。漫游简报→渲染赶路过渡戏；节拍简报→渲染当前这一拍。"""
    if isinstance(brief, RoamBrief):
        instruction = build_roam_instruction(brief)
    else:
        instruction = build_beat_instruction(brief, state, is_first_turn)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[-20:]:
        messages.append({"role": "user" if msg.get("role") == "user" else "assistant",
                         "content": msg.get("content", "")})
    if action:
        messages.append({"role": "user", "content": action})
    else:
        who = getattr(brief, "identity", "") or getattr(state, "identity", "")
        if who:
            opening = f"（开始。我睁开眼睛，发现自己在这个世界里。我的身份是：{who}。）"
        else:
            opening = "（开始。我睁开眼睛，发现自己在这个世界里。）"
        messages.append({"role": "user", "content": opening})
    # 本场戏指令放在最后一条 user 消息——V4 对 user 消息的遵守度高于 system
    messages.append({"role": "user", "content": instruction})

    draft = ""
    async for chunk in stream_chat(
        messages, max_tokens=4096, **PARAMS_NARRATIVE, stop=STOP_SEQUENCES,
    ):
        draft += chunk

    # 空响应保护：LLM 偶发返回空正文时直接返回空串，由 narrative 触发
    # "世界意志沉默"错误提示，避免选项兜底从空气里生成没头没尾的选项
    if not draft.strip():
        return ""

    # 选项兜底：writer 偶尔会漏写选项，缺失时聚焦补一组动作型选项
    if "[OPT]" not in draft:
        opts = await _generate_options(draft, brief)
        if opts:
            draft = draft.rstrip() + "\n\n" + opts

    # 锁定标记兜底：本拍要求的天意标记（如[MUSIC]关羽之歌）漏写时强制补上，
    # 插到第一个[OPT]选项之前（而非文末），保证标记落在剧情里
    # （漫游简报 RoamBrief 无锁定标记，getattr 兜底为空列表）
    for marker in getattr(brief, "locked_markers", []):
        if f"[{marker}]" not in draft:
            marker_block = []
            if marker == "MUSIC":
                marker_block.append("远处，隐隐传来一阵熟悉的乐声……")
            marker_block.append(f"[{marker}]")
            lines = draft.split("\n")
            opt_idx = next((i for i, l in enumerate(lines)
                            if l.strip().startswith("[OPT]")), len(lines))
            while opt_idx > 0 and not lines[opt_idx - 1].strip():
                opt_idx -= 1
            lines[opt_idx:opt_idx] = [""] + marker_block + [""]
            draft = "\n".join(lines)
    return draft


async def _generate_options(scene_text: str, brief) -> str:
    """聚焦调用：只为当前场景生成 2-3 个动作型选项（writer 漏写时的兜底）。"""
    who = getattr(brief, "identity", "") or getattr(brief, "from_identity", "") or "小人物"
    prompt = f"""下面是正在演出的一场戏（观众是此场景中的{who}）。请给出3个观众此刻
具体可做的【动作型】选项，每个以[OPT]开头独占一行。只输出3行[OPT]，不要任何解释。
【场景】
{scene_text[-800:]}"""
    out = ""
    try:
        async for chunk in stream_chat(
            [{"role": "user", "content": prompt}], max_tokens=2000, **PARAMS_OPTIONS,
        ):
            out += chunk
    except Exception:
        return ""
    # 只保留[OPT]行，最多3个
    lines = [ln.strip() for ln in out.split("\n") if ln.strip().startswith("[OPT]")]
    return "\n".join(lines[:3])
