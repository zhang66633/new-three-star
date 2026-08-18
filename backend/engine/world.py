# -*- coding: utf-8 -*-
"""
World（世界推进 · 自由沙盒）
============================
职责：世界日期推进 + 事件队列生成 + 简报合成。由 graph._commit 每拍调用。

设计（见 docs/自由沙盒重构设计.md §一/§二/§三）：
- 世界时间 = 具体日期 {year, month, day}，按行动类型耗时推进
- 世界事件 = 事实层（world_events），玩家移动/周期时预生成，相关度分级衰减
- 简报 = 玩家到达新地点/重进时，由事件队列合成
"""
import random
import re

# 行动类型 → 耗时（天）。0.5=半天，1=一天，>1=多天（赶路按距离）
ACTION_COST = {
    "talk": 0.5,       # 对话/打听/观察
    "errand": 1,       # 办事/买卖/打探
    "rest": 1,         # 休息（可自定义天数）
    "travel": 2,       # 赶路（邻近；跨州由调用方加权）
    "wait": 1,         # 等待
}
_DAYS_IN_MONTH = 30   # 简化：每月 30 天（历史游戏无需精确日历）
_MONTHS = 12


def advance_date(world_date: dict, days: float) -> dict:
    """按天数推进世界日期，返回新日期。days 支持小数（半天=0.5）。

    半天行动也累积：day 存小数余量，跨月进位用整数判断，显示保留小数
    （如 1.5 天 = 1 天半，前端可显示"午后"）。
    """
    d = dict(world_date or {"year": 184, "month": 2, "day": 1})
    y, m = int(d.get("year", 184)), int(d.get("month", 2))
    day = float(d.get("day", 1))
    total = day + days
    while total > _DAYS_IN_MONTH:
        total -= _DAYS_IN_MONTH
        m += 1
        if m > _MONTHS:
            m = 1
            y += 1
    # 注：无倒退借位循环——days≥0 且 day≥1，total<1 永不合法出现；旧版借位循环会把
    # 刚进位的半天小数（如 30.5→进位后 total=0.5）又借回上月，产生不可能日期（day 30.5）。
    # 进位后 total ∈ (0, 30]，新月第 0.5 天表示"进新月后半天"。
    d["year"], d["month"], d["day"] = y, m, round(total, 1)
    return d


def action_days(action: str, plan_options: list = None, location: str = "") -> float:
    """玩家行动 → 耗时（天）。

    优先读选项声明的 cost_days；否则按行动文本关键词判断类型。
    赶路（travel）按距离加权：跨州默认 3 天，邻近 1-2 天。
    """
    # 1. 选项显式声明 cost_days（registry options/prep 可加）
    if plan_options:
        for opt in plan_options:
            if opt.get("text") and opt["text"] in (action or ""):
                cd = opt.get("cost_days")
                if cd:
                    try:
                        return float(cd)
                    except (TypeError, ValueError):
                        pass
    # 2. 关键词判断（优先级：休息/打听 > 赶路 > 买卖，避免"去洛阳打听"被误判为赶路）
    if not action:
        return 0.0  # 开局无行动
    a = action or ""
    if any(k in a for k in ("休息", "睡", "歇", "休整", "养伤", "躺")):
        # 休息天数可自定义（B-④ §1.2）：「休息N天」→ N 天（1-30），默认 1 天
        m = re.search(r"(\d+)\s*天", a)
        if m:
            return float(max(1, min(int(m.group(1)), 30)))
        return ACTION_COST["rest"]
    if any(k in a for k in ("打听", "问问", "交谈", "观察", "看看", "围观", "闲聊", "问问路")):
        return ACTION_COST["talk"]
    if any(k in a for k in ("赶路", "前往", "离开", "南下", "北上", "去往", "去", "动身", "出发", "回到", "返回", "回")):
        # 赶路耗时=距离（B-③ §1.2）：邻近约 1 天，隔站递增（2 站 2.5 / 3 站 4 / 4 站 5.5）
        from .worlddata import LOCATIONS
        names = list(LOCATIONS.keys())
        # 目标地点 = 方向词（去/往/到/赴/奔/进/入/回/返）后紧跟的地点名
        target = next((n for n in names if re.search(r"(?:去|往|到|赴|奔|进|入|回|返)" + n, a)), "")
        # 起点 = 当前所在（era.location，如 "颍川·荒野" → "颍川"）
        cur = next((n for n in names if n and (location or "") and n in location), None)
        ti = names.index(target) if target in names else -1
        ci = names.index(cur) if cur in names else -1
        if ti >= 0 and ci >= 0:
            dist = abs(ti - ci)
            if dist == 0:
                return 0.5                    # 同地移动（城内/近郊转）
            if dist == 1:
                return 1.0                    # 邻近地点：约 1 天
            return 1.0 + 2.5 * (dist - 1)     # 隔站：2 站 3.5 / 3 站 6.0 / 4 站 8.5（提速世界节奏）
        # 无明确目标地点：跨州词 → 长途；否则默认 1 天（回访/城内移动，防"回头"误判）
        if any(k in a for k in ("跨州", "远行", "长途", "数日")):
            return 8.0
        return 1.0
    # 买卖/办事（在赶路之后：含"前往X买/办事"的复合动作先按赶路距离计时，防距离经济被旁路）
    if any(k in a for k in ("买", "卖", "买卖", "交易", "办事", "赶集")):
        return ACTION_COST["errand"]
    return ACTION_COST["errand"]  # 默认 1 天


def _days_between(d1: dict, d2: dict) -> int:
    """两个日期相隔的天数（近似，用于判断移动是否触发事件）。"""
    y1, m1 = int(d1.get("year", 0)), int(d1.get("month", 1))
    y2, m2 = int(d2.get("year", 0)), int(d2.get("month", 1))
    return (y2 - y1) * 365 + (m2 - m1) * _DAYS_IN_MONTH


def should_generate_events(state: dict, result: dict) -> bool:
    """判断本拍是否触发事件生成：长跨度移动 或 驻留周期。

    移动（§3.1 时间跨度门槛）：日期跨度达阈值（>7 天，跨地点/长行程）才生成；
    同地点内短距离移动（邻近直达，几 天内）不生成世界事件。
    周期：scene_turns 每 4 拍生成一次世界动态。
    """
    old_pos = state.get("skeleton_pos")
    new_pos = result.get("skeleton_pos", old_pos)
    moved = False
    if new_pos != old_pos:
        # 日期跨度门槛：短距离移动（<7 天）不生成（直达）
        old_wd = state.get("world_date") or {}
        new_wd = result.get("world_date") or old_wd
        if _days_between(old_wd, new_wd) >= 7:
            moved = True
    # 驻留周期：scene_turns 每 4 拍生成一次世界动态
    scene_turns = int(result.get("scene_turns", 1) or 1)
    periodic = scene_turns > 0 and scene_turns % 4 == 0
    return moved or periodic


def generate_events(state: dict, world_date: dict, moved: bool, location: str = "") -> list[dict]:
    """生成世界事件（预生成，结果写死）。时间线锚点 + 本地点日常生态。

    自由沙盒设计 §二.1：离开时预生成结构化事件。从 history_timeline 取
    当前日期附近历史事件 + 按地点取世界常态的 daily_scenes 日常。
    """
    from .worlddata import events_around, load_normal, phase_of
    events = []
    # 1. 时间线锚点事件（历史大势）
    recent = events_around(world_date, days_before=1)
    for e in recent:
        if e.get("date"):
            ev = {
                "event_id": e.get("event_id", ""),
                "date": e.get("date", ""),
                "event": e.get("event", "")[:80],
                "related_to_player": "weak",
                "seen": False,
                "source": "timeline",
            }
            # 相关度：涉及玩家认识的人（relations 非空）→ strong
            npcs = e.get("key_npcs", [])
            rels = set(state.get("relations", {}).keys())
            if any(n in rels for n in npcs):
                ev["related_to_player"] = "strong"
            events.append(ev)
    # 2. 本地点日常生态（world_normal 该地点 daily_scenes 抽一条，去哪演哪的活世界）
    if location:
        idx = phase_of(world_date)
        normal = load_normal(idx)
        for loc in (normal.get("locations") or []):
            ln = loc.get("name") or ""
            if ln and (ln == location or (location and ln in location)):
                scenes = loc.get("daily_scenes") or []
                if scenes:
                    s = random.choice(scenes)
                    events.append({
                        "event_id": f"loc_{idx}_{random.randint(1000, 9999)}",
                        "date": f"{world_date.get('year', 0)}-{world_date.get('month', 1):02d}",
                        "event": f"【{ln}】{str(s)[:56]}",
                        "related_to_player": "weak",
                        "seen": False,
                        "source": "daily",
                    })
                break
    return events


def freshen_events(events: list, world_date: dict, max_age_months: int = 6) -> list:
    """事件相关度衰减（B-①，§3.1）：strong（与你有关）事件随日期推移淡出。

    距今 >6 月 → 降为 weak，不再持续刷"与你有关"高亮（旧事已成过往，新事才相关）。
    返回新列表（不改原事件）。
    """
    from .worlddata import _ym
    y = int(world_date.get("year", 0) or 0)
    m = int(world_date.get("month", 1) or 1)
    out = []
    for e in events or []:
        e = dict(e)
        if e.get("related_to_player") == "strong" and e.get("date"):
            ey, em = _ym(str(e.get("date")))
            if (ey, em) != (0, 0):
                age = (y - ey) * 12 + (m - em)
                if age > max_age_months:
                    e["related_to_player"] = "weak"
                    e["decayed"] = True
        out.append(e)
    return out


def period_events(prev_wd: dict, cur_wd: dict) -> list[dict]:
    """离开期间简报（B-⑩）：休息/赶路跨越大段时间 → 取 (prev, cur] 期间的时间线事件。

    生成 weak 事件（世界照常转，与你关系弱），source='period'——玩家醒来/落地后简报天下事。
    """
    from .worlddata import load_timeline, _ym
    py, pm = int(prev_wd.get("year", 0) or 0), int(prev_wd.get("month", 1) or 1)
    cy, cm = int(cur_wd.get("year", 0) or 0), int(cur_wd.get("month", 1) or 1)
    out = []
    for e in load_timeline():
        ey, em = _ym(e.get("date", ""))
        if (py, pm) < (ey, em) <= (cy, cm):
            out.append({
                "event_id": e.get("event_id", f"period_{ey}_{em}"),
                "date": e.get("date", ""),
                "event": str(e.get("event", ""))[:80],
                "related_to_player": "weak",
                "seen": False,
                "source": "period",
            })
    return out


def season_month(season: str) -> int | None:
    """季节 → 代表月（春3/夏6/秋9/冬12）。时代快进/场景预告时对齐 world_date 月份，
    防"189-02 仍判 P1"或"季节秋配 2 月"的矛盾。"""
    return {"春": 3, "夏": 6, "秋": 9, "冬": 12}.get(season)


def season_of(month: int) -> str:
    """月份 → 季节（自由大世界：era.season 由 world_date 派生，取代 registry 静态季）。

    按农历/历史纪月理解（world_date 的月份 = 历史月，如黄巾起义 184年二月=初春）：
    2/3/4 → 春、5/6/7 → 夏、8/9/10 → 秋、11/12/1 → 冬。
    （开局 184-02 显示'春'，与 P1 设计'184年春雨夜醒来'一致。）
    """
    if month in (2, 3, 4):
        return "春"
    if month in (5, 6, 7):
        return "夏"
    if month in (8, 9, 10):
        return "秋"
    return "冬"


def due_events(prev_wd: dict, cur_wd: dict, location: str = "") -> list[dict]:
    """到点历史事件（自由大世界 §事件触发）：(prev, cur] 月窗内到点的时间线事件。

    玩家在事件 locations 内（含当前地点）→ related_to_player='strong' + witnessable=True
    + interaction_types（首次接线 history_timeline 的 player_interactions 五类互动）；
    不在 → 'weak'（世界公告/小报得知）。source='timeline'。
    这是"历史事件到点自动触发"的唯一入口（取代 _commit 里散落的事件生成）。
    """
    from .worlddata import load_timeline, _ym
    py, pm = int(prev_wd.get("year", 0) or 0), int(prev_wd.get("month", 1) or 1)
    cy, cm = int(cur_wd.get("year", 0) or 0), int(cur_wd.get("month", 1) or 1)
    out = []
    for e in load_timeline():
        ey, em = _ym(e.get("date", ""))
        # 到点判定：事件月已到（≤ 当前月）且不早于上一拍月。同月移动（08→08）也触发当月事件
        # ——玩家进入事件地点时应看到"正在发生"的事（防"人在洛阳却看不到董卓进京"）。
        # 纯驻留（prev==cur 同月）会重复返回当月事件，由调用方按 event_id 去重。
        if not ((py, pm) <= (ey, em) <= (cy, cm)):
            continue
        ev_locs = [str(x) for x in (e.get("locations") or [])]
        in_place = bool(location) and any(l in (location or "") or (location in l) for l in ev_locs)
        # 在场判定：玩家当前地点与事件地点重叠 → 可亲历（witnessable + 五类互动模板）
        interactions = (e.get("player_interactions") or [])
        ev = {
            "event_id": e.get("event_id", f"due_{ey}_{em}"),
            "date": e.get("date", ""),
            "event": str(e.get("event", ""))[:80],
            "locations": ev_locs,
            "key_npcs": list(e.get("key_npcs") or []),
            "related_to_player": "strong" if in_place else "weak",
            "witnessable": bool(in_place),
            "interaction_types": [i.get("type") for i in interactions if isinstance(i, dict) and i.get("type")][:5],
            "player_interactions": interactions[:3],  # 在场亲历时 writer 可用的互动模板
            "seen": False,
            "source": "timeline",
        }
        out.append(ev)
    return out


def advance_world(state: dict, action: str, result: dict) -> dict:
    """世界推进（自由大世界 · 世界自主运转的核心）。

    由 graph._commit 调用，返回世界侧增量 dict（不碰玩家数据/成就）：
      {world_date, world_events, new_briefing, era, scene_turns}
    内部顺序：advance_date（按行动耗时）→ due_events（(旧,新] 到点事件）
            → next_timeline_skip（空闲休息且距下事件 >12 月 → 跳时，跳时窗补 due_events）
            → 阶段切换（era.chapter/season 由 phase_of/season_of 派生）
            → 周期事件（scene_turns 每 4 拍）→ freshen_events 衰减。
    """
    from .worlddata import phase_of, match_location, chapter_of
    # 1. 移动解析：玩家「前往X」→ 目标地点（决定到达后在场判定与 era.location 写回）
    #    非地点动作 → 目标 = 当前地点（驻留，loc 不变）
    # cur_loc 优先读 result（图执行后，含 director 跳转前移写回的新位置），再 fallback state——
    # 否则 force 跳转当拍 result.player 已是冀州，却按旧 state 的颍川算 target，又把 era.location 覆盖回颍川
    cur_loc = ((result.get("player") or {}).get("location", "")
               or (state.get("player") or {}).get("location", "")
               or (result.get("era") or {}).get("location", "") or "颍川")
    target = match_location(action) or cur_loc
    # 1.5 推进日期（按行动类型耗时；location 供赶路距离解析）
    days = action_days(action, [], cur_loc)
    wd = result.get("world_date") or state.get("world_date") or {"year": 184, "month": 2, "day": 1}
    new_wd = advance_date(wd, days)
    world_events = list(result.get("world_events") or state.get("world_events") or [])
    new_briefing = False
    # 玩家位置写回（前往X 到达目标地点；era.location 同步供 view_scene/due_events 使用）
    loc = target
    era = dict(result.get("era") or state.get("era") or {})
    era["location"] = loc
    # 2. 到点事件（(旧,新] 月窗）：在场 strong+witnessable / 不在 weak
    due = due_events(wd, new_wd, loc)
    all_due = list(due)  # 供角色事实更新/简报（含跳时窗补）
    seen_ids = {e.get("event_id") for e in world_events}
    for ev in due:
        if ev.get("event_id") not in seen_ids:
            world_events.append(ev)
            seen_ids.add(ev.get("event_id"))
            # 简报降频（与玩家有关才打断）：仅在场强相关事件弹窗；弱相关远方小报只进天下事列表积累
            if ev.get("related_to_player") == "strong":
                new_briefing = True
        elif ev.get("related_to_player") == "strong":
            # 就地升级：事件此前以 weak 入队（如颍川首见），玩家现在亲临现场 → 升级为 strong
            # + 触发简报（修复"人在洛阳却看不到董卓进京"——event_id 去重不再吞掉强相关）
            for _old in world_events:
                if _old.get("event_id") == ev.get("event_id") and _old.get("related_to_player") != "strong":
                    _old["related_to_player"] = "strong"
                    _old["witnessable"] = True
                    _old["interaction_types"] = ev.get("interaction_types", [])
                    _old["player_interactions"] = ev.get("player_interactions", [])
                    new_briefing = True
                    break
    # 3. 历史压缩：驻留空闲且距下一事件 >4 月 → 跳时（带过平淡期，跳时窗补 due_events）
    #    快速跳转（"静观其变/等待时机/静候"等）→ 无视间隔强制跳到下一事件
    if is_idle_action(action):
        _force = any(k in (action or "") for k in ("静观其变", "等待时机", "静候", "按兵不动", "静待"))
        # 已由 director 预判跳转（_skip_done）→ 本拍不再重复跳（否则连续跳两事件）
        _skip_done = bool((result.get("meta") or {}).get("_skip_done"))
        skip = None if _skip_done else next_timeline_skip(new_wd, force=_force)
        if skip:
            old_wd = dict(new_wd)
            new_wd = skip["date"]
            _timeskip_gap = (new_wd.get("year", 0) - old_wd.get("year", 0)) * 12 + (new_wd.get("month", 1) - old_wd.get("month", 1))
            _timeskip_note = f"时间跳跃 {max(_timeskip_gap, 1)} 个月"  # P0-4: 供 writer 感知跳转
            # P0-2 修复：快速跳转时同步玩家位置到目标事件主地点——
            # 否则只改日期不改 location，标题到 189 洛阳但正文还在颍川演 184（日期/位置脱节）
            if _force and skip.get("location"):
                loc = skip["location"]
                era["location"] = loc
                if isinstance(result.get("player"), dict):
                    result["player"]["location"] = loc
            # 跳时自身作为一条"时间如水"事件入队（玩家能在天下事看到"一晃过去 N 个月"），
            # 跳时窗内到点事件统一由 due_events 吸收（不重复 timeskip 事件）
            if skip.get("event") and skip["event"].get("event_id") not in seen_ids:
                world_events.append(skip["event"])
                seen_ids.add(skip["event"]["event_id"])
                new_briefing = True
            for ev in due_events(old_wd, new_wd, loc):
                all_due.append(ev)
                if ev.get("event_id") not in seen_ids:
                    world_events.append(ev)
                    seen_ids.add(ev.get("event_id"))
                    new_briefing = True
    # 4. 篇章/阶段切换（era.chapter 由 8 篇章 chapter_of 派生；season 由 world_date 派生）
    idx = phase_of(new_wd)
    if phase_of(wd) != idx:
        new_briefing = True   # 跨时代 → 简报（世界翻篇，值得一报）
    era["chapter"] = chapter_of(new_wd)["label"]
    era["year"] = int(new_wd.get("year", 0) or 0)
    era["season"] = season_of(int(new_wd.get("month", 1) or 1))
    # 5. 周期事件（驻留每 4 拍 或 时间跨 7 天 生成一次世界动态——保留 generate_events 的日常生态分支）
    #    驻留轮次自增：换地点重置 1、驻留每拍 +1（此前恒为 1 从未自增，%4 永假，活世界机制失效）
    scene_turns = int(result.get("scene_turns") or state.get("scene_turns") or 1)
    same_place = bool(target) and bool(cur_loc) and (target in cur_loc or cur_loc in target)
    scene_turns = 1 if not same_place else scene_turns + 1
    # 时间间隔触发：跨 7 天（如休息N天/长途赶路）也补一条日常，让"歇着世界也转"成立
    # 跨年修复：用 year*12+month 的月差计算（旧版只比 month，12月→1月跨年会算出 -11*30 负数）
    _month_delta = (int(new_wd.get("year") or 1) - int(wd.get("year") or 1)) * 12 + (int(new_wd.get("month") or 1) - int(wd.get("month") or 1))
    _day_delta = _month_delta * 30 + (int(new_wd.get("day") or 1) - int(wd.get("day") or 1))
    if (scene_turns > 0 and scene_turns % 4 == 0) or _day_delta >= 7:
        daily = generate_events(state, new_wd, False, loc)
        for ev in daily:
            if ev.get("event_id") not in seen_ids:
                world_events.append(ev)
                seen_ids.add(ev.get("event_id"))
                # 周期动态为弱相关日常 → 不弹简报（只进天下事）
    # 6. 事件相关度衰减
    if world_events:
        world_events = freshen_events(world_events, new_wd)
    return {
        "world_date": new_wd,
        "world_events": world_events[-50:],
        "new_briefing": new_briefing,
        "era": era,
        "scene_turns": scene_turns,
        "timeskip_note": _timeskip_note if skip else "",  # P0-4: 跳转标记（writer 感知）——自动跳时（gap>4月）也要返回，否则 writer 无感知
        "due_events": all_due,
    }


def is_idle_action(action: str) -> bool:
    """判断玩家本拍是否"驻留空闲"（休息/等待/无所事事）→ 允许历史跳时。

    A1 历史压缩门控：主动行动（对话/打听/赶路/买卖等）不跳时，避免打断进行中的互动；
    只有持续休息/等待才让世界大步向前（"玩家歇着，天下照转"）。
    """
    a = (action or "").strip()
    if not a:
        return False  # 开局首拍无行动，不跳
    IDLE_KW = ("休息", "睡", "歇", "休整", "养伤", "躺", "等待", "等等", "无所事事", "发呆", "闲逛",
               "静观其变", "等待时机", "按兵不动", "养精蓄锐", "静待时局", "静候")
    return any(k in a for k in IDLE_KW)


def next_timeline_skip(world_date: dict, force: bool = False) -> dict | None:
    """历史压缩（§1.3）：若距下一时间线事件过远（>4 个月）→ 自动跳时。

    force=True（快速跳转按钮触发）：无视间隔门槛，直接跳到下一时间线事件
    （玩家"静观其变/等待时机"→ 世界大步向前到下一件大事）。
    返回 {"date": 目标日期, "event": 简报事件} 或 None（无下一事件）。
    """
    from .worlddata import load_timeline, _ym
    y = int(world_date.get("year", 0) or 0)
    m = int(world_date.get("month", 1) or 1)
    nxt = None
    for e in load_timeline():
        ey, em = _ym(e.get("date", ""))
        if (ey, em) > (y, m):
            nxt = e
            break
    if not nxt:
        return None
    ny, nm = _ym(nxt.get("date", ""))
    gap = (ny - y) * 12 + (nm - m)
    if gap <= 4 and not force:
        return None  # 间隔小（≤4 个月），不跳时（保留当前事件密集期的体验）；快速跳转不受限
    return {
        "date": {"year": ny, "month": nm, "day": 1},
        "location": (nxt.get("locations") or [""])[0],  # P0-2：目标事件主地点（供跳转同步位置）
        "event": {
            "event_id": f"timeskip_{ny}_{nm}",
            "date": f"{ny:03d}-{nm:02d}",
            "event": f"时间如水：一晃过去 {gap} 个月。{str(nxt.get('event', ''))[:60]}",
            "related_to_player": "weak",
            "seen": False,
            "source": "timeskip",
        },
    }
