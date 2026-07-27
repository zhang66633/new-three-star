"""
Director（导演层，Phase 2）——纯代码，零 LLM
==========================================
职责：读 StoryState 决定"这一轮拍哪一拍"，锁死本拍的道具名与必含台词，
把 RAG 蒸馏成短事实。输出 BeatBrief 交给 Writer。

关键不变量：节拍推进、道具锁定都在这里（代码）决定，Writer 拿不到不属于
本拍的台词/道具，从源头杜绝"台词错位""道具改名"。
"""
from dataclasses import dataclass, field

from knowledge.nodes import NODE_DATA, MAIN_NODES, beat_count
from services.rag import search as rag_search
from services.story_state import StoryState


@dataclass
class BeatBrief:
    node: str
    beat_index: int
    beat_desc: str                       # 本拍描述
    locked_items: dict = field(default_factory=dict)   # {道具名: 设定}
    locked_lines: list = field(default_factory=list)   # 本拍须自然说出的台词
    locked_markers: list = field(default_factory=list) # 本拍须输出的标记（如 MUSIC）
    excluded_items: list = field(default_factory=list) # 尚未登场、本拍不得出现的道具
    rag_facts: list = field(default_factory=list)      # 蒸馏后的本拍可用事实
    worldview_base: list = field(default_factory=list) # 节点级世界观底色（游戏化解读+角色身份+bug）
    beat_worldview: str = ""                            # 本拍专属世界观爆点（名场面拍才有）
    max_options: int = 3
    identity: str = ""
    cause: str = ""                      # 前因（背景）


# 节点间漫游（自由行动）最多轮数：演完节点最后一拍后，观众有 MAX_ROAM 轮
# 自由赶路，天意用巧合收束，最后一轮抵达下一节点。
MAX_ROAM = 2


@dataclass
class RoamBrief:
    """节点间漫游简报：观众刚离开上一节点、正赶往下一节点的路上。"""
    from_node: str                       # 刚离开的节点
    to_node: str                         # 赶往的下一节点
    roam_turn: int                       # 当前是第几轮漫游（1基）
    is_final: bool                       # 是否最后一轮（本轮须抵达）
    from_identity: str = ""              # 上一节点的观众身份（赶路时的身份）
    to_cause: str = ""                   # 下一节点的前因（背景）
    to_identity: str = ""                # 抵达后承接的观众身份
    max_options: int = 3


def direct(state, action: str):
    """根据当前 state 决定本轮内容：漫游中→RoamBrief（自由赶路），否则→BeatBrief（锁拍）。"""
    if state.roam_turns > 0:
        from_node = state.node
        to_node = _next_node(from_node) or from_node
        to_data = NODE_DATA.get(to_node, {})
        return RoamBrief(
            from_node=from_node,
            to_node=to_node,
            roam_turn=state.roam_turns,
            is_final=state.roam_turns >= MAX_ROAM,
            from_identity=NODE_DATA.get(from_node, {}).get("观众身份", ""),
            to_cause=to_data.get("前因", ""),
            to_identity=to_data.get("观众身份", ""),
        )

    data = NODE_DATA[state.node]
    beats = data["节拍"]
    idx = min(state.beat_index, len(beats) - 1)
    beat = beats[idx]

    # 锁定道具 = 本拍声明的 ∪ 已在玩家手上的（state.items）
    locked_items = {}
    for name in beat.get("锁定道具", []):
        if name in data.get("关键道具", {}):
            locked_items[name] = data["关键道具"][name]
    for name, info in state.items.items():
        if isinstance(info, dict) and info.get("locked"):
            locked_items.setdefault(name, info.get("desc", ""))

    # 尚未登场的道具：首次出现在更晚节拍的锁定道具里，本拍不得出现（防提前剧透）
    excluded_items = []
    for item_name in data.get("关键道具", {}):
        intro_idx = next((i for i, b in enumerate(beats)
                          if item_name in b.get("锁定道具", [])), None)
        if intro_idx is not None and idx < intro_idx and item_name not in locked_items:
            excluded_items.append(item_name)

    rag_facts = distill_rag(state.node, beat["描述"], action)

    return BeatBrief(
        node=state.node,
        beat_index=idx,
        beat_desc=beat["描述"],
        locked_items=locked_items,
        locked_lines=beat.get("锁定台词", []),
        locked_markers=beat.get("锁定标记", []),
        excluded_items=excluded_items,
        rag_facts=rag_facts,
        worldview_base=data.get("世界观", []),
        beat_worldview=beat.get("世界观", ""),
        max_options=3,
        identity=data.get("观众身份", "") or state.identity,
        cause=data.get("前因", ""),
    )


def distill_rag(node: str, beat_desc: str, action: str, top_k: int = 4) -> list:
    """RAG 只喂给 Director：检索后截短成'事实'，而非整段原文倾倒给 Writer。"""
    try:
        query = f"新三国 {node} {beat_desc} {action}".strip()
        results = rag_search(query, top_k=top_k)
        return [r["text"][:80] for r in results if r.get("text")]
    except Exception:
        return []


def _next_node(node: str):
    """按主线顺序返回下一个节点；最后一个节点（归晋）返回 None（游戏通关）。"""
    if node in MAIN_NODES:
        i = MAIN_NODES.index(node)
        if i + 1 < len(MAIN_NODES):
            return MAIN_NODES[i + 1]
    return None


def advance(state: StoryState, brief) -> StoryState:
    """状态推进（代码独占）：
    - 本轮是漫游（RoamBrief）：最后一轮→抵达下一节点（node切换/beat归零/roam清零）；
      否则 roam_turns+1 继续漫游。
    - 本轮是正常节拍：演完节点最后一拍→进入漫游（roam_turns=1，观众自由赶路）；
      否则 beat_index+1。归晋无下一节点，演完最后一拍停留原地（游戏通关）。
    - 本拍锁定道具登记进 state.items；turn +1。
    """
    s = StoryState.from_dict(state.to_dict())

    if isinstance(brief, RoamBrief):
        if brief.is_final:
            s.node = brief.to_node
            s.beat_index = 0
            s.roam_turns = 0
        else:
            s.roam_turns = s.roam_turns + 1
        s.turn += 1
        return s

    total = beat_count(s.node)
    if s.beat_index >= total - 1:
        # 演完最后一拍：有下一节点→进入漫游（自由赶路），否则停留（归晋通关）
        if _next_node(s.node):
            s.roam_turns = 1
    else:
        s.beat_index = s.beat_index + 1
    for name, desc in brief.locked_items.items():
        s.items.setdefault(name, {"locked": True, "desc": desc})
    s.turn += 1
    return s
