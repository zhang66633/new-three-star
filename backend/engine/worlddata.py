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

# 阶段定义：按产出文件顺序（黄巾乱起 → 天下三分）
PHASES = [
    {"idx": 1, "name": "黄巾乱起", "start": "184-02", "end": "188-12"},
    {"idx": 2, "name": "董卓乱政", "start": "189-01", "end": "190-12"},
    {"idx": 3, "name": "群雄割据", "start": "191-01", "end": "199-12"},
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
        if loc.get("name") == location or (location and location in (loc.get("name") or "")):
            loc_normal = loc
            break
    return {
        "phase_name": normal.get("phase", ""),
        "phase_idx": idx,
        "normal": normal,
        "recent_events": recent,
        "location_normal": loc_normal,
    }
