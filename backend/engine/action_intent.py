# -*- coding: utf-8 -*-
"""
玩家自由行动解析（自由大世界 · 决策 5/12）
============================================
parse_action：把玩家自由输入确定性分类 → {type, target, location, cost_days}。
自由大世界里玩家可输入任何话（"跟曹操喝酒""潜入王允府""去洛阳找董卓"），
引擎需要确定性判断"这是赶路/互动/打探/停留/战斗"，驱动世界反应与耗时。

- 赶路：前往X / 去X / 回X（match_location 解析目标地点）
- 互动：提及在场已知角色（KNOWN_NAMES/relations/character_states）→ target=角色名
- 打探：打听/观察/看看/问问/围观
- 停留：休息N天/睡/歇/等待（沿用 action_days 的「休息N天」正则）
- 战斗：单挑/打/杀/偷袭/劫/战（提及角色 → 战斗目标）
- 自由：以上都不是（LLM 现场即兴）
"""
import re

# 动作类型 → 基础耗时（天）（与 world.ACTION_COST 对齐）
TYPE_COST = {
    "打探": 0.5,
    "互动": 0.5,
    "停留": 1.0,
    "战斗": 1.0,
    "自由": 1.0,
}

_REST_RE = re.compile(r"(\d+)\s*天")


def parse_action(action: str, location: str = "", known_names: set = None) -> dict:
    """自由输入 → 结构化意图。确定性规则（不调 LLM）。

    known_names: 在场/已知角色名集合（供互动/战斗目标匹配）。
    返回 {type, target, location, cost_days, raw}。
    """
    a = (action or "").strip()
    known = known_names or set()
    out = {"type": "自由", "target": None, "location": None, "cost_days": TYPE_COST["自由"], "raw": a}
    if not a:
        return out

    # 1. 赶路：前往/去/回 + 已知地点（最高优先，含"去洛阳找董卓"复合）
    from .worlddata import match_location
    loc = match_location(a)
    if loc:
        out["type"] = "赶路"
        out["location"] = loc
        # 赶路耗时=距离（action_days 已有公式；这里给 1 天基准，world.action_days 会按距离加权）
        out["cost_days"] = None  # None → world.action_days 按距离算
        # 复合动作："去洛阳找董卓" → 目标角色也解析（抵达后互动）
        for n in known:
            if n and n in a:
                out["target"] = n
        return out

    # 2. 停留：休息N天/睡/歇/等待（"休息10天" → 10 天）
    if any(k in a for k in ("休息", "睡", "歇", "休整", "养伤", "躺", "等待", "等等", "发呆")):
        m = _REST_RE.search(a)
        out["type"] = "停留"
        out["cost_days"] = float(max(1, min(int(m.group(1)), 30))) if m else TYPE_COST["停留"]
        return out

    # 3. 战斗：提及角色 + 攻击性动词 → 战斗（目标角色）
    combat_kw = ("单挑", "砍", "杀", "偷袭", "劫", "抢", "战", "打", "踹", "揍", "放倒")
    if any(k in a for k in combat_kw):
        target = next((n for n in known if n in a), None)
        if target:
            out["type"] = "战斗"
            out["target"] = target
            out["cost_days"] = TYPE_COST["战斗"]
            return out

    # 4. 明确互动：跟/找/见/陪/问 + 角色 → 互动（社交性动词优先）
    soc_kw = ("跟", "找", "见", "陪", "问", "约", "请")
    target = next((n for n in known if n in a), None)
    if target and any(k in a for k in soc_kw) and not any(k in a for k in ("杀", "砍", "偷袭", "单挑")):
        out["type"] = "互动"
        out["target"] = target
        out["cost_days"] = TYPE_COST["互动"]
        return out

    # 5. 打探：打听/观察/潜入/看看/问问/围观（含角色目标也归打探，如"潜入王允府"）
    if any(k in a for k in ("打听", "问问", "观察", "看看", "围观", "打探", "了解", "探听", "潜入", "探查", "跟踪")):
        out["type"] = "打探"
        out["target"] = target  # 有角色目标则带（如潜入王允府 → 王允）
        out["cost_days"] = TYPE_COST["打探"]
        return out

    # 6. 互动兜底：提及在场角色（无明确动词 → 默认互动）
    if target:
        out["type"] = "互动"
        out["target"] = target
        out["cost_days"] = TYPE_COST["互动"]
        return out

    # 6. 自由：其他（LLM 现场即兴）
    out["cost_days"] = TYPE_COST["自由"]
    return out
