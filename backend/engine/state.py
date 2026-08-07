# -*- coding: utf-8 -*-
"""
GameState Schema（新三国 星空 · LangGraph State）
==================================================
依据: docs/引擎设计规范.md §2
序列化: to_dict / from_dict（前端每轮回传，沿用现状协议）
"""
from typing import TypedDict, Literal, Optional


class PlayerState(TypedDict):
    identity: str            # 玩家身份（无名奇人 → 随剧情获得称呼）
    alive: bool
    location: str            # 当前位置（颍川/洛阳/…）
    reputation: int          # 声望 0-100
    notes: list[str]         # 玩家视角的差异记录（"黄金"vs"黄巾"等）


class EraState(TypedDict):
    chapter: str             # 篇章 id（P1 黄巾风起 / P2 洛阳暗夜 / …）
    year: int                # 年份
    season: str              # 季节
    location: str            # 时代层面的位置
    world_facts: list[str]   # 世界侧已发生的事件（玩家可见）


class KnowledgeState(TypedDict):
    public: list[str]        # 玩家已见内容（看到/听到/对话）→ 可注入 Writer
    hidden: list[str]        # 世界真实（NPC内心/远处事件/未来走向）→ validate 禁泄漏
    player: list[str]        # 穿越记忆/历史直觉 → 仅玩家可引用（NPC 不当真）


class MemoryItem(TypedDict):
    id: str
    text: str
    ts: int                  # 轮次时间戳


class MemoryState(TypedDict):
    stm: list[MemoryItem]    # 短期记忆 ≤6 条
    ltm: list[MemoryItem]    # 长期记忆（无上限）
    pins: list[str]          # PIN 钉选记忆 id ≤5 条


class OptionSpec(TypedDict):
    text: str
    type: Literal["major", "minor"]
    tension: int             # 历史干预度 0-100
    effect: str              # 对玩家可见的后果说明


class NarrativeOutput(TypedDict):
    narrative: str
    options: list[OptionSpec]
    state_updates: dict
    validated: bool
    phase_report: dict
    retry_reasons: list[str]


class GameState(TypedDict):
    # ── 玩家 ──
    player: PlayerState
    # ── 时代 ──
    era: EraState
    # ── 世界 ──
    relations: dict[str, int]     # 10+ NPC 好感值 0-100
    trust: dict[str, int]         # 信任值（好感=态度，信任=信不信你的话）
    flags: list[str]              # 状态标记（暗线/见证者/知情者）
    # ── 知识分层（信息迷雾）──
    knowledge: KnowledgeState
    # ── 记忆（向量检索）──
    memory: MemoryState
    # ── 剧情 ──
    skeleton_pos: str             # 当前骨架位置（场景 id）
    tension: int                  # 历史干预度累计 0-100
    corrected: list[str]          # 已发生的修正记录
    # ── 引擎 ──
    turn: int
    retry_count: int              # 本轮重写次数
    history: list[dict]           # 对话历史（前端回传）
    last_output: Optional[NarrativeOutput]
    last_trace: str               # 最近一次修正痕迹 id（''=无）
    meta: dict                    # 运行时信息（plan/距离映射等，不持久化）


def new_game_state() -> GameState:
    """开局状态：P1 黄巾风起 · 雨夜醒来"""
    return {
        "player": {
            "identity": "无名旅人",
            "alive": True,
            "location": "颍川",
            "reputation": 0,
            "notes": [],
        },
        "era": {
            "chapter": "P1 黄巾风起",
            "year": 184,
            "season": "春",
            "location": "颍川·荒野",
            "world_facts": ["黄金之乱方兴未艾"],
        },
        "relations": {},
        "trust": {},
        "flags": [],
        "knowledge": {
            "public": [],
            "hidden": ["张角已被天意吞噬，黄金军是替代产物", "世界将在 189 年发生时间跳跃至洛阳"],
            "player": ["记忆碎片：史书上是'黄巾'，眼前旗上是'黄金'", "直觉：乱世将绵延数十年"],
        },
        "memory": {"stm": [], "ltm": [], "pins": []},
        "skeleton_pos": "P1_s1_rain",
        "tension": 0,
        "corrected": [],
        "turn": 0,
        "retry_count": 0,
        "history": [],
        "last_output": None,
        "last_trace": "",
        "meta": {},
    }


def to_dict(state: GameState) -> dict:
    """GameState → 可 JSON 序列化 dict（直接是 TypedDict，无额外处理）"""
    return dict(state)


def from_dict(data: dict) -> GameState:
    """前端回传 dict → GameState（容错缺字段）"""
    base = new_game_state()
    for k, v in (data or {}).items():
        if k in base:
            base[k] = v
    # 深层容错：保证嵌套结构完整
    for k in ("player", "era", "knowledge", "memory"):
        if not isinstance(base.get(k), dict):
            base[k] = base[k] if isinstance(base[k], dict) else {}
    return base
