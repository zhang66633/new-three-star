# -*- coding: utf-8 -*-
"""
PlayerData（玩家档案 · 自由沙盒）
=================================
职责：玩家持久化数据——资产/属性/关系/声誉/成就。
- apply_player_updates：解析 LLM 声明的 player_updates（获得/失去物品、属性变化、新称号）
- check_attributes：行动前属性判定（低值约束）
- check_achievements：行动后成就条件检查解锁

设计（docs/自由沙盒重构设计.md §三）：
- 物品 = 描述字符串列表 + 金钱
- 属性 = {stamina, hunger, wound} 0-100，低值→叙事+行动受限，行动恢复
- 称号 = 事件授予，NPC 凭称号认出/议论
- 成就 = 条件定义 + 行动后自动检查解锁
"""
# 属性下限阈值（低于则行动受限）
_ATTR_LOW = {
    "stamina": 20,   # 体力低于 20：不能赶远路
    "hunger": 80,    # 饥饿高于 80：行动受限（饥饿值，越高越饿）
    "wound": 50,     # 伤势高于 50：不能战斗/赶远路
}
_DEFAULT_STATS = {"stamina": 80, "hunger": 60, "wound": 0}


def _clamp(v, lo=0, hi=100):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return lo


def get_stats(player: dict) -> dict:
    """取玩家属性（容错缺字段）。"""
    st = player.get("stats") or {}
    return {k: _clamp(st.get(k, _DEFAULT_STATS.get(k, 50))) for k in _DEFAULT_STATS}


def apply_player_updates(state: dict, output: dict) -> dict:
    """解析 LLM 声明的 player_updates，应用到玩家数据。

    player_updates 结构（LLM 在 narrative 输出里声明）：
      {
        "assets_add": ["半块干粮"],       # 获得物品
        "assets_remove": ["破布衣"],       # 失去物品
        "coins_delta": 5,                  # 金钱变化（+-）
        "stats_delta": {"stamina": -10, "hunger": +15},  # 属性变化
        "title_add": "乱世见证者",         # 新称号
      }
    返回更新后的 player（经 state 整体写入由调用方做）。
    """
    updates = (output or {}).get("state_updates", {}) or {}
    pu = updates.get("player_updates") or {}
    if not isinstance(pu, dict):
        return state

    player = dict(state.get("player") or {})

    # 物品增减
    assets = list(player.get("assets", []))
    for a in (pu.get("assets_add") or []):
        if a and a not in assets:
            assets.append(str(a)[:100])
    for a in (pu.get("assets_remove") or []):
        if a in assets:
            assets.remove(a)
    player["assets"] = assets[:200]

    # 金钱
    try:
        player["coins"] = max(0, int(player.get("coins", 0)) + int(pu.get("coins_delta", 0)))
    except (TypeError, ValueError):
        pass

    # 属性
    stats = get_stats(player)
    for k, dv in (pu.get("stats_delta") or {}).items():
        if k in _DEFAULT_STATS:
            try:
                stats[k] = _clamp(stats[k] + int(dv))
            except (TypeError, ValueError):
                pass
    player["stats"] = stats

    # 称号
    t = pu.get("title_add")
    if t and t not in player.get("titles", []):
        player["titles"] = list(player.get("titles", [])) + [str(t)[:50]]

    state["player"] = player
    return state


def check_attributes(player: dict, action: str = "") -> dict:
    """行动前属性判定：返回约束信息（低值限制）。

    返回 {blocked: bool, reason: str}——blocked 时不禁止但受限，
    由调用方决定是否给 LLM 注入约束提示。
    """
    stats = get_stats(player)
    reasons = []
    if stats["stamina"] < _ATTR_LOW["stamina"]:
        reasons.append("你体力透支，赶不了远路")
    if stats["hunger"] > _ATTR_LOW["hunger"]:
        reasons.append("你饿得前胸贴后背，动作迟缓")
    if stats["wound"] > _ATTR_LOW["wound"]:
        reasons.append("你伤重未愈，难以战斗或长途跋涉")
    return {"blocked": bool(reasons), "reasons": reasons}


def apply_recovery(player: dict, action: str, world_date: dict) -> dict:
    """行动恢复属性：休息回体力、进食回饥饿（消耗物品）、治伤回伤势。

    返回更新后的 player。
    """
    stats = get_stats(player)
    a = action or ""
    # 休息 → 体力恢复
    if any(k in a for k in ("休息", "睡", "歇", "休整")):
        stats["stamina"] = _clamp(stats["stamina"] + 40)
    # 进食 → 饥饿下降（有食物才有效）
    if any(k in a for k in ("吃", "进食", "觅食", "买吃的")):
        assets = player.get("assets", [])
        food = [x for x in assets if any(f in x for f in ("粮", "食", "饼", "干", "肉", "馒"))]
        if food or player.get("coins", 0) > 0:
            stats["hunger"] = _clamp(stats["hunger"] - 30)
            # 消耗一份食物
            if food:
                assets.remove(food[0])
                player["assets"] = assets
    # 治伤 → 伤势下降
    if any(k in a for k in ("治伤", "疗伤", "看伤", "包扎", "敷药")):
        stats["wound"] = _clamp(stats["wound"] - 40)
    # 日常行动 → 饥饿缓慢上升、体力缓慢下降（世界时间流逝的代价）
    else:
        stats["hunger"] = _clamp(stats["hunger"] + 5)
        stats["stamina"] = _clamp(stats["stamina"] - 3)
    player["stats"] = stats
    return player


# ═════════ 成就系统 ═════════
# 条件定义：action 后检查 state 满足条件即解锁
_ACHIEVEMENTS = {
    "first_step": {
        "name": "迈出第一步",
        "desc": "在乱世中迈出第一步",
        "check": lambda st: st.get("turn", 0) >= 1,
    },
    "survivor": {
        "name": "活下来了",
        "desc": "存活超过 10 个回合",
        "check": lambda st: st.get("turn", 0) >= 10,
    },
    "wealth_100": {
        "name": "小有积蓄",
        "desc": "攒到 100 钱",
        "check": lambda st: (st.get("player") or {}).get("coins", 0) >= 100,
    },
    "witness_huangjin": {
        "name": "亲历黄金军",
        "desc": "目睹/参与黄金军事件",
        "check": lambda st: any("黄金" in (e.get("event", "") or "") for e in st.get("world_events", [])),
    },
    "reputation_30": {
        "name": "小有名声",
        "desc": "声望达到 30",
        "check": lambda st: (st.get("player") or {}).get("reputation", 0) >= 30,
    },
}


def check_achievements(state: dict) -> list[str]:
    """行动后检查所有成就条件，解锁满足的。返回新解锁的成就 id。"""
    player = state.get("player") or {}
    unlocked = set(player.get("achievements", []))
    new = []
    for aid, spec in _ACHIEVEMENTS.items():
        if aid in unlocked:
            continue
        try:
            if spec["check"](state):
                unlocked.add(aid)
                new.append(aid)
        except Exception:
            continue
    if new:
        player["achievements"] = sorted(unlocked)
        state["player"] = player
    return new
