# -*- coding: utf-8 -*-
"""
GameState Schema（新三国 星空 · LangGraph State）
==================================================
依据: docs/引擎设计规范.md §2
序列化: to_dict / from_dict（前端每轮回传，沿用现状协议）
"""
from typing import TypedDict, Literal, Optional
import os
import json


class PlayerState(TypedDict):
    identity: str            # 玩家身份（无名奇人 → 随剧情获得称呼）
    alive: bool
    location: str            # 当前位置（颍川/洛阳/…）
    reputation: int          # 声望 0-100
    personality: str         # 性格标签（如"冷静·机敏·仁厚"）— 人格铁律锁定
    goal: str                # 当前阶段目标（如"在乱世中活下去"）
    inner_voice: str         # 最近内心独白（每轮更新）
    notes: list[str]         # 玩家视角的差异记录（"黄金"vs"黄巾"等）
    # ── 自由沙盒：资产/属性/称号/成就（独立字段，见自由沙盒重构设计 §三）──
    assets: list[str]        # 物品描述列表（如 ["破布衣","半块干粮","生锈短刀"]）
    coins: int               # 金钱
    stats: dict              # 属性 {stamina, hunger, wound} 0-100
    titles: list[str]        # 动态称号（事件授予）
    achievements: list[str]  # 已解锁成就 id


class EraState(TypedDict):
    chapter: str             # 篇章 id（P1 黄金风起 / P2 洛阳暗夜 / …）
    year: int                # 年份
    season: str              # 季节
    location: str            # 时代层面的位置


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
    relations: dict[str, int]     # NPC 好感值 0-100（关系网权威源；相遇才登记，不再开局预填）
    trust: dict[str, int]         # 信任值（好感=态度，信任=信不信你的话）
    stances: dict[str, str]       # 立场标签（LLM 动态生成，兼容旧档；开局空）
    encountered: list[str]        # 已相遇角色名集合（关系网只显示这些人；首遇 LLM 生成初见好感）
    flags: list[str]              # 状态标记（暗线/见证者/知情者）
    # ── 知识分层（信息迷雾）──
    knowledge: KnowledgeState
    # ── 记忆（向量检索）──
    memory: MemoryState
    # ── 剧情 ──
    skeleton_pos: str             # 当前骨架位置（场景/地点 id）
    tension: int                  # 历史干预度累计 0-100
    corrected: list[str]          # 已发生的修正记录
    foreshadowing: list[str]      # 未解伏笔/承诺追踪（如"曹操欠你一个人情"）
    briefing: str                 # 本拍 LLM 合成世界简报（§3.3：时间跨度+相关点；无动态=''）
    world_rumors: list[str]       # 传闻层（NPC 传的、未证实的话）
    world_events: list[dict]      # 事实层：世界事件队列（离开时预生成，见自由沙盒重构设计 §二）
    world_date: dict              # 世界具体日期 {year, month, day}（取代 turns_left 时节）
    location_state: Optional[dict]  # 地点面板状态 {current, unlocked, next_station, rumored}（director 每拍写入）
    rumor_unlocked: list[str]       # 传闻解锁的地点（玩家「打听X」确认过传闻 → 可赶路，独立于 visited）
    character_states: dict          # 角色世界状态档案（自由大世界·决策8）：按需登记交集角色
                                   #   {名: {location/activity/goal/attitude/alive/dies_on/known/last_seen/seen_at/tags/notes}}
    vitals_alarm: Optional[str]     # 濒死标记（stamina/hunger/wound，下拍 writer 演后果；脱离=''）
    dead: Optional[bool]            # 死亡（三属性同时极端，alive=False）——前端读档最近快照
    # ── 引擎 ──
    turn: int
    scene_turns: int              # 当前地点驻留轮次（供 world 周期事件判定；未声明会被 LangGraph 丢弃）
    retry_count: int              # 本轮重写次数
    history: list[dict]           # 对话历史（前端回传）
    scene_state: Optional[dict]   # 连续性子系统：结构化"上一拍状态"（见 continuity.py，取代窗口化历史反推）
    last_output: Optional[NarrativeOutput]
    last_trace: str               # 最近一次修正痕迹 id（''=无）
    meta: dict                    # 运行时信息（plan/距离映射等，不持久化）


def _character_personas() -> dict:
    """人物抽象人设标签库（character_personas.json）：name → tags。mtime 缓存。

    标签源自折棒吐槽提炼（新三国观众共识的抽象梗人设），用于关系网多标签展示
    与天意「第一印象」生成的参考。静态定义，开局即可用，不随存档变化。
    """
    cache = _character_personas.__dict__
    path = os.path.join(os.path.dirname(__file__), "..", "knowledge", "character_personas.json")
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return cache.get("_data") or {}
    if cache.get("_mtime") != mtime:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f) or {}
            cache["_data"] = {p["name"]: p.get("tags", []) for p in data.get("personas", []) if isinstance(p, dict) and p.get("name")}
            cache["_mtime"] = mtime
        except (OSError, json.JSONDecodeError):
            pass
    return cache.get("_data") or {}


def get_persona_tags(name: str) -> list:
    """取角色抽象人设标签（无则空列表）。供关系网/第一印象生成复用。"""
    return _character_personas().get(name, [])


def new_game_state() -> GameState:
    """开局状态：P1 黄金风起 · 雨夜醒来"""
    # 关系网不再开局预填：玩家「遇到才登记」（决策 14 哲学），relations/trust/stances 从空开始，
    # 首次相遇由 LLM 生成 first_impression（初见好感 10-60 区间）。见 writer 系统 prompt 相遇规则。
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
            # 自由沙盒：开局资产/属性（延续"身无分文、衣衫褴褛"设定）
            "assets": ["破布衣", "无鞋"],
            "coins": 0,
            "stats": {"stamina": 80, "hunger": 60, "wound": 0},
            "titles": [],
            "achievements": [],
        },
        "era": {
            "chapter": "P1 黄金风起",
            "year": 184,
            "season": "春",  # 184-02 → season_of(2)=春（见 world.season_of，开局"春雨夜醒来"）；director 每拍按 world_date 派生覆盖
            "location": "颍川",
        },
        "relations": {},   # 关系网：玩家遇到才登记（首次相遇由 LLM 生成初见好感）
        "trust": {},         # 信任：同上，相遇才建
        "stances": {},       # 立场标签：LLM 动态生成（兼容旧档字段，开局空）
        "encountered": [],   # 已相遇角色名集合（关系网只显示这些人）
        "flags": [],
        "knowledge": {
            "public": [],
            "hidden": ["张角已被天意吞噬，黄金军是替代产物", "世界将在 189 年发生时间跳跃至洛阳"],
            "player": ["记忆碎片：史书上是'黄巾'，眼前旗上是'黄金'", "直觉：乱世将绵延数十年", "记忆：这场起义好像第八个月就会平息——虽然现在才刚起"],
        },
        "memory": {"stm": [], "ltm": [], "pins": []},
        "skeleton_pos": "颍川",  # 自由大世界：skeleton_pos = 地点名（不再是场景 id）
        "tension": 0,
        "corrected": [],
        "foreshadowing": [],
        "briefing": "",            # 本拍 LLM 合成世界简报（§3.3）
        "world_rumors": ["颍川传言：黄金军近日在附近出没", "朝廷发榜征兵"],
        "world_events": [],           # 事实层：世界事件队列（离开时预生成，见自由沙盒重构设计）
        "world_date": {"year": 184, "month": 2, "day": 1},  # 世界具体日期（取代 turns_left 时节）
        "location_state": None,       # 地点面板状态（director 每拍写入）
        "rumor_unlocked": [],         # 传闻解锁的地点（打听确认后加入，见 worlddata.LOCATION_RUMORS）
        "character_states": {},       # 角色世界状态档案（自由大世界·决策8）：按需登记交集角色
        "vitals_alarm": "",           # 濒死标记（无濒死为空串）
        "dead": False,                # 死亡标记（三属性极端）
        "turn": 0,
        "scene_turns": 1,          # 当前地点驻留轮次（供 world 周期事件判定，见 world.py）
        "retry_count": 0,
        "history": [],
        "scene_state": None,      # None = 未初始化（旧存档/未接线），continuity 回退历史扫描
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
    # tension 钳位 0-100（防前端伪造干预度强制触发天意修正）；轮次字段钳位正整数
    try:
        base["tension"] = max(0, min(100, int(base.get("tension", 0))))
    except (TypeError, ValueError):
        base["tension"] = 0
    for _k in ("turn", "scene_turns", "retry_count"):
        try:
            base[_k] = max(0, min(1_000_000, int(base.get(_k, 0))))
        except (TypeError, ValueError):
            base[_k] = 0
    # encountered 钳制：字符串列表去重 + 上限（防前端注入脏数据/无限膨胀）
    enc = base.get("encountered")
    if isinstance(enc, list):
        seen_names = []
        for n in enc:
            if isinstance(n, str) and n.strip() and n not in seen_names and len(seen_names) < _LIST_CAP:
                seen_names.append(n.strip())
        base["encountered"] = seen_names
    elif not isinstance(enc, list):
        base["encountered"] = []

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
    # stances 钳位：键数 ≤_DICT_CAP、每值 ≤12 字（防前端放大长文本）
    st = base.get("stances")
    if isinstance(st, dict):
        base["stances"] = {n: str(v)[:12] for n, v in list(st.items())[:_DICT_CAP]}
    # 自由沙盒：player 子字段保护（stats 钳位 0-100；list 字段钳位）
    pl = base.get("player")
    if isinstance(pl, dict):
        st = pl.get("stats")
        if isinstance(st, dict):
            pl["stats"] = {
                kk: max(0, min(100, int(vv)))
                for kk, vv in list(st.items())[:_DICT_CAP]
                if isinstance(vv, (int, float)) or str(vv).lstrip("-").isdigit()
            }
        for kk in ("assets", "titles", "achievements"):
            if isinstance(pl.get(kk), list):
                pl[kk] = [str(x)[:_STR_CAP] for x in pl[kk]][:_LIST_CAP]
        try:
            pl["coins"] = max(0, int(pl.get("coins", 0)))
        except (TypeError, ValueError):
            pl["coins"] = 0
    # knowledge.hidden 收紧（防 check_hidden_leak O(n²) DoS：每条 ≤200 字、≤50 条）
    kn = base.get("knowledge")
    if isinstance(kn, dict) and isinstance(kn.get("hidden"), list):
        kn["hidden"] = [str(h)[:200] for h in kn["hidden"]][:50]
    # STM 截断到 6（防前端放大，与 remember.STM_CAP 一致）
    mem = base.get("memory")
    if isinstance(mem, dict) and isinstance(mem.get("stm"), list) and len(mem["stm"]) > 6:
        mem["stm"] = mem["stm"][-6:]
    # 角色世界状态档案：钳制（每角色 attitude 0-100、tags/notes 上限、值类型保护）
    cs = base.get("character_states")
    if isinstance(cs, dict):
        clamped = {}
        for name, st in list(cs.items())[:_DICT_CAP]:
            if not isinstance(st, dict):
                continue
            s = dict(st)
            try:
                s["attitude"] = max(0, min(100, int(s.get("attitude", 50))))
            except (TypeError, ValueError):
                s["attitude"] = 50
            if isinstance(s.get("tags"), list):
                s["tags"] = [str(x)[:20] for x in s["tags"]][:4]
            if isinstance(s.get("notes"), list):
                s["notes"] = [str(x)[:60] for x in s["notes"]][:3]
            for kk in ("location", "activity", "goal", "last_seen", "seen_at"):
                if kk in s:
                    s[kk] = str(s[kk])[:_STR_CAP]
            clamped[name] = s
        base["character_states"] = clamped
    return base
