# -*- coding: utf-8 -*-
"""
WorldData（世界数据层 · 时间线 + 常态设定）
==========================================
加载历史事件时间线（history_timeline_*.json）+ 世界常态设定（world_normal_*.json），
提供：
  1. `phase_of(world_date)`    —— 按玩家当前日期判断所处阶段
  2. `normal_for(phase_idx)`   —— 取某阶段的常态设定（五维）
  3. `events_around(date)`     —— 按日期取事件（用于简报/场景注入）
  4. `world_context(world_date, location)` —— 综合常态+近期事件，供 writer 注入

数据源（另 AI 产出）：
  backend/knowledge/history_timeline/history_timeline_{1..4}.json
  backend/knowledge/world_normal/world_normal_{1..6}.json
"""
import json
import os

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge")

# 阶段定义：按产出文件顺序（黄金乱起 → 天下三分）
# 边界对齐时间线事件语义点（B-⑤）：
#   P1 到 189-07（黄金军+余波/前夜，无空窗）→ P2 189-08 = 董卓进京事件起
#   P2 到 192-03（董卓乱政全程）→ P3 192-04 = 董卓伏诛事件起（群雄割据真正开始）
# 边界连续（前一阶段 end 的次月 = 后一阶段 start），phase_of 无空窗。
PHASES = [
    {"idx": 1, "name": "黄金乱起", "start": "184-02", "end": "189-07"},
    {"idx": 2, "name": "董卓乱政", "start": "189-08", "end": "192-03"},
    {"idx": 3, "name": "群雄割据", "start": "192-04", "end": "199-12"},
    {"idx": 4, "name": "官渡定鼎", "start": "200-01", "end": "207-12"},
    {"idx": 5, "name": "赤壁三足", "start": "208-01", "end": "219-12"},
    {"idx": 6, "name": "天下三分", "start": "220-01", "end": "230-12"},
]


def _ym(date_key: str) -> tuple:
    """'184-02' → (184, 2)；容错非标准格式"""
    try:
        y, m = str(date_key).split("-")[:2]
        return int(y), int(m)
    except (ValueError, AttributeError):
        return (0, 0)


# ═════════ 地点导航（自由沙盒 · 见设计 §5.2）═════════
# 地点 → 涉及场景（对齐 registry.json 场景的 location 归属；顺序即解锁次序）
# 回访目标 = 该地点"最后访问过"的场景（记忆中的场景，LLM 圆场时间冲突）
LOCATIONS: dict[str, list[str]] = {
    "颍川": ["P1_s1_rain", "P1_s2_gold"],
    "洛阳": ["P1_s3_leap", "P2_s1_street", "P2_s2_ci"],
    "中牟": ["P2_s3_escape"],
    "成皋": ["P2_s4_slaughter"],
    "陈留": ["P3_s1_alliance"],
}


# 传闻地点（自由沙盒 §5.2）：玩家在 X 地能听到的远方传闻 → 把目标地点点亮为"传闻"态。
# hint = 传闻文本（前端地图显示 + writer 注入让 NPC 顺口带出）；target 未解锁才点亮。
# 打听解锁：玩家「打听X」命中传闻中的地点 → 该地升级为已解锁（可赶路，director.resolve_rumor）。
LOCATION_RUMORS: dict[str, list[dict]] = {
    "颍川": [
        {"target": "洛阳", "hint": "北边传闻，洛阳最近不太平，车马都往城外逃"},
        {"target": "中牟", "hint": "商旅说东边有座中牟县城，城墙低矮，过得去"},
    ],
    "洛阳": [
        {"target": "中牟", "hint": "东边传闻，中牟县城设了关卡，正盘查往来行商"},
        {"target": "成皋", "hint": "过虎牢往东，成皋关城据传屯了重兵"},
    ],
    "中牟": [
        {"target": "陈留", "hint": "县里人传，陈留近来广发帖子，邀各方豪杰赴会"},
    ],
    "成皋": [
        {"target": "陈留", "hint": "往东传闻，陈留将有场大盟会，四方人马正往那赶"},
    ],
    "陈留": [],
}


def match_location(action: str) -> str | None:
    """解析地点动作：「前往/赶路到/动身去/去/回 地点」→ 地点名（未知地点返回 None）。

    只认 LOCATIONS 已知地点名；非地点动作（"去打听消息"等）返回 None。
    解锁/推进判定在 director（有 registry flow），这里只管文本 → 地点名。
    """
    a = (action or "").strip()
    if not a:
        return None
    for kw in ("前往", "赶路到", "动身去", "去", "回"):
        if a.startswith(kw):
            rest = a[len(kw):].strip()
            for name in LOCATIONS:
                if rest.startswith(name):
                    return name
            return None  # 不是已知地点
    return None


def _load_json(path: str, cache: dict, key: str) -> dict:
    """mtime 缓存加载（JSON 文件变了就重读，开发期免重启）"""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return cache.get(key) or {}
    if key not in cache or cache[key].get("_mtime") != mtime:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            cache[key] = {"_mtime": mtime, "data": data}
        except (OSError, json.JSONDecodeError):
            pass
    return (cache.get(key) or {}).get("data") or {}


_timeline_cache: dict = {}
_normal_cache: dict = {}


def load_timeline() -> list[dict]:
    """加载全部时间线事件（按日期排序）"""
    events = []
    for i in range(1, 5):
        path = os.path.join(_DATA_DIR, "history_timeline", f"history_timeline_{i}.json")
        d = _load_json(path, _timeline_cache, f"tl{i}")
        events.extend(d.get("events", []))
    events.sort(key=lambda e: e.get("date", ""))
    return events


def load_normal(phase_idx: int) -> dict:
    """加载某阶段（1-6）的常态设定"""
    if not 1 <= phase_idx <= 6:
        return {}
    path = os.path.join(_DATA_DIR, "world_normal", f"world_normal_{phase_idx}.json")
    return _load_json(path, _normal_cache, f"n{phase_idx}")


def phase_of(world_date: dict) -> int:
    """玩家日期 → 阶段序号（1-6）。缺省回退 1。"""
    y = int(world_date.get("year", 0) or 0)
    m = int(world_date.get("month", 1) or 1)
    key = f"{y:03d}-{m:02d}"
    for p in PHASES:
        if _ym(p["start"]) <= (y, m) <= _ym(p["end"]):
            return p["idx"]
    # 超出阶段范围：最早回退 1，最晚回退 6
    if (y, m) < _ym(PHASES[0]["start"]):
        return 1
    return 6


def events_around(world_date: dict, days_before: int = 0) -> list[dict]:
    """取玩家当前日期附近的近期事件（用于场景注入/简报）。
    时间线只有年月粒度，取"同月或之前最近 N 条"。
    """
    y = int(world_date.get("year", 0) or 0)
    m = int(world_date.get("month", 1) or 1)
    cur = (y, m)
    events = load_timeline()
    near = [e for e in events if _ym(e.get("date", "")) <= cur]
    return near[-days_before:] if days_before > 0 else near[-3:]  # 默认最近 3 条


def world_context(world_date: dict, location: str = "") -> dict:
    """综合：当前阶段常态 + 近期事件 → 供 writer 注入的"当前世界背景"。

    返回 {phase_name, normal(五维), recent_events, location_normal}
    """
    idx = phase_of(world_date)
    normal = load_normal(idx)
    recent = events_around(world_date, days_before=3)
    loc_normal = None
    for loc in (normal.get("locations") or []):
        ln = loc.get("name") or ""
        # era.location 如 "颍川·荒野" → 匹配常态地点 "颍川"（name 作子串匹配）
        if ln and (ln == location or (location and ln in location)):
            loc_normal = loc
            break
    return {
        "phase_name": normal.get("phase", ""),
        "phase_idx": idx,
        "normal": normal,
        "recent_events": recent,
        "location_normal": loc_normal,
    }
