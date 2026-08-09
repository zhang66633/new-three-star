# -*- coding: utf-8 -*-
"""
Events（事件生成 · 历史时间线驱动）
===================================
职责：从 history_timeline 提取"当前日期附近"的历史大事件，标记与玩家的相关度。
由 world.generate_events 调用，作为世界事件队列的时间线锚点部分。

设计（docs/自由沙盒重构设计.md §二.1）：
- 事件生成时判断相关度：涉及玩家认识的 NPC / 所在地区 / 承诺相关 → strong
- 分级+衰减：强相关逐条展示，弱相关合并，久未互动自然淡化
"""
from .worlddata import events_around, load_timeline


def timeline_events(world_date: dict, state: dict, limit: int = 3) -> list[dict]:
    """当前日期附近的历史锚点事件 → 结构化事件（带相关度标记）。

    相关度判定：
    - 涉及玩家认识的人（relations/trust 非空）→ strong
    - 涉及玩家承诺（foreshadowing 提及）→ strong
    - 否则 weak
    """
    rels = set(state.get("relations", {}).keys())
    trust = set(state.get("trust", {}).keys())
    known = rels | trust
    # 承诺/伏笔中的关键词（人物名粗匹配）
    fs_text = "".join(state.get("foreshadowing", []))

    out = []
    for e in events_around(world_date, days_before=limit):
        npcs = e.get("key_npcs", [])
        rel = "weak"
        if any(n in known for n in npcs):
            rel = "strong"
        if any(n and n in fs_text for n in npcs):
            rel = "strong"
        out.append({
            "event_id": e.get("event_id", ""),
            "date": e.get("date", ""),
            "event": e.get("event", "")[:80],
            "related_to_player": rel,
            "seen": False,
            "source": "timeline",
        })
    return out


def mark_seen(events: list[dict]) -> list[dict]:
    """已展示事件标记 seen（简报去重）。"""
    return [{**e, "seen": True} for e in events]


def unread_events(events: list[dict]) -> list[dict]:
    """筛出未展示的、与玩家强相关的事件（简报重点）。"""
    return [e for e in events if not e.get("seen") and e.get("related_to_player") == "strong"]
