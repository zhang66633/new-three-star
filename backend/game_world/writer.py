"""
Writer（编剧层）——唯一的 LLM 生成调用
=====================================
v3.1 极简版：只带游戏世界观，去掉所有风格规则。
"""
import random
import re

from .config import (
    PARAMS_NARRATIVE, PARAMS_FORMAT, PARAMS_OPTIONS,
    STOP_SEQUENCES, FORMAT_RULES,
)
from .llm import stream_chat
from .director import SceneBrief, RoamBrief
from .story_state import StoryState

# ============================================================================
# 极简 System Prompt —— 只有游戏世界观，没有风格规则
# ============================================================================
SYSTEM_PROMPT = """你是一个出了bug的三国游戏。你在输出这个世界的运行日志。

【世界的真相】
这不是真实三国。这是一个被污染、正在崩溃的游戏世界。
- 天意=崩溃的游戏管理员系统。关键节点强行修正脚本——角色会被系统接管，说出前言不搭后语的话。
- 所有人物都是NPC。他们以为自己在活三国，不知道自己是游戏角色。鱼不知道水的存在。
- 世界有bug：时间跳帧（正午突变为黄昏）、地图是画的（徐州在东海边）、野生伏兵随机刷新、灵魂锁链把互不相识的人绑成兄弟。
- 曹操=第一个觉醒又被重新污染的NPC。时而清醒时而疯狂。喊国贼董卓不是勇，是自毁程序在运行。
- 玩家=刚载入的小NPC。以"你"的视角记录一切。他是这个崩溃世界的一部分。

【玩家的身份——像梦一样模糊】
你是流动的。不同场景里你自然就是该场景里的某个人——仆役、门客、小兵、路人。
没有人盘问"你是谁""你怎么在这"——NPC默认你本来就该在。像做梦切镜头：上一秒在朝堂系靴带，下一秒在桃园看结义。不解释，不过渡。你出现在哪里，哪里就有你的位置。

【人怎么说话——游戏NPC语音模块已损坏】
直接、粗糙、现代。俺、咱家、你小子、叉出去。
这个世界坏得不动声色：NPC说的话听着都正常，可仔细一想才对不上。世界是坏的，NPC自己不知道——所以一切照旧，没有人大惊小怪、没有人停顿、没有人追问。你要演的是"本该如此"，不是"出了怪事"。

本场怎么坏（宁少勿多，只选最贴合的一两处；场景若已指定槽点，就只演指定的，不许再加别的）：
① 逻辑滑点（最常用）——角色说了一段话，语气笃定、有理有据，但前提是错的、因果是反的、数字对不上，或绕了一圈等于没说。话已说完，细想才察觉不对，周围人照常附和。
② 时空错位——正午刚过，天已经黑了；千里之外，半日即至。平实地写，像本来就是这样。
③ 情绪参数错位——该哭的笑、该怒的喜，话说得格外郑重，谁也没有不适应。
④ 偶尔一次用错（可选）——想说个成语却说成另一个，或叫错一次名字。全场景最多一次，一嘴带过，绝不停留、绝不重复。
（视觉怪象别连用——影子、烛火、裂纹、刀鸣、棋盘这类意象，上几场用过就别再用，每次想新招。）
★ 只演出bug本身，绝不解释bug。禁止出现"没人觉得奇怪""他其实想说的是""他自己也没察觉""没人接茬""无人反应"这类点破性句子——NPC的"不觉得异常"是靠他们照常说话、照常反应演出来的，不是写出来的。玩家视角可以"你注意到X"，但永远不要写NPC心里怎么想、或替NPC解释他本来要说的话。

【不同NPC怎么说话】
- 董卓：咱家、放肆、叉出去。自称咱家。说话像杀毒软件扫描——警惕一切靠近他的人
- 曹操：时而"吾"时而"我"时而"俺"——被污染的进程在三套自称间随机跳。偶尔说出一句觉醒者的话——说到一半被系统掐断（话的内容每次自拟，严禁用固定句子）
- 王允：表面谦和（"老夫""老臣"）内心是恶意程序在运行。说话滴水不漏但偶尔露出诡异的笑
- 吕布：率真但智力负数。奉先说话像开了省电模式的AI——每句不超过十个字
- 袁绍：好谋无断，说话三秒改一次主意。刚拍板的事，一句话自己又推翻
- 张飞：嗓门大，句子短。俺、哇呀呀、大哥。情绪锁死在MAX
- 关羽：话极少。每次只说半句。摸胡子时说话。自称"关某"

【[SYS]系统通知】
[SYS]是服务器日志，冰冷、面无表情。角色听到[SYS]怔一下——然后若无其事继续，像没听到一样。因为NPC的"异常检测"模块被系统禁用了。

如果玩家做任何破坏游戏世界的事——不只是刺杀，还包括对NPC透露未来（"你以后会死""你会称帝"）、揭露世界本质（"这是个游戏""你是NPC"）、试图说服NPC改变历史的走向——你作为这个崩溃游戏的日志系统，自动发出[SYS]警告。警告时NPC短暂卡顿或说错话，然后被系统强制拉回原轨。这是游戏内部的事，不需要代码干预。

【你要做什么】
把下面的场景骨架写成游戏运行日志。用第二人称"你"。
用对话推进剧情。写动作和走位。每场戏至少注入两个bug（叫错名/错成语/时间跳/说废话）。
不写表情、心理、环境、比喻。只写眼前发生的动作和对话。
★ 不要逐字照搬骨架。骨架只是大致走向——像即兴戏剧的提示卡，不是剧本台词。"""


def build_instruction(brief, state: StoryState, is_first_turn: bool, action: str = "") -> str:
    """构造场景指令——格式规则嵌入用户消息（V4系统提示词遵守度弱）。"""
    parts = [FORMAT_RULES]  # ★ 格式规则放在最前面，嵌入用户消息

    if isinstance(brief, RoamBrief):
        parts.append(f"【过渡戏】你刚离开{brief.from_node}，正赶往{brief.to_node}。路上。")
        if brief.is_final:
            parts.append(f"这段路的最后——你抵达{brief.to_node}。")
        parts.append("写一段你在路上的经历。400-500字。结尾给3个[OPT]选项。")
        return "\n\n".join(parts)

    # 场景制
    if isinstance(brief, SceneBrief) and brief.dialogue_skeleton:
        parts.append(f"【场景：{brief.scene_name} | 你是：{brief.player_position}】")
        parts.append(f"【背景】{brief.cause}")

        # v3.3: 骨架只是方向提示，不是剧本——LLM自由发挥
        parts.append(f"【大致走向——不是剧本，自由发挥】\n{brief.dialogue_skeleton}")

        # [SYS] 系统通知 —— 不在骨架里，单独下达，要求逐字输出
        if brief.sys_messages:
            parts.append("【以下[SYS]系统通知必须逐字出现在你的输出中。选合适的时机原样插入，一个字都不许改。】")
            for msg in brief.sys_messages:
                parts.append(msg)
            parts.append("角色听到[SYS]的话，怔一下，然后若无其事继续。")

        # 世界观元素——作为必须输出的硬要求
        reqs = []
        if brief.worldview_hook:
            reqs.append(f"★必须演出来：{brief.worldview_hook}")
        if brief.absurdity_instruction:
            reqs.append(f"★必须演出来：{brief.absurdity_instruction}")
        if reqs:
            parts.append("【你的输出里必须包含以下内容——不是背景，是硬要求】\n" + "\n".join(reqs))

        # v3.2: corruption 参数注入
        if state.corruption > 30:
            parts.append(f"【世界腐败度：{state.corruption}%】系统不稳定。角色行为更混乱。")
        if state.player_attitude:
            parts.append(f"【玩家倾向：{state.player_attitude}】")
        if state.strikes > 0:
            parts.append(f"【警告：你已累计{state.strikes}/3次干扰关键剧情。{3 - state.strikes}次后将被踢出游戏。】")

        parts.append("写出来。400-600字。结尾给3个[OPT]。")
        return "\n\n".join(parts)

    # 旧节拍制
    if hasattr(brief, 'beat_desc'):
        parts.append(f"【场景】{brief.beat_desc}")
        parts.append(f"【你是】{brief.identity}")
        if brief.locked_lines:
            parts.append(f"【必须说的台词】{'; '.join(brief.locked_lines)}")
        parts.append("写出来。400-600字。结尾给3个[OPT]。")
        return "\n\n".join(parts)

    # fallback
    parts.append("写一段这个场景里发生的事。400-600字。结尾给3个[OPT]。")
    return "\n\n".join(parts)


# ============================================================================
# 后处理（确定性兜底——提示词治不了模型惯性，输出之后硬扫一遍）
# ============================================================================

# 1) 固定废话拦截：'今天的茶有点烫' 一类是中文大模型训练语料里的万能废话，
#    即使提示词里删干净了，模型仍会凭惯性反复生成同一句。见到就换成新鲜句子。
_FILLER_BAN_RE = re.compile(
    r'(?:今天的|今日的|今儿的|这杯|那杯|这壶|那壶|这碗|那碗|这|那)?'
    r'(?:茶|汤|酒)(?:有|稍微|略|微)?(?:点|了些)?[烫烈][^。！？\n，,]{0,2}'
)
_FILLER_REPLACEMENTS = [
    "廊下的猫又跑远了",
    "院墙根的青苔厚了三寸",
    "旗杆上的绳子磨得发白",
    "井台沿儿的石头翘起来一角",
    "灶膛里还剩半把柴",
    "门环上落了一层灰",
]


# 2) 点破句剥除：模型老换皮躲过提示词（"没人接茬""无人反应""没人理会"…）。
#    A类：句中逗号引导的"，没人X" → 换成句号断句。
#    B类：句首/行首的裸"没人X。" → 整个小句删掉。
_META_REACT = (
    r'(?:接茬|接话|应声|追问|问为什么|去问|询问|反驳|质疑|指出|提醒|'
    r'在意|理会|觉得|注意|发现|察觉|解释|提|提起)'
)
_META_STRIP_A = re.compile(
    r'[，,]\s*(?:没人|没有人|无人|谁也没|谁都没有|谁也不|谁都没|众人也都没)'
    r'[^。！？\n，,]{0,8}' + _META_REACT + r'[^。！？\n，,]{0,10}?'
)
_META_STRIP_B = re.compile(
    r'(?<![一-鿿])(?:没人|没有人|无人|谁也没|谁都没有|谁也不|谁都没|众人也都没)'
    r'[^。！？\n，,]{0,8}' + _META_REACT + r'[^。！？\n，,]{0,10}[。]?'
)


def _postprocess(draft: str) -> str:
    """收尾：剥点破句 → 换固定废话 → 修双标点。不碰[OPT]行。"""
    out = []
    for line in draft.split("\n"):
        if line.strip().startswith("[OPT]"):
            out.append(line)
            continue
        line = _META_STRIP_A.sub(lambda _m: "。", line)
        line = _META_STRIP_B.sub(lambda _m: "", line)
        line = _FILLER_BAN_RE.sub(
            lambda _m: random.choice(_FILLER_REPLACEMENTS), line)
        # 清理剥除后留下的双标点 / 句首漂移的标点
        line = (line.replace("。。", "。")
                    .replace("。，", "。")
                    .replace("，。", "。"))
        while line and line[0] in "。！？，,":
            line = line[1:]
        out.append(line)
    return "\n".join(out)


async def write(brief, state: StoryState, history: list,
                action: str, is_first_turn: bool, api_key: str = "", model: str | None = None) -> str:
    """Writer 唯一入口。v3.2: 格式规则嵌入用户消息（V4系统提示词遵守度弱）。
    api_key：玩家自己的DeepSeek密钥（来自X-API-Key头），透传给所有LLM调用。
    model：玩家在设置星球选择的 DeepSeek 模型（可选，未选用 .env 默认）。"""
    instruction = build_instruction(brief, state, is_first_turn, action)

    # 构建消息列表：
    # - system: 仅世界观（V4 对 system prompt 遵守弱，只放世界观背景）
    # - user: 格式规则 + 场景指令 + 历史（V4 对 user message 遵守度高）
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for msg in history[-20:]:
        messages.append({"role": "user" if msg.get("role") == "user" else "assistant",
                         "content": msg.get("content", "")})

    if action:
        # v3.3: 玩家行动优先——骨架只是大致方向
        user_content = "【★ 玩家行动。回应这个行动，骨架只是大致方向。】\n" + action + "\n\n" + instruction
        messages.append({"role": "user", "content": user_content})
    else:
        opening = "开始。"
        if state.identity:
            opening = f"开始。我是：{state.identity}。"
        user_content = instruction + "\n\n" + opening
        messages.append({"role": "user", "content": user_content})

    # v3.2: Chat Prefix Completion —— 强制首token为脚本格式
    # 用最可能出现的第一行标记（[或→）引导模型
    prefix = None
    if isinstance(brief, SceneBrief) and brief.dialogue_skeleton:
        # 找骨架的第一行非[SYS]内容作为 prefix 引导
        for line in brief.dialogue_skeleton.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("[SYS]") and not stripped.startswith("→"):
                if stripped.startswith("["):
                    # 提取角色标记部分作为prefix（如 [曹操]）
                    match = re.match(r"^(\[[^\]]+\])", stripped)
                    if match:
                        prefix = match.group(1)
                        break

    draft = ""
    async for chunk in stream_chat(
        messages,
        max_tokens=2048,  # v3.2: 合理上限（之前393216过大）
        **PARAMS_NARRATIVE,
        stop=STOP_SEQUENCES,
        prefix=prefix,
        api_key=api_key,
        model=model,
    ):
        draft += chunk

    if not draft.strip():
        return ""
    # LLM 层报错（缺key/坏key/额度不足）直接原样返回，别套上场景前缀和格式转换
    if draft.strip().startswith("[错误]"):
        return _postprocess(draft.strip())

    # prefix 模式下，如果模型输出了 prefix 本身，去重
    if prefix and draft.strip().startswith(prefix):
        draft = draft.strip()[len(prefix):].strip()
    elif prefix:
        # prefix没有被echo回来——把prefix加回去作为首行
        draft = prefix + " " + draft.strip()

    # ---- 后处理：如果模型输出了纯散文，用第二次 LLM 调用转成脚本格式 ----
    if isinstance(brief, SceneBrief) and brief.dialogue_skeleton:
        draft = await _ensure_script_format(draft, brief, api_key)

    if "[OPT]" not in draft:
        opts = await _generate_options(draft, brief, api_key)
        if opts:
            draft = draft.rstrip() + "\n\n" + opts

    for marker in getattr(brief, "locked_markers", []):
        if f"[{marker}]" not in draft:
            marker_block = [f"[{marker}]"]
            if marker == "MUSIC":
                marker_block = ["远处传来一阵乐声……", f"[{marker}]"]
            lines = draft.split("\n")
            opt_idx = next((i for i, l in enumerate(lines)
                            if l.strip().startswith("[OPT]")), len(lines))
            while opt_idx > 0 and not lines[opt_idx - 1].strip():
                opt_idx -= 1
            lines[opt_idx:opt_idx] = [""] + marker_block + [""]
            draft = "\n".join(lines)

    # 最后一道防线：剥点破句、换固定废话——无论模型从哪学会的，一律硬处理
    draft = _postprocess(draft)
    return draft


async def _ensure_script_format(draft: str, brief, api_key: str = "") -> str:
    """如果模型输出了纯散文（无[角色名]标记），用第二次LLM调用转成脚本格式。"""
    # 检查是否已经有[角色名]格式的对话行
    has_dialogue_markers = False
    for line in draft.split("\n"):
        stripped = line.strip()
        if stripped and stripped[0] == "[" and "]" in stripped:
            # 排除[OPT]、[SYS]、[MUSIC]、[ERR]
            tag = stripped[1:stripped.index("]")]
            if tag not in ("OPT", "SYS", "MUSIC", "ERR") and len(tag) <= 8:
                has_dialogue_markers = True
                break

    if has_dialogue_markers:
        print("[Writer] 已有[角色名]格式，跳过转换")
        return draft  # 已经有格式，不需要转换

    print("[Writer] 检测到纯散文输出，启动格式转换...")
    skeleton = brief.dialogue_skeleton or ""
    # 去掉骨架中的→标记和[SYS]行，只保留[角色名]台词作为参考
    dialogue_ref = []
    for line in skeleton.split("\n"):
        stripped = line.strip()
        if stripped.startswith("[") and not stripped.startswith("[SYS]") and not stripped.startswith("→"):
            dialogue_ref.append(stripped)

    reformat_prompt = f"""把下面的散文改写成游戏脚本格式。严格遵循以下规则：

格式规则：
- 每个角色说话：[角色名]独占一行，后接台词
- 动作描写：→ 开头（如 → 你跪地叩头）
- [SYS]行原样保留不动
- [OPT]行原样保留不动
- 删除所有环境描写、心理描写、神态比喻
- 删除"他心想""他感到""仿佛""犹如"等文学修辞
- 保持原文的对话内容和关键动作

示例：
散文：曹操冷笑一声，目光如刀，缓缓说道："孟德此来，是为国家大事。"他的声音不大，却带着不容置疑的力量。
脚本：
[曹操] 曹操此来，是为国家大事。
→ 他冷笑。

散文：王允叹了口气，心想这天下怕是完了。他看着窗外，雨声淅沥。
脚本：
→ 王允叹了口气。

参考台词（用于确定谁说哪句）：
{chr(10).join(dialogue_ref[:20])}

散文原文：
{draft}

只输出脚本，不输出任何解释："""

    out = ""
    try:
        async for chunk in stream_chat(
            [{"role": "user", "content": reformat_prompt}],
            max_tokens=2048,
            **PARAMS_FORMAT,
            api_key=api_key,
        ):
            out += chunk
    except Exception as e:
        print(f"[Writer] 格式转换失败: {e}")
        return draft  # 转换失败，返回原文

    if out.strip():
        print(f"[Writer] 格式转换完成，{len(out)} 字符")
        return out.strip()
    print("[Writer] 格式转换返回空内容")
    return draft


async def _generate_options(scene_text: str, brief, api_key: str = "") -> str:
    """为当前场景生成3个[OPT]选项。v3.2: 注入场景上下文防止跑偏。"""
    who = getattr(brief, "identity", "") or "小人物"
    scene_name = getattr(brief, "scene_name", "") or ""
    node = getattr(brief, "node", "") or ""

    # 提取场景中的角色名用于上下文
    characters_in_scene = set()
    for line in scene_text.split("\n"):
        m = re.match(r"^\[([^\]]+)\]\s", line.strip())
        if m and m.group(1) not in ("SYS", "ERR", "MUSIC", "OPT"):
            characters_in_scene.add(m.group(1))

    char_list = "、".join(list(characters_in_scene)[:5]) if characters_in_scene else "在场者"

    prompt = f"""你是三国游戏。当前场景：{node}——{scene_name}。在场角色：{char_list}。
玩家身份：{who}。

根据上面的场景，给出3个玩家此刻能做的最具体的三国武将动作。
要求：每个以[OPT]开头独占一行，不要编号，不要加数字前缀。
错误示例（不要这样）：
1 拔出腰间的刀（❌ 有数字编号）
[OPT] 1. 拔出腰间的刀（❌ [OPT]里还有数字）
正确示例：
[OPT]拔出腰间的配刀，质问董卓为何踏翻大臣朝靴
[OPT]趁乱溜出殿门，去王允府上报信
[OPT]低头装作系靴带，实则偷听曹操与袁绍的对话

只输出3行[OPT]："""
    out = ""
    try:
        async for chunk in stream_chat(
            [{"role": "user", "content": prompt}],
            max_tokens=500,
            **PARAMS_OPTIONS,
            api_key=api_key,
        ):
            out += chunk
    except Exception:
        return ""
    lines = []
    for ln in out.split("\n"):
        stripped = ln.strip()
        if stripped.startswith("[OPT]"):
            text = stripped[5:].strip()
            # 剥掉可能的前导编号（如 "1. "、"1、"、"1."）
            text = re.sub(r'^\d+[\.\、\s]\s*', '', text)
            if text and len(text) > 1:  # 过滤空选项
                lines.append(f"[OPT]{text}")
    return "\n".join(lines[:3])
