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
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        # 文件缺失：保留上次成功加载的缓存（从未加载则空 dict）
        return _REGISTRY if _REGISTRY is not None else {}
    if _REGISTRY is None or mtime != _REGISTRY_MTIME:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger = logging.getLogger(__name__)
            logger.error(f"registry.json 加载失败: {e}，保留旧缓存")
            return _REGISTRY if _REGISTRY is not None else {}
        _REGISTRY = data
        _REGISTRY_MTIME = mtime
        _warn_dangling_flows(data)
    return _REGISTRY


def _warn_dangling_flows(registry: dict) -> None:
    """加载时校验 aftermath.flow 目标 id 都在 registry 内（防 flow 笔误致伪重开）"""
    for sid, scene in registry.items():
        flow = (scene.get("aftermath") or {}).get("flow")
        if isinstance(flow, str) and flow and flow != "END" and flow not in registry:
            logging.getLogger(__name__).warning(
                f"场景 {sid} aftermath.flow -> {flow} 在 registry 中不存在（将导致伪重开）"
            )


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
        # 自由沙盒：场景选项即普通选项（独立提示，LLM 可改写；无行动盘机制）
        self.options = scene.get("options", [])
        self.atmo = scene.get("atmo", "雨夜沉静")  # 氛围标签（匹配 AtmoBackground）
        self.music = scene.get("music", "")
        self.flags_on_enter = scene.get("flags_on_enter", [])  # 入场锚定 flag（关键节点必亲历）
        self.aftermath = scene.get("aftermath", {})  # aftermath（flow/memory_add，供 remember 记忆接线）
        self.distance_map = distance_map
        self.next_pos = next_pos

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
            "atmo": s.get("atmo", "雨夜沉静"),
            "music": s.get("music", ""),
            "flags_on_enter": s.get("flags_on_enter", []),
            "aftermath": s.get("aftermath", {}),
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
        if pos == "P1_s1_rain" or not pos:
            # 新开局：P1_s1_rain 必须存在，否则无法起步
            scene = registry.get("P1_s1_rain")
        if scene is None:
            # 未知/悬空 pos（flow 笔误或占位被删）：挂起当前场景，不回退 P1（防带记忆伪重开）
            logging.getLogger(__name__).warning(
                f"场景 {pos} 不存在（flow 目标悬空），挂起当前场景防伪重开"
            )
            return ScenePlan(_dead_end_scene(pos), {}, "")

    # 距离映射：从场景的锁定台词/选项中提取角色 → 默认"远观"
    distance_map = _infer_distance_map(scene, state)
    # 下一场景（状态驱动岔路）
    next_pos = _resolve_next(scene, state)
    # 安全阀：防止 placeholder 场景自循环耗尽 LLM 额度
    if next_pos == pos:
        logger = logging.getLogger(__name__)
        turn = state.get("turn", 0)
        if turn > 15:
            logger.warning(
                f"场景自循环检测: {pos} → {next_pos}（turn={turn}），"
                f"可能缺少后续场景。使用 END 终止。"
            )
            next_pos = "END"
    return ScenePlan(scene, distance_map, next_pos)



def _dead_end_scene(pos: str) -> dict:
    """未知场景的占位 stub（挂起用，next_pos 空 → 不推进）"""
    return {
        "scene_id": pos, "chapter": "?", "chapter_label": "", "year": 0, "season": "",
        "location": "", "atmo": "雨夜沉静", "title": "（场景缺失）",
        "setting": f"场景 {pos} 尚未定义。", "world_normal": "", "player_pov": [],
        "locked_lines": [], "options": [], "flags_on_enter": [],
    }


def _resolve_next(scene: dict, state: GameState) -> str:
    """解析场景 aftermath.flow → 下一场景 id（状态驱动岔路）

    flow 支持三种格式：
    1. 字符串：直接作为下一场景 id（线性推进）
    2. 字典：{"flag_name": "scene_id", ...} — 按 state.flags 匹配第一条
       - 特殊 key "default" 始终兜底
       - 特殊 key "tension_high" / "tension_mid" 按 tension 阈值匹配
    3. 空：停留在当前场景（死路保护见调用方）

    安全阀：若解析结果 = 当前 scene_id（自循环），且 turn > 15，
    记录 warning 并置 END（graph.run_step 守卫不推进 skeleton_pos 防伪重开）。
    """
    aftermath = scene.get("aftermath", {})
    flow = aftermath.get("flow", "")

    # ── 字典分支 ──
    if isinstance(flow, dict):
        flags = set(state.get("flags", []))
        tension = state.get("tension", 0)
        turn = state.get("turn", 0)

        # 天意修正标志（corrected 非空 → tension 曾触发）
        if state.get("corrected"):
            flags.add("天意修正")

        # ① 优先匹配 flags
        for flag_name, target in flow.items():
            if flag_name in ("default", "tension_high", "tension_mid", "tension_low"):
                continue
            if flag_name in flags:
                return target

        # ② tension 阈值匹配
        if tension > 70 and "tension_high" in flow:
            return flow["tension_high"]
        if tension > 30 and "tension_mid" in flow:
            return flow["tension_mid"]

        # ③ 兜底
        if "default" in flow:
            return flow["default"]
        # 无 default 且无 flag/tension 命中：挂起当前场景（不误入第一个分支）
        return ""

    # ── 字符串分支（直接返回）──
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
