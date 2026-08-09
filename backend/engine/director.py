# -*- coding: utf-8 -*-
"""
Director（导演层 · 纯代码，零 LLM）
==================================
职责：读 GameState → 选下一场景（骨架导航 + 状态驱动岔路 + tension 判定）
输出：ScenePlan（含 distance_map 角色距离映射，供 Writer 分层注入人设）
"""
import json
import logging
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
        self.rumor_unlock = None  # 本拍打听解锁的地点（命中「打听X」传闻 → 地点名）

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

    导航逻辑（自由沙盒 · 玩家驱动，见设计 §5.2）：
    1. 玩家动作「前往X」→ 已解锁地点直达回访 / 未解锁沿 flow 推进一拍
    2. 无地点动作 → 按 state.skeleton_pos 停留当前场景（自由驻留）
    3. 场景 aftermath.flow 决定下一场景（状态驱动岔路，供未表达目的地时的推进）
    """
    registry = load_registry()
    # 地点导航：读本拍玩家动作，命中「前往X」→ 目标场景（直达/推进）
    travel = None
    last_action = ""
    for h in reversed(state.get("history", [])):
        if h.get("user"):
            last_action = h["user"]
            break
    if last_action:
        travel = resolve_travel(last_action, state)
    # 传闻解锁：玩家「打听X」命中传闻中的地点 → 本拍驻留演"确认消息"（不赶路），解锁该地
    rumor_unlock = resolve_rumor(last_action, state) if last_action else None
    if rumor_unlock:
        travel = None  # 打听 = 原地确认，不移动
    pos = (travel[1] if travel else None) or state.get("skeleton_pos") or "P1_s1_rain"
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
    # 玩家已表达目的地（直达/推进）→ 本拍驻留，不再沿 flow 继续推
    # 打听传闻 = 原地确认消息（解锁地点，不赶路不推进）
    next_pos = "" if (travel or rumor_unlock) else _resolve_next(scene, state)
    # 安全阀：防止 placeholder 场景自循环耗尽 LLM 额度
    if not travel and next_pos == pos:
        logger = logging.getLogger(__name__)
        turn = state.get("turn", 0)
        if turn > 15:
            logger.warning(
                f"场景自循环检测: {pos} → {next_pos}（turn={turn}），"
                f"可能缺少后续场景。使用 END 终止。"
            )
            next_pos = "END"
    plan = ScenePlan(scene, distance_map, next_pos)
    plan.rumor_unlock = rumor_unlock
    return plan



# ═════════ 地点导航（自由沙盒 · 见设计 §5.2）═════════

def _visited_scenes(state: GameState) -> list:
    """玩家访问过的场景 id（按历史顺序，最后访问在末尾）。

    当前 skeleton_pos 视为已访问（所在即解锁，开局雨夜即解锁颍川）。
    """
    visited = [h.get("scene_id") for h in state.get("history", []) if h.get("scene_id")]
    cur = state.get("skeleton_pos")
    if cur and cur not in visited:
        visited.append(cur)
    return visited


def _location_of(scene_id: str) -> str | None:
    """场景 id → 所属地点名（反查 LOCATIONS）。"""
    from .worlddata import LOCATIONS
    for name, scenes in LOCATIONS.items():
        if scene_id in scenes:
            return name
    return None


def _walk_flow(state: GameState) -> list:
    """当前场景沿 aftermath.flow 链的所有后续场景（有序、去重、防环）。"""
    registry = load_registry()
    cur = state.get("skeleton_pos") or "P1_s1_rain"
    seen, out = set(), []
    while cur in registry and cur not in seen:
        seen.add(cur)
        flow = (registry[cur].get("aftermath") or {}).get("flow")
        if isinstance(flow, dict):
            flow = flow.get("default") or ""
        if not flow or flow == "END" or flow not in registry:
            break
        out.append(flow)
        cur = flow
    return out


def resolve_travel(action: str, state: GameState):
    """玩家「前往X」→ (mode, scene_id) 或 None。

    - 已解锁地点 → 优先沿 flow 推进该地点内"未访问场景"（探索更深）；
      地点内全访问 → ('goto', 最后访问场景) 回访
    - 未解锁地点但在推进路径（flow 链可达）→ ('advance', 第一个未访问场景) 沿 flow 推进一拍
    - 未知地点 / 非地点动作 → None（走正常场景流程）
    """
    from .worlddata import match_location, LOCATIONS
    name = match_location(action)
    if not name:
        return None
    # 行动受限（自由沙盒 §4.2）：体力 <20 不能赶远路——不切场景，writer 已注入
    # "行动受限"提示，LLM 演"体力透支赶不了路"（玩家休息恢复后再去）
    try:
        stamina = int((state.get("player") or {}).get("stats", {}).get("stamina", 100))
    except (TypeError, ValueError):
        stamina = 100
    if stamina < 20:
        return None
    visited = _visited_scenes(state)
    scenes = LOCATIONS.get(name, [])
    # 已解锁 = 实地到访过 或 传闻解锁（rumor_unlocked，UI 显示"可前往"——修复：此前只看
    # visited，传闻解锁地点被当未解锁、目标地点名被忽略）
    if any(s in visited for s in scenes) or name in (state.get("rumor_unlocked") or []):
        # 已解锁：优先探索该地点内未访问场景（沿 flow 链，地点内更深处）
        for sid in _walk_flow(state):
            if sid not in visited and _location_of(sid) == name:
                return ("advance", sid)
        # 地点内无未访问 → 回访最后访问场景
        for sid in reversed(visited):
            if sid in scenes:
                return ("goto", sid)
    else:
        # 未解锁：沿 flow 链推进到第一个未访问场景（前往该地点的路上）
        for sid in _walk_flow(state):
            if sid not in visited:
                return ("advance", sid)
    return None


def _location_state(state: GameState, rumor_unlock: str = None) -> dict:
    """地点面板状态：当前地点 / 已解锁（可往返）/ 下站（推进目标）/ 传闻地点（打听解锁）。

    - unlocked = 去过（visited）∪ 传闻解锁（rumor_unlocked，独立于 visited 的持久字段）
    - rumored = 已解锁地点的传闻指向中，尚未解锁的地点（带 hint，前端显示"传闻"态）
    - next_station = 沿 flow 链第一个"未访问且地点未解锁"的场景所属地点
    rumor_unlock: 本拍新增的打听解锁地点（并入 rumor_unlocked 参与计算）。
    """
    visited = _visited_scenes(state)
    from .worlddata import LOCATIONS, LOCATION_RUMORS
    # 已去过 + 传闻解锁 → 可往返/可赶路
    base = list(state.get("rumor_unlocked") or [])
    if rumor_unlock and rumor_unlock not in base:
        base.append(rumor_unlock)
    unlocked = [name for name, scenes in LOCATIONS.items() if any(s in visited for s in scenes)]
    unlocked += [n for n in base if n not in unlocked]
    # 已解锁地点的传闻 → 点亮传闻地点（未解锁、去重）
    rumored = []
    for name in unlocked:
        for r in LOCATION_RUMORS.get(name, []):
            t = r.get("target", "")
            if t and t not in unlocked and all(x["name"] != t for x in rumored):
                rumored.append({"name": t, "hint": r.get("hint", "")})
    current = _location_of(state.get("skeleton_pos") or "")
    next_station = None
    for sid in _walk_flow(state):
        if sid not in visited:
            loc = _location_of(sid)
            if loc and loc not in unlocked:
                next_station = loc
                break
    return {"current": current, "unlocked": unlocked, "next_station": next_station, "rumored": rumored}


def resolve_rumor(action: str, state: GameState) -> str | None:
    """「打听X地/探听X」→ 若 X 在传闻中（未解锁但听过传闻）→ 返回 X（解锁），否则 None。

    传闻解锁（自由沙盒 §5.2）：玩家打听到确切消息 → 该地升级为可赶路（rumor_unlocked）。
    不影响本拍移动（打听=驻留演"确认消息"，不赶路）。
    """
    a = (action or "").strip()
    if not a or not any(k in a for k in ("打听", "探听", "打探", "问问")):
        return None
    ls = _location_state(state)
    for r in ls.get("rumored", []):
        if r["name"] in a:
            return r["name"]
    return None


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
