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
    personality: str         # 性格标签（如"冷静·多疑·仁厚"）— 人格铁律锁定
    goal: str                # 当前阶段目标（如"在乱世中活下去"）
    inner_voice: str         # 最近内心独白（每轮更新）
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
    scene: str               # 场景标记（如 "颍川·雨夜荒野"）
    time: str                # 可读时间标记（如 "184年·春"）


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
    foreshadowing: list[str]      # P2 未解伏笔/承诺追踪（如"曹操欠你一个人情"）
    world_rumors: list[str]       # §3.6 世界动态（流言/军报/势力变动）
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
            "personality": "沉稳·机敏·仁心",  # 人格铁律锁定（开局默认，玩家行为可自然偏移）
            "goal": "在乱世中活下去，弄清自己为何在此",
            "inner_voice": "",
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
        "foreshadowing": [],
        "world_rumors": ["颍川传言：黄金军近日在附近出没", "朝廷发榜征兵"],
        "turn": 0,
        "retry_count": 0,
        "history": [],
        "last_output": None,
        "last_trace": "",
        "meta": {},
    }


def to_dict(state: GameState) -> dict:
    """GameState → 可 JSON 序列化 dict

    meta 只保留最小 plan_summary（前端场景上下文）：phase_report/validate_reasons/
    retry_reasons/prev_era 是图内运行时信息，前端用 last_output.phase_report（SSE 单独发），
    剔除可防状态体积随轮次膨胀。
    """
    d = dict(state)
    meta = d.get("meta")
    if isinstance(meta, dict):
        d["meta"] = {"plan_summary": meta.get("plan_summary", {})}
    return d


# 前端回传白名单 + 长度上限（防提示注入 / 超大 body / 内存 DoS）
# 键白名单 = new_game_state 的全部顶层键；字符串/列表做长度钳制
_STR_CAP = 2000      # 单个字符串上限（action/叙事/记忆条目）
_LIST_CAP = 200      # 单个列表上限（history/memory/flags 等）
_DICT_CAP = 100      # 单个 dict 上限（relations/trust 等）


def _cap(v, cap: int):
    """递归钳制字符串长度与容器大小"""
    if isinstance(v, str):
        return v[:cap] if len(v) > cap else v
    if isinstance(v, list):
        return [_cap(x, cap) for x in v[:cap]]
    if isinstance(v, dict):
        return {k: _cap(x, cap) for k, x in list(v.items())[:cap]}
    return v


def from_dict(data: dict) -> GameState:
    """前端回传 dict → GameState（容错缺字段 + 白名单 + 长度钳制）"""
    base = new_game_state()
    for k, v in (data or {}).items():
        if k not in base:
            continue  # 白名单外键丢弃（防注入）
        # 嵌套 dict（player/era/knowledge/memory）：合并而非覆盖，保护新增字段
        if isinstance(base[k], dict) and isinstance(v, dict):
            merged = dict(base[k])
            merged.update(_cap(v, _STR_CAP))
            base[k] = merged
        elif isinstance(base[k], dict):
            base[k] = dict(base[k])  # 非 dict 覆盖 → 丢弃回默认
        else:
            base[k] = _cap(v, _LIST_CAP if isinstance(base[k], list) else _STR_CAP)
    # 深层容错：保证嵌套结构完整
    for k in ("player", "era", "knowledge", "memory"):
        if not isinstance(base.get(k), dict):
            base[k] = {}
    # relations/trust 值钳位 0-100 整数（防恶意前端放大/字符串/负数）
    for k in ("relations", "trust"):
        d = base.get(k)
        if isinstance(d, dict):
            clamped = {}
            for name, v in list(d.items())[:_DICT_CAP]:
                try:
                    clamped[name] = max(0, min(100, int(v)))
                except (TypeError, ValueError):
                    continue
            base[k] = clamped
    # knowledge.hidden 收紧（防 check_hidden_leak O(n²) DoS：每条 ≤200 字、≤50 条）
    kn = base.get("knowledge")
    if isinstance(kn, dict) and isinstance(kn.get("hidden"), list):
        kn["hidden"] = [str(h)[:200] for h in kn["hidden"]][:50]
    # STM 截断到 6（防前端放大，与 remember.STM_CAP 一致）
    mem = base.get("memory")
    if isinstance(mem, dict) and isinstance(mem.get("stm"), list) and len(mem["stm"]) > 6:
        mem["stm"] = mem["stm"][-6:]
    return base
