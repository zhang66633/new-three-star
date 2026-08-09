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
    while total < 1:
        total += _DAYS_IN_MONTH
        m -= 1
        if m < 1:
            m = _MONTHS
            y -= 1
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
        return ACTION_COST["rest"]
    if any(k in a for k in ("打听", "问问", "交谈", "观察", "看看", "围观", "闲聊", "问问路")):
        return ACTION_COST["talk"]
    if any(k in a for k in ("买", "卖", "买卖", "交易", "办事", "赶集")):
        return ACTION_COST["errand"]
    if any(k in a for k in ("赶路", "前往", "离开", "南下", "北上", "去往", "动身", "出发")):
        # 赶路：跨州 vs 邻近
        if any(k in a for k in ("跨州", "远行", "长途", "数日")):
            return 5.0
        return 3.0
    return ACTION_COST["errand"]  # 默认 1 天


def _days_between(d1: dict, d2: dict) -> int:
    """两个日期相隔的天数（近似，用于判断移动是否触发事件）。"""
    y1, m1 = int(d1.get("year", 0)), int(d1.get("month", 1))
    y2, m2 = int(d2.get("year", 0)), int(d2.get("month", 1))
    return (y2 - y1) * 365 + (m2 - m1) * _DAYS_IN_MONTH


def should_generate_events(state: dict, result: dict) -> bool:
    """判断本拍是否触发事件生成：移动了 或 驻留达到周期。

    移动：skeleton_pos/location 变化；周期：scene_turns 达阈值（每 4 拍）。
    """
    old_pos = state.get("skeleton_pos")
    new_pos = result.get("skeleton_pos", old_pos)
    moved = new_pos != old_pos
    # 驻留周期：scene_turns 每 4 拍生成一次世界动态
    scene_turns = int(result.get("scene_turns", 1) or 1)
    periodic = scene_turns > 0 and scene_turns % 4 == 0
    return moved or periodic


def generate_events(state: dict, world_date: dict, moved: bool) -> list[dict]:
    """生成世界事件（预生成，结果写死）。当前用时间线锚点 + 随机日常事件。

    自由沙盒设计 §二.1：离开时预生成结构化事件。这里做轻量实现——
    从 history_timeline 取当前日期附近的历史事件作为"世界正在发生的事"。
    """
    from .worlddata import events_around, load_timeline
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
    # 2. 周期日常事件（驻留时世界仍在动）
    if not moved:
        daily = _daily_event(state, world_date)
        if daily:
            events.append(daily)
    return events


def _daily_event(state: dict, world_date: dict) -> dict:
    """随机日常事件（世界"平时"在发生什么，LLM 即兴的底料）。"""
    # 从常态设定抽一个本阶段传闻/日常作为事件
    from .worlddata import world_context, load_normal, phase_of
    idx = phase_of(world_date)
    normal = load_normal(idx)
    atm = normal.get("atmosphere") or {}
    rumors = atm.get("rumors") or []
    if rumors:
        r = random.choice(rumors)
        return {
            "event_id": f"daily_{idx}_{random.randint(1000, 9999)}",
            "date": f"{world_date.get('year', 184):03d}-{world_date.get('month', 1):02d}",
            "event": f"民间传闻：{r}",
            "related_to_player": "weak",
            "seen": False,
            "source": "daily",
        }
    return {}


def compose_briefing(events: list[dict]) -> str:
    """世界事件队列 → 简报文本（LLM 可读/前端展示）。"""
    if not events:
        return ""
    lines = ["—— 你离开的这段时间，天下发生了这些 ——"]
    for e in events[:6]:
        tag = "【与你有关】" if e.get("related_to_player") == "strong" else ""
        lines.append(f"〔{e.get('date', '')}〕{tag}{e.get('event', '')}")
    return "\n".join(lines)


def mark_seen(events: list[dict]) -> list[dict]:
    """简报已展示的事件标记 seen，避免重复弹。"""
    out = []
    for e in events:
        e = dict(e)
        if not e.get("seen"):
            e["seen"] = True
        out.append(e)
    return out
