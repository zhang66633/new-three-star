# -*- coding: utf-8 -*-
"""
Director（导演层 · 纯代码，零 LLM）
==================================
职责：读 GameState → 选下一场景（骨架导航 + 状态驱动岔路 + tension 判定）
输出：ScenePlan（含 distance_map 角色距离映射，供 Writer 分层注入人设）
"""
import json
import os
from typing import Optional

from .state import GameState

_REGISTRY: Optional[dict] = None
_REGISTRY_MTIME: float = 0.0


def load_registry() -> dict:
    """加载场景注册表（mtime 缓存：JSON 文件变了就重读，开发期免重启）"""
    global _REGISTRY, _REGISTRY_MTIME
    path = os.path.join(os.path.dirname(__file__), "scenes", "registry.json")
    mtime = os.path.getmtime(path)
    if _REGISTRY is None or mtime != _REGISTRY_MTIME:
        with open(path, encoding="utf-8") as f:
            _REGISTRY = json.load(f)
        _REGISTRY_MTIME = mtime
    return _REGISTRY


class ScenePlan:
    """场景导航结果"""

    def __init__(self, scene: dict, distance_map: dict, next_pos: str):
        self.scene = scene
        self.scene_id = scene["scene_id"]
        self.chapter = scene["chapter"]
        self.chapter_label = scene.get("chapter_label", "")
        self.year = scene.get("year", 0)
        self.season = scene.get("season", "")
        self.location = scene.get("location", "")
        self.title = scene.get("title", "")
        self.setting = scene.get("setting", "")
        self.world_normal = scene.get("world_normal", "")
        self.player_pov = scene.get("player_pov", [])
        self.locked_lines = scene.get("locked_lines", [])
        self.options = scene.get("options", [])
        self.distance_map = distance_map   # {角色: 远观|互动|核心}
        self.next_pos = next_pos           # 下一场景 id（由 aftereffect 决定）

    @classmethod
    def from_summary(cls, s: dict) -> "ScenePlan":
        """从 meta 里的 plan_summary（可序列化 dict）重建"""
        scene = {
            "scene_id": s.get("scene_id", ""),
            "chapter": s.get("chapter", ""),
            "chapter_label": s.get("chapter_label", ""),
            "year": s.get("year", 0),
            "season": s.get("season", ""),
            "location": s.get("location", ""),
            "title": s.get("title", ""),
            "setting": s.get("setting", ""),
            "world_normal": s.get("world_normal", ""),
            "player_pov": s.get("player_pov", []),
            "locked_lines": s.get("locked_lines", []),
            "options": s.get("options", []),
        }
        return cls(scene, s.get("distance_map", {}), s.get("next_pos", ""))


def choose_scene(state: GameState) -> ScenePlan:
    """主入口：读 State → 选场景 → ScenePlan

    导航逻辑：
    1. 按 state.skeleton_pos 找场景
    2. 若无（新开局）→ P1_s1_rain
    3. 场景的 aftermath.flow 决定下一场景（状态驱动岔路入口，后续扩展 flags）
    """
    registry = load_registry()
    pos = state.get("skeleton_pos") or "P1_s1_rain"
    scene = registry.get(pos)
    if scene is None:
        scene = registry["P1_s1_rain"]

    # 距离映射：从场景的锁定台词/选项中提取角色 → 默认"远观"
    distance_map = _infer_distance_map(scene, state)
    # 下一场景
    next_pos = _resolve_next(scene, state)
    return ScenePlan(scene, distance_map, next_pos)


def _resolve_next(scene: dict, state: GameState) -> str:
    """解析场景 aftermath.flow → 下一场景 id（状态驱动岔路入口）"""
    aftermath = scene.get("aftermath", {})
    flow = aftermath.get("flow", "")
    # 占位符替换（后续扩展：按 flags/tension 岔路）
    return flow


def _infer_distance_map(scene: dict, state: GameState) -> dict:
    """推断角色距离：场景锁定台词中出现的角色 = 核心；relations 中有记录 = 互动；其余远观"""
    from .writer import KNOWN_NAMES  # 延迟导入避免循环

    distance_map = {}
    # 锁定台词中的说话人 → 核心
    for line in scene.get("locked_lines", []):
        sp = line.get("speaker", "")
        if sp and sp != "玩家":
            distance_map[sp] = "核心"
    # relations 有记录 → 互动（若未标核心）
    for name in state.get("relations", {}):
        distance_map.setdefault(name, "互动")
    # 其余已知角色 → 远观（不预填，Writer 按需）
    return distance_map
