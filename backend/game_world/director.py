"""
Director（导演层，v3.0 场景制）——纯代码，零 LLM
==============================================
职责：读 StoryState → 决定"这一轮拍哪一场景"→ 输出 SceneBrief。
场景制核心改动：每场景带原剧本原文，Writer 工作从"凭空生成"变为"改编原剧本"。

兼容层：同时支持新"场景"格式和旧"节拍"格式。
"""
from dataclasses import dataclass, field
import random

from .nodes import NODE_DATA, MAIN_NODES, scene_count
from .beat_knowledge import (
    get_beat_knowledge, get_worldview_hook, get_absurdity, get_mechanism_name,
)
from .absurdity_injections import (
    pick_absurdity, fill_absurdity_template, get_character_context,
    CHARACTER_NAMES,
)
from .knowledge_cards import distill_cards_for_beat
from .rag import search as rag_search
from .story_state import StoryState


@dataclass
class SceneBrief:
    """场景制简报：一场完整的戏 + 原剧本原文。

    与旧 BeatBrief 的关键区别：
    - original_script（原剧本原文）替代了 beat_desc（一句话动作摘要）
    - player_position 明确玩家在场景中的位置
    - Writer 的职责是"改编原剧本"而非"根据摘要凭空写"
    """
    node: str
    scene_index: int
    scene_name: str = ""
    original_script: str = ""              # 原剧本原文（保留用于 reference）
    dialogue_skeleton: str = ""            # ★对话骨架（纯对话+→动作，Writer 的实际输入）
    player_position: str = ""              # 玩家在此场景中的位置/身份
    locked_items: dict = field(default_factory=dict)
    locked_lines: list = field(default_factory=list)
    locked_markers: list = field(default_factory=list)
    excluded_items: list = field(default_factory=list)
    rag_facts: list = field(default_factory=list)
    worldview_base: list = field(default_factory=list)   # 世界观底色
    worldview_hook: str = ""                              # 本场景世界观钩子
    absurdity_instruction: str = ""                       # 本场景槽点指令
    knowledge_cards: list = field(default_factory=list)
    allowed_characters: list = field(default_factory=list)
    excluded_characters: list = field(default_factory=list)
    identity_shift: str = ""                               # 身份切换 [SYS] 标记
    sys_messages: list = field(default_factory=list)       # 骨架中解析出的 [SYS] 行（逐字输出）
    max_options: int = 3
    identity: str = ""
    cause: str = ""

    # 兼容旧 beat 格式的字段别名
    @property
    def beat_desc(self) -> str:
        """兼容旧代码：对于场景制，返回场景名称+玩家位置作为'描述'。"""
        if self.original_script:
            return f"{self.scene_name}｜{self.player_position}"
        return ""

    @property
    def beat_index(self) -> int:
        return self.scene_index

    @property
    def beat_worldview(self) -> str:
        return self.worldview_hook


# 节点间漫游最多轮数
MAX_ROAM = 2


@dataclass
class RoamBrief:
    """节点间漫游简报。"""
    from_node: str
    to_node: str
    roam_turn: int
    is_final: bool
    from_identity: str = ""
    to_cause: str = ""
    to_identity: str = ""
    max_options: int = 3


def direct(state, action: str):
    """返回 SceneBrief（场景制）或 BeatBrief 兼容格式（旧节拍制）。"""
    if state.roam_turns > 0:
        return _build_roam(state)

    data = NODE_DATA[state.node]
    scenes = data.get("场景", [])
    if scenes:
        return _build_scene_brief(state, data, scenes, action)
    return _build_beat_brief_legacy(state, data)


def _build_roam(state):
    """节点间漫游。"""
    from_node = state.node
    to_node = _next_node(from_node) or from_node
    to_data = NODE_DATA.get(to_node, {})
    return RoamBrief(
        from_node=from_node,
        to_node=to_node,
        roam_turn=state.roam_turns,
        is_final=state.roam_turns >= MAX_ROAM,
        from_identity=NODE_DATA.get(from_node, {}).get("默认身份", ""),
        to_cause=to_data.get("前因", ""),
        to_identity=to_data.get("默认身份", ""),
    )


def _build_scene_brief(state, data: dict, scenes: list, action: str = "") -> SceneBrief:
    """场景制：从原剧本原文构建 SceneBrief。"""
    idx = min(state.scene_index, len(scenes) - 1)
    scene = scenes[idx]

    # ---- 锁定道具 ----
    locked_items = {}
    for name in scene.get("锁定道具", []):
        if name in data.get("关键道具", {}):
            locked_items[name] = data["关键道具"][name]
    for name, info in state.items.items():
        if isinstance(info, dict) and info.get("locked"):
            locked_items.setdefault(name, info.get("desc", ""))

    # ---- RAG 事实 ----
    rag_facts = _distill_rag(state.node, scene.get("名称", ""), action, top_k=2)

    # ---- 世界观 ----
    worldview_base = list(data.get("世界观底色", [])[:2])
    worldview_hook = scene.get("世界观钩子", "")
    # 场景没写钩子时，从 beat_knowledge 补
    if not worldview_hook:
        bk = get_beat_knowledge(state.node, idx)
        if bk and bk.get("worldview_hook"):
            worldview_hook = bk["worldview_hook"]

    # ---- 槽点 ----
    absurdity_instruction = ""
    if scene.get("槽点指令"):
        absurdity_instruction = scene["槽点指令"]
    else:
        # 先查 beat_knowledge
        bk = get_beat_knowledge(state.node, idx)
        if bk and bk.get("absurdity"):
            absurdity_instruction = bk["absurdity"].get("instruction", "")
        if not absurdity_instruction:
            # 兜底：slot machine —— 腐败度高时选更难的槽点
            difficulty = "medium" if state.corruption > 50 else "easy"
            absurdities = pick_absurdity(
                beat_desc=scene.get("名称", ""),
                node=state.node,
                difficulty=difficulty,
                count=1,
            )
            if absurdities:
                ctx = _build_absurdity_context(state.node, idx)
                absurdity_instruction = fill_absurdity_template(absurdities[0]["instruction"], ctx)

    # ---- v3.2: flag-driven context 增强世界观钩子 ----
    flag_context = ""
    if state.flags.get("defied_dong_zhuo"):
        flag_context += "你之前顶撞了董卓——这个守门进程已经开始注意到你。"
    if state.flags.get("acted_aggressively"):
        flag_context += "你的暴力行为让系统的威胁检测模块提高了对你的关注度。"
    if state.corruption > 50:
        flag_context += "世界的腐败度已经很高——NPC行为更不稳定，[SYS]通知更频繁。"
    if state.player_attitude == "aggressive":
        flag_context += "你选择了暴力之路。天意正在标记你的进程。"
    elif state.player_attitude == "diplomatic":
        flag_context += "你选择了对话之路。但在这个崩溃的世界里，语言也是bug的一种。"
    if flag_context and worldview_hook:
        worldview_hook = worldview_hook + " " + flag_context

    # ---- 知识卡 ----
    card_texts = distill_cards_for_beat(
        node=state.node,
        characters=_infer_characters(scene.get("原剧本", "")),
        max_cards=2,
    )
    for ct in card_texts[:1]:
        if ct not in worldview_base:
            worldview_base.append(ct)

    # ---- 解析骨架中的 [SYS] 行 ----
    sys_messages = []
    cleaned_skeleton = ""
    raw_skeleton = scene.get("对话骨架", "")
    for line in raw_skeleton.split("\n"):
        stripped = line.strip()
        if stripped.startswith("[SYS]"):
            sys_messages.append(stripped)
        else:
            cleaned_skeleton += line + "\n"
    cleaned_skeleton = cleaned_skeleton.rstrip("\n")

    # v3.2: 身份模糊化——不显式宣布切换，让玩家自然融入新场景
    identity_shift = ""
    prev_pos = getattr(state, 'last_player_position', '')
    curr_pos = scene.get("玩家位置", "")
    if prev_pos and curr_pos and prev_pos != curr_pos:
        # 不再生成 [SYS] 身份切换通知——玩家像梦里换场景一样自然出现
        identity_shift = ""
    state.last_player_position = curr_pos

    return SceneBrief(
        node=state.node,
        scene_index=idx,
        scene_name=scene.get("名称", ""),
        original_script=scene.get("原剧本", ""),
        dialogue_skeleton=cleaned_skeleton,
        player_position=scene.get("玩家位置", ""),
        locked_items=locked_items,
        locked_lines=scene.get("锁定台词", []),
        locked_markers=scene.get("锁定标记", []),
        excluded_items=[],
        rag_facts=rag_facts,
        worldview_base=worldview_base,
        worldview_hook=worldview_hook,
        absurdity_instruction=absurdity_instruction,
        knowledge_cards=card_texts,
        allowed_characters=scene.get("出场角色", []),
        excluded_characters=scene.get("禁止角色", []),
        identity_shift=identity_shift,
        sys_messages=sys_messages,
        max_options=3,
        identity=data.get("默认身份", "") or state.identity,
        cause=data.get("前因", ""),
    )


def _build_beat_brief_legacy(state, data: dict):
    """旧节拍制兼容层。返回 SceneBrief 格式，从节拍描述构造。"""
    beats = data.get("节拍", [])
    idx = min(state.scene_index, len(beats) - 1)
    beat = beats[idx]

    locked_items = {}
    for name in beat.get("锁定道具", []):
        if name in data.get("关键道具", {}):
            locked_items[name] = data["关键道具"][name]
    for name, info in state.items.items():
        if isinstance(info, dict) and info.get("locked"):
            locked_items.setdefault(name, info.get("desc", ""))

    rag_facts = _distill_rag(state.node, beat.get("描述", "")[:60], "", top_k=2)
    worldview_base = list(data.get("世界观底色", data.get("世界观", []))[:2])

    return SceneBrief(
        node=state.node,
        scene_index=idx,
        scene_name="",
        original_script="",  # 旧格式无原剧本
        player_position=data.get("默认身份", data.get("观众身份", "")),
        locked_items=locked_items,
        locked_lines=beat.get("锁定台词", []),
        locked_markers=beat.get("锁定标记", []),
        rag_facts=rag_facts,
        worldview_base=worldview_base,
        worldview_hook=beat.get("世界观钩子", ""),
        allowed_characters=beat.get("出场角色", []),
        excluded_characters=beat.get("禁止角色", []),
        max_options=3,
        identity=data.get("默认身份", data.get("观众身份", "")) or state.identity,
        cause=data.get("前因", ""),
    )


def _distill_rag(node: str, query_text: str, action: str, top_k: int = 2) -> list:
    """RAG 检索。"""
    try:
        query = f"新三国 {node} {query_text[:60]}".strip()
        results = rag_search(query, top_k=top_k)
        return [r["text"][:150] for r in results if r.get("text")]
    except Exception:
        return []


# 槽点兜底模板的取值池：从多组里随机抽，避免每次注入同一句具体话
# ——LLM 一旦在指令里反复看到同一原句就会照抄。
_IDIOM_TRIPLES = [
    ("多此一举的额外", "画蛇添足", "画蛇填足"),
    ("守着树桩等兔子的侥幸", "守株待兔", "守株逮兔"),
    ("对不懂的人白费口舌", "对牛弹琴", "对牛鼓琴"),
    ("抱着老办法找剑的刻板", "刻舟求剑", "刻舟寻剑"),
]
_INVENTED_SAYINGS = ["龙行千里，终须一潜", "棋落无悔，灯起有明", "风过留痕，人过留影"]


def _build_absurdity_context(node: str, scene_idx: int) -> dict:
    """构建槽点模板的上下文。"""
    correct_meaning, correct_phrase, wrong_phrase = random.choice(_IDIOM_TRIPLES)
    ctx = {
        "primary_speaker": "曹操", "target": "董卓",
        "speaker": "曹操", "listener": "在场者",
        "character": "曹操", "character_a": "曹操", "character_b": "董卓",
        "name": "曹操", "courtesy": "孟德", "self_name": "吾", "self_courtesy": "孟德",
        "from_place": "许昌", "to_place": "洛阳",
        "time_a": "正午", "time_b": "夜深",
        "season_a": "盛夏", "weather_b": "大雪",
        "emotion_a": "平静", "emotion_b": "暴怒",
        "short_action": "拢了拢袖子", "long_time_passed": "半个时辰过去了",
        "correct_meaning": correct_meaning, "wrong_phrase": wrong_phrase,
        "correct_phrase": correct_phrase, "invented_saying": random.choice(_INVENTED_SAYINGS),
    }
    return ctx


def _infer_characters(text: str) -> list[str]:
    """从文本中推断角色名。"""
    found = []
    for name in CHARACTER_NAMES:
        if name in text:
            found.append(name)
    return found[:3]


def _next_node(node: str):
    if node in MAIN_NODES:
        i = MAIN_NODES.index(node)
        if i + 1 < len(MAIN_NODES):
            return MAIN_NODES[i + 1]
    return None


def advance(state: StoryState, brief) -> StoryState:
    """状态推进。支持 SceneBrief、旧 BeatBrief、RoamBrief。"""
    s = StoryState.from_dict(state.to_dict())

    if isinstance(brief, RoamBrief):
        if brief.is_final:
            s.node = brief.to_node
            s.scene_index = 0
            s.roam_turns = 0
        else:
            s.roam_turns = s.roam_turns + 1
        s.turn += 1
        return s

    # SceneBrief 或 BeatBrief
    total = scene_count(s.node)
    if s.scene_index >= total - 1:
        if _next_node(s.node):
            s.roam_turns = 1
    else:
        s.scene_index = s.scene_index + 1
    for name, desc in brief.locked_items.items():
        s.items.setdefault(name, {"locked": True, "desc": desc})
    s.turn += 1
    return s
