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
            return 1.0 + 1.5 * (dist - 1)     # 隔站：2 站 2.5 / 3 站 4.0 / 4 站 5.5
        # 无明确目标地点：跨州词 → 长途；否则默认 1 天（回访/城内移动，防"回头"误判）
        if any(k in a for k in ("跨州", "远行", "长途", "数日")):
            return 5.0
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


def is_idle_action(action: str) -> bool:
    """判断玩家本拍是否"驻留空闲"（休息/等待/无所事事）→ 允许历史跳时。

    A1 历史压缩门控：主动行动（对话/打听/赶路/买卖等）不跳时，避免打断进行中的互动；
    只有持续休息/等待才让世界大步向前（"玩家歇着，天下照转"）。
    """
    a = (action or "").strip()
    if not a:
        return False  # 开局首拍无行动，不跳
    IDLE_KW = ("休息", "睡", "歇", "休整", "养伤", "躺", "等待", "等等", "无所事事", "发呆", "闲逛")
    return any(k in a for k in IDLE_KW)


def next_timeline_skip(world_date: dict) -> dict | None:
    """历史压缩（§1.3）：若距下一时间线事件过远（>12 个月）→ 自动跳时。

    返回 {"date": 目标日期, "event": 简报事件} 或 None（间隔小不跳）。
    玩家驻留日常时世界大步向前，跳时以简报带过（"几年过去，谁干成了什么"）。
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
    if gap <= 12:
        return None  # 间隔小（≤1 年），不跳时（保留当前事件密集期的体验）
    return {
        "date": {"year": ny, "month": nm, "day": 1},
        "event": {
            "event_id": f"timeskip_{ny}_{nm}",
            "date": f"{ny:03d}-{nm:02d}",
            "event": f"时间如水：一晃过去 {gap} 个月。{str(nxt.get('event', ''))[:60]}",
            "related_to_player": "weak",
            "seen": False,
            "source": "timeskip",
        },
    }
