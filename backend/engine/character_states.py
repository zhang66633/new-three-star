# -*- coding: utf-8 -*-
"""
角色世界状态档案（自由大世界 · 决策 7/8/9/14）
================================================
职责：维护"与玩家有交集的角色"的世界状态（位置/在做什么/目标/对玩家态度）。
- 引擎更新事实（update_char_facts）：位置/存活/最近见——按 timeline 到点事件驱动，LLM 不可写
- LLM 更新软状态（merge_character_soft_state）：doing/goal/attitude/tags/notes——writer 声明
- 按需登记（ensure_character）：只维护玩家接触过的角色（决策 14），未接触的到点由时间线带过

数据：knowledge/character_states.json（seeds 提供初始位置/活动/目标 + _starts 默认值）。
"""

# 引擎事实字段（LLM 不可写）：事实层由引擎/时间线权威维护
FACT_FIELDS = {"location", "alive", "dies_on", "last_seen", "seen_at", "known"}

# LLM 软状态字段（LLM 可写）：软状态由 writer 声明维护
# 统一键：LLM 协议 emit doing → 落地 activity（前端 CharacterState/CharacterPanel、writer 注入、
# from_dict 钳制都读 activity，勿双轨）。引擎事实层 update_char_facts 也写 activity（在场事件摘要），
# 语义一致：activity = 角色"正在做什么"。
SOFT_FIELDS = {"activity", "goal", "attitude", "tags", "notes"}


def _load_seeds() -> dict:
    """加载角色种子（seeds + _starts + _generic）。mtime 缓存。"""
    import json
    import os
    _cache = _load_seeds.__dict__
    path = os.path.join(os.path.dirname(__file__), "..", "knowledge", "character_states.json")
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return _cache.get("_data") or {}
    if _cache.get("_mtime") != mtime:
        try:
            with open(path, encoding="utf-8") as f:
                _cache["_data"] = json.load(f)
            _cache["_mtime"] = mtime
        except (OSError, json.JSONDecodeError):
            pass
    return _cache.get("_data") or {}


def ensure_character(state: dict, name: str) -> dict:
    """按需登记：玩家首次接触某角色 → 从种子初始化并登记。已在则返回。

    决策 14（只维护交集角色）：不启动全量初始化 14 人，玩家接触谁就登记谁。
    未接触角色不占档案（view_scene 只在到点事件 key_npcs / 在场常态注入时触发登记）。
    """
    states = state.get("character_states")
    if states is None:
        states = {}
        state["character_states"] = states
    if name in states:
        return states[name]
    data = _load_seeds()
    seed = (data.get("seeds") or {}).get(name) or (data.get("_generic") or {}).get(name) or {}
    starts = data.get("_starts") or {}
    st = {
        "name": name,
        "location": seed.get("location", starts.get("location", "行踪未明")),
        "activity": seed.get("activity", starts.get("activity", "行止未明")),
        "goal": seed.get("goal", ""),
        # 双轨合并：好感以 relations（关系网）为唯一权威，attitude 从这里派生，
        # 避免 character_states.attitude 与 relations[name] 各自演化而漂移
        "attitude": (state.get("relations") or {}).get(name, starts.get("attitude", 50)),
        "alive": seed.get("alive", starts.get("alive", True)),
        "dies_on": seed.get("dies_on", starts.get("dies_on")),
        "known": False,
        "last_seen": "",
        "seen_at": "",
        "tags": [],
        "notes": [],
    }
    states[name] = st
    return st


def present_characters(state: dict, location: str = "", due_events: list = None) -> list[str]:
    """当前地点在场的已知角色（决策 10：在场即呈现）。

    来源：① character_states 中 location 匹配当前地点的角色（无论 known）；
         ② relations 键（玩家有过关系的人）；
         ③ 到点事件 key_npcs（在场事件主角，先 ensure 登记）。
    返回角色名列表（去重）。
    """
    names = []
    states = state.get("character_states") or {}
    for n, st in states.items():
        cl = (st or {}).get("location", "")
        if cl and location and (cl in location or location in cl):
            names.append(n)
    # 已登记且 known（玩家真正见过）的关系角色——关系网预填的 30 人仅"闻其名"，
    # 不算在场（预填 relations 后不能拿 relations 键当在场信号）
    for n in (state.get("relations") or {}):
        cst = states.get(n)
        if cst and cst.get("known") and n not in names:
            names.append(n)
    # 到点事件 key_npcs（在场事件主角）
    for e in (due_events or []):
        for npc in (e.get("key_npcs") or []):
            if npc and npc not in names:
                ensure_character(state, npc)
                names.append(npc)
    return names


def update_char_facts(state: dict, due_events: list, new_wd: dict, location: str = "",
                        prev_location: str = "") -> None:
    """引擎更新事实（决策 9：引擎管事实，LLM 不可写）。

    对每条到点事件：
      - key_npcs 中"在场"（事件 locations 含玩家当前地）的角色 → 位置=事件地点、activity=事件摘要
        （在场亲历的事实更新；不在场的角色位置不强制更新，保持"行踪未明"由小报带过）
    dies_on <= 当前年月 → alive=False（历史人物按点退场）。
    玩家移动后（location != prev_location）：旧地点已登记角色（未在本拍到点事件在场）
    置 location="行踪未明"——"离场生命周期"：见过的人离开当前地后不再算在场。
    """
    y = int((new_wd or {}).get("year", 0) or 0)
    m = int((new_wd or {}).get("month", 1) or 1)
    for e in (due_events or []):
        ev_locs = [str(x) for x in (e.get("locations") or [])]
        in_place = bool(location) and any(l in location or location in l for l in ev_locs)
        if not in_place:
            continue  # 事件不在玩家所在地 → 角色动向你只在简报得知，不强制更新位置
        for npc in (e.get("key_npcs") or []):
            st = ensure_character(state, npc)
            if ev_locs:
                st["location"] = ev_locs[0]
            st["activity"] = str(e.get("event", ""))[:40]
            st["last_seen"] = f"{y}-{m:02d}"
            st["seen_at"] = location
            st["known"] = True  # 在场亲历 = 玩家认识了
            # 同步关系网「已相遇」：玩家在场亲历 = 遇到，关系网应显示（即使 LLM 未给 first_impression）
            _enc = state.setdefault("encountered", [])
            if npc not in _enc:
                _enc.append(npc)
    # 历史人物按点退场
    for n, st in (state.get("character_states") or {}).items():
        dies = st.get("dies_on")
        if not dies or not st.get("alive"):
            continue
        dy, dm = dies, 1
        if isinstance(dies, str) and "-" in dies:
            try:
                dy, dm = int(dies.split("-")[0]), int(dies.split("-")[1])
            except (ValueError, IndexError):
                continue
        if (y, m) >= (dy, dm):
            st["alive"] = False
    # 离场生命周期：玩家移动到新地点后，旧地点的已登记角色（本拍到点事件在场者除外）置"行踪未明"
    if location and prev_location and location != prev_location:
        # 本拍在场亲历事件的主角（保持位置）
        in_place_now = set()
        for e in (due_events or []):
            ev_locs = [str(x) for x in (e.get("locations") or [])]
            if any(l in location or location in l for l in ev_locs):
                in_place_now.update(e.get("key_npcs") or [])
        for n, st in (state.get("character_states") or {}).items():
            cl = (st or {}).get("location", "")
            # 位置匹配旧地点 且 不在本拍在场名单 → 离开
            if cl and (cl in prev_location or prev_location in cl) and n not in in_place_now:
                st["location"] = "行踪未明"


def merge_character_soft_state(state: dict, updates: dict) -> None:
    """LLM 软状态落地（决策 9：LLM 管软状态）。

    updates = {角色名: {"doing", "goal", "attitude_delta", "tags_add", "notes_add"}}
    - 只覆盖 SOFT_FIELDS；FACT_FIELDS（location/alive/dies_on/last_seen/seen_at/known）LLM 不可写
    - LLM 协议字段是 doing，落地统一键 activity（前端/注入读 activity）
    - attitude_delta 钳位 0-100
    - tags/notes 去重上限（tags ≤4 / notes ≤3）
    """
    states = state.get("character_states")
    if states is None:
        states = {}
        state["character_states"] = states
    # 泛型/即兴 NPC 过滤：LLM 常即兴创建"胖妇人/瘸腿老头/茶棚掌柜"这类场景背景角色，
    # 若全部 ensure_character 登记会永久污染在场面板（且无地点关联，离场逻辑清不掉）。
    # 规则：GENERIC_NAMES（明确泛型）→ 跳过；陌生名字（未登记且非 KNOWN）→ 跳过；
    # 只接受已登记角色或知名角色的软状态更新（决策 14：只维护玩家接触过的角色）。
    from .writer import GENERIC_NAMES, KNOWN_NAMES
    for name, up in (updates or {}).items():
        if not isinstance(up, dict):
            continue
        if name in GENERIC_NAMES:
            continue  # 明确泛型（老者/乡绅/管家…）
        if name not in states and name not in KNOWN_NAMES:
            continue  # 陌生即兴 NPC（胖妇人/瘸腿老头…）不登记，避免污染在场面板
        st = ensure_character(state, name)
        if "doing" in up and isinstance(up["doing"], str):
            st["activity"] = up["doing"][:40]  # doing → activity（统一键，勿双轨）
        if "goal" in up and isinstance(up["goal"], str):
            st["goal"] = up["goal"][:40]
        d = up.get("attitude_delta")
        if isinstance(d, (int, float)) and not isinstance(d, bool):
            st["attitude"] = max(0, min(100, int(st.get("attitude", 50)) + int(d)))
        for tag in up.get("tags_add") or []:
            if isinstance(tag, str) and tag not in st["tags"]:
                st["tags"].append(tag[:20])
        st["tags"] = st["tags"][:4]
        for note in up.get("notes_add") or []:
            if isinstance(note, str) and note not in st["notes"]:
                st["notes"].append(note[:60])
        st["notes"] = st["notes"][:3]
    # 清理历史脏数据：登记了但"无地点关联 + 非知名角色"的即兴 NPC（旧存档的胖妇人/瘸腿老头等）
    # → 移除出 character_states（不再污染在场面板；玩家真正互动过的知名角色不受影响）
    _junk = [n for n, st in states.items()
             if n not in KNOWN_NAMES and n not in GENERIC_NAMES
             and not (st or {}).get("location") and not (st or {}).get("known")]
    for n in _junk:
        states.pop(n, None)
