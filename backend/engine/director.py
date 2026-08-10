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


# 阶段 → 篇章（自由大世界：era.chapter 由 phase_of(world_date) 派生，取代 registry 静态章）
CHAPTER_BY_PHASE = {
    1: "P1 黄金风起",
    2: "P2 洛阳暗夜",
    3: "P3 诸侯并起",
    4: "P4 中原逐鹿",
    5: "P5 赤壁三足",
    6: "P6 天下三分",
}


# ═════════ 名场面接线（决策 1：view_scene 注入 registry 名场面）═════════
# 时间线事件 id → registry 名场面场景 id。事件到点 + 玩家在场（witnessable）时，
# view_scene 把该场景的锁定台词/选项/flag 注入自由视野（"字幕锚定"，见 continuity.py）。
# 未接线的事件仍走过程化合成（事件在 setting 简述，不锁定台词）。
# P2~P4 名场面已全接线：事件到点 + 玩家在场 → 注入 registry 场景锁定台词。
FAMOUS_SCENE_BY_EVENT: dict[str, str] = {
    "e_189_08_dongzhuo_jinjing": "P2_s1_street",
    "e_189_09_cao_cao_xian_dao": "P2_s2_ci",
    "e_190_01_zhuhou_huimeng": "P3_s1_alliance",
    "e_190_02_wenjiu_huaxiong": "P3_s2_huaxiong",
    "e_190_02_sanying_zhan_lvbu": "P3_s3_three",
    # P4：192 年董卓伏诛（凤仪亭）→ 李傕郭汜乱长安
    "e_192_04_dongzhuo_fuzhu": "P4_s1_fengyiting",
    "e_192_06_lijue_guosi": "P4_s2_lijueguosi",
    # P4：194-199 群雄割据（三让徐州→迎帝→辕门射戟→称帝→白门楼→败亡→煮酒）
    "e_194_09_sanrang_xuzhou": "P4_s3_sanrang",
    "e_196_08_caocao_yingdi": "P4_s4_yingdi",
    "e_196_10_yuanmen_sheji": "P4_s5_yuanmen",
    "e_197_02_yuanshu_chengdi": "P4_s6_chengdi",
    "e_198_12_lvbu_zhiming": "P4_s7_lvbu",
    "e_199_07_yuanshu_baiwang": "P4_s8_baiwang",
    "e_199_11_zhujiu_lunying": "P4_s9_zhujiu",
    # 官渡定鼎批（200-207）：关羽降曹→官渡之战→袁绍败亡→投荆州→三顾茅庐
    "e_200_06_guanyu_wuguan": "P4_s10_guanyu",
    "e_200_09_guandu_dazhan": "P4_s11_guandu",
    "e_200_10_yuanshao_baiwang": "P4_s12_yuanshao",
    "e_201_05_xin_ye_li_zu": "P4_s13_xinye",
    "e_207_10_wolong_chushan": "P4_s14_wolong",
    # 赤壁三足批（208-219）：博望坡→长坂坡→赤壁→华容道→借荆州→四郡→甘露寺→合肥→
    # 周瑜之死→张松献图→入川→落凤坡→益州易主→单刀赴会→逍遥津→汉中之战→水淹七军
    "e_208_01_bowangpo": "P5_s1_bowangpo",
    "e_208_09_changbanpo": "P5_s2_changbanpo",
    "e_208_10_chibizhizhan": "P5_s3_chibi",
    "e_208_11_huarongdao": "P5_s4_huarong",
    "e_209_05_nanjun_jiezhou": "P5_s5_nanjun",
    "e_209_08_qujingnan_sijun": "P5_s6_sijun",
    "e_209_10_sun_liu_ganlu": "P5_s7_ganlu",
    "e_209_12_hefei": "P5_s8_hefei",
    "e_210_11_zhouyu_zhi_si": "P5_s9_zhouyu",
    "e_210_12_zhangsong_xiantu": "P5_s10_zhangsong",
    "e_211_12_liubei_ruchuan": "P5_s11_ruchuan",
    "e_214_06_fengchu_luofengpo": "P5_s12_luofengpo",
    "e_214_06_yizhou_yizhu": "P5_s13_yizhou",
    "e_215_08_dandao_fuhui": "P5_s14_dandao",
    "e_215_08_hefei_xiaoyaojin": "P5_s15_xiaoyaojin",
    "e_219_01_hanzhong_dingshan": "P5_s16_hanzhong",
    "e_219_08_guanyu_beifa": "P5_s17_guanyubeifa",
    # P6：天下三分（220-223）败走麦城→曹操之死→曹丕篡汉→夷陵之战→白帝托孤
    "e_220_01_maicheng": "P6_s1_maicheng",
    "e_220_01_caocao_zhi_si": "P6_s2_caocao",
    "e_220_11_caopi_chanhan": "P6_s3_caopi",
    "e_222_08_yiling_zhizhan": "P6_s4_yiling",
    "e_223_04_baidi_tuogu": "P6_s5_baidi",
}


def _match_famous_scene(due: list) -> tuple:
    """从到点事件里选"正在上演的名场面" → (事件, registry 场景) 或 (None, None)。

    规则：witnessable（玩家在场亲历）且事件 id 在 FAMOUS_SCENE_BY_EVENT 中。
    取 due 里最靠后的一个——due 已按时间线日期排序，靠后 = 最新到点；同月双事件
    （如 190-02 温酒/三英在陈留都可见）取时间线靠后的三英，即"当前正在进行的这场"。
    事件已过（不在窗口）/玩家不在场（不 witnessable）→ None，过程化合成兜底。
    """
    reg = load_registry()
    pick = None
    for e in due:
        if not e.get("witnessable"):
            continue
        sid = FAMOUS_SCENE_BY_EVENT.get(str(e.get("event_id", "")))
        if sid and sid in reg:
            pick = (e, reg[sid])  # 迭代到最后一个命中 → 最新到点的名场面
    return pick or (None, None)


def _current_location(state: GameState) -> str:
    """玩家当前位置（地点名，LOCATIONS 键）。player.location 优先，era.location 兜底。"""
    loc = state.get("player", {}).get("location", "") or (state.get("era") or {}).get("location", "")
    from .worlddata import LOCATIONS
    for name in LOCATIONS:
        if loc and (name in loc or loc in name):
            return name
    return loc or "颍川"


def view_scene(state: GameState) -> ScenePlan:
    """自由大世界视野合成：读 state → 合成"玩家当前所在世界切片" → ScenePlan。

    不再读 registry 场景剧本。全部字段由 world_date + phase_of + 地点常态 + 到点事件派生：
      - scene_id / skeleton_pos = 当前地点名（LOCATIONS 键，如 "颍川"）
      - chapter = CHAPTER_BY_PHASE[phase_of(world_date)]
      - year/season = world_date 的年 / season_of(月)
      - setting = 地点细描 + 天下大势 + 到点事件（在场 witnessable）
      - distance_map = 在场角色 → "互动"（供 writer 人设分层）
      - options = 过程化选项种子（Step 3 升级为 LLM 引导；此处先给世界行动引导）
    world_date 是唯一时钟——杜绝"189-02 仍判 P1"（时期由世界日期判，非场景静态年）。
    """
    from .worlddata import world_context, LOCATIONS, phase_of
    from .world import season_of, due_events

    wd = state.get("world_date") or {"year": 184, "month": 2, "day": 1}
    loc = _current_location(state)
    idx = phase_of(wd)
    chapter = CHAPTER_BY_PHASE.get(idx, "P1 黄金风起")
    wctx = world_context(wd, loc)

    # 1. setting：地点细描 + 天下大势 + 本地点常态
    setting_lines = [f"{loc}·{wctx.get('phase_name', '')}"]
    n = wctx.get("normal") or {}
    if n.get("world", {}).get("summary"):
        setting_lines.append(f"天下大势：{n['world']['summary']}")
    lc = wctx.get("location_normal")
    if lc:
        setting_lines.append(f"【{lc.get('name', '')}】{lc.get('status', '')}")
    # 2. 到点事件（本拍在场 → witnessable，注入"现场正在发生"）
    prev_wd = {"year": int(wd.get("year", 0)), "month": int(wd.get("month", 1) or 1) - 1, "day": 1}
    due = due_events(prev_wd, wd, loc)
    # 2.5 名场面接线：事件到点+在场 → 命中 registry 场景（锁定台词/选项/flag 注入视野）
    famous_ev, famous_scene = _match_famous_scene(due)
    for e in due:
        if e.get("witnessable") and e is not famous_ev:
            setting_lines.append(f"现场正在发生：{e.get('event', '')}")
    setting = "\n".join(setting_lines)

    # 2.5 P1 后期软引导（决策 11：自然流逝 + 自主赴洛阳）：黄金之乱平息后（184-10 起），
    #     往北洛阳的风声渐紧（董卓进京前兆），引导玩家可自行前往洛阳进入 P2（软引导不硬推）
    wd_y = int(wd.get("year", 0) or 0)
    wd_m = int(wd.get("month", 1) or 1)
    if idx == 1 and (wd_y > 184 or (wd_y == 184 and wd_m >= 10)):
        setting_lines.append("北边传来的风声越来越紧——洛阳城似乎要变天了。")
        setting = "\n".join(setting_lines)

    # 2.6 P1 暗线钩子（决策 17：自由行动触发）：未触发的暗线 hint 注入视野，
    #     让 LLM 在叙事/选项里自然带出（软钩子，玩家按 trigger 行动即触发）
    if idx == 1:
        from .player_data import _load_darklines
        dl_data = _load_darklines()
        for line, spec in dl_data.items():
            if not isinstance(spec, dict) or line.startswith("_"):
                continue
            if spec.get("flag") in (state.get("flags") or []):
                continue  # 已触发
            if spec.get("hint") and spec.get("hint") not in setting_lines:
                setting_lines.append(f"【暗线】{spec['hint']}")
        setting = "\n".join(setting_lines)

    # 3. 在场角色（distance_map）：严格"在场即呈现"（决策 10）——只呈现玩家
    #    真正遇到/认识的角色（character_states 已登记且位置匹配当前地点的），
    #    以及本拍在场亲历（witnessable）事件的主角。
    #    不再把 world_normal 常态角色全量塞入（那是"此阶段有此人物"的背景，不是"此刻在场"——
    #    刘备/关羽在涿郡，不应出现在颍川"在场"，也不该被 LLM 造无依据的关系值）。
    distance_map = {}
    from .character_states import ensure_character, present_characters
    from .worlddata import LOCATIONS
    # ① 已登记且位置匹配当前地点的角色（玩家真接触过的）
    cur = _current_location(state)
    for name, st in (state.get("character_states") or {}).items():
        cl = (st or {}).get("location", "")
        if cl and cur and (cl in cur or cur in cl) and st.get("known"):
            distance_map[name] = "互动"
    # ② 本拍在场亲历（witnessable）事件的主角 → 登记进档案 + 在场
    for e in due:
        if not e.get("witnessable"):
            continue
        for npc in (e.get("key_npcs") or []):
            if npc and npc not in distance_map:
                distance_map[npc] = "互动"
                ensure_character(state, npc)
    # ③ 名场面锁定台词说话人（非泛型）→ 在场可互动（名场面主角如袁隗/刘三刀/袁术等，
    #     可能不在事件 key_npcs 里但台词锁定必须出场；泛型说话人如管家由 writer 直接渲染）
    if famous_scene:
        from .writer import GENERIC_NAMES
        for line in famous_scene.get("locked_lines", []):
            sp = line.get("speaker", "")
            if sp and sp not in GENERIC_NAMES and sp not in distance_map:
                distance_map[sp] = "互动"
                ensure_character(state, sp)

    # 4. 过程化选项种子（Step 3 升级；此处给世界行动引导，writer 可改造）
    opts = []
    if due:
        opts.append({"text": f"观察眼前正在发生的事（{due[0].get('event', '')[:18]}…）",
                     "type": "minor", "tension": 5, "effect": "亲历此刻天下大事", "category": "打探"})
    if lc and lc.get("daily_scenes"):
        opts.append({"text": f"在这附近转转，看看{lc.get('name', '')}的人情世故",
                     "type": "minor", "tension": 5, "effect": "打探当地消息/找机会", "category": "打探"})
    if distance_map:
        top = next(iter(distance_map))
        opts.append({"text": f"去找{top}攀谈",
                     "type": "major", "tension": 10, "effect": "与在场人物互动，经营关系", "category": "互动"})
    # 可赴地点（阶段可达地图）
    unlocked = [name for name, _ in LOCATIONS.items() if name != loc]
    if unlocked:
        opts.append({"text": f"前往{unlocked[0]}（赶路）",
                     "type": "minor", "tension": 0, "effect": "移动至其他地点，耗费旅途时间", "category": "赶路"})
    opts.append({"text": "在此歇脚，等天色亮些再说", "type": "minor", "tension": 0,
                 "effect": "休息恢复，世界时间流逝", "category": "停留"})

    scene = {
        "scene_id": loc,
        "chapter": chapter,
        "chapter_label": f"{wd.get('year', '?')} 年 · {loc}",
        "year": int(wd.get("year", 0) or 0),
        "season": season_of(int(wd.get("month", 1) or 1)),
        "location": loc,
        "atmo": "",
        "music": "",
        "title": f"{loc}·{wctx.get('phase_name', '')}",
        "setting": setting,
        "world_normal": "世界侧一切正常运转，NPC 各忙各的。玩家是其中的自由参与者。",
        "player_pov": (state.get("player") or {}).get("notes", []) or [
            "你总觉得这世道有哪里不对——可仔细想，又想不起该是什么样",
        ],
        "locked_lines": [],
        "options": opts,
        "flags_on_enter": [],
        "aftermath": {},
    }
    # 名场面接线（决策 1）：命中 → 注入 registry 场景的锁定台词/选项/flag。
    # 保 scene_id=loc（地点导航零回归）；era.chapter 仍由 phase 派生（世界面板 P2 不变）。
    if famous_scene:
        scene["chapter_label"] = famous_scene.get("chapter_label", scene["chapter_label"])
        scene["year"] = int(famous_scene.get("year", scene["year"]) or 0)
        scene["season"] = famous_scene.get("season", scene["season"])
        scene["location"] = famous_scene.get("location", scene["location"])
        scene["atmo"] = famous_scene.get("atmo", scene["atmo"])
        scene["music"] = famous_scene.get("music", scene["music"])
        scene["title"] = famous_scene.get("title", scene["title"])
        scene["setting"] = famous_scene.get("setting", scene["setting"])
        scene["world_normal"] = famous_scene.get("world_normal", scene["world_normal"])
        scene["player_pov"] = famous_scene.get("player_pov", scene["player_pov"])
        scene["locked_lines"] = famous_scene.get("locked_lines", scene["locked_lines"])
        # 名场面选项 + 自由出口（玩家可旁观/参与/离开，不被锁死在名场面里）
        scene["options"] = list(famous_scene.get("options") or []) + [
            {"text": "不掺和，退到一边，把这出热闹看完", "type": "minor", "tension": 0,
             "effect": "旁观名场面，不介入", "category": "停留"},
        ]
        scene["flags_on_enter"] = famous_scene.get("flags_on_enter", scene["flags_on_enter"])
        scene["aftermath"] = famous_scene.get("aftermath", scene["aftermath"])
    plan = ScenePlan(scene, distance_map, "")
    plan.rumor_unlock = None
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
    """地点面板状态（自由大世界 · 阶段可达地图）：当前地点 / 已解锁 / 可赴地点 / 传闻地点。

    - current = 玩家当前位置（player.location，LOCATIONS 键）
    - unlocked = 去过（visited，历史 scene_id=地点名）∪ 传闻解锁（rumor_unlocked）
    - next_station = 最近一个"去过地点"的传闻指向/相邻地点（引导下一步赶路）
    - rumored = 已解锁地点的传闻指向中，尚未解锁的地点（带 hint，前端显示"传闻"态）
    rumor_unlock: 本拍新增的打听解锁地点（并入 rumor_unlocked 参与计算）。
    """
    visited = _visited_scenes(state)
    from .worlddata import LOCATIONS, LOCATION_RUMORS
    base = list(state.get("rumor_unlocked") or [])
    if rumor_unlock and rumor_unlock not in base:
        base.append(rumor_unlock)
    # visited 的 scene_id 现在=地点名（view_scene 写回）；兼容旧存档（场景 id 反查地点）
    unlocked = []
    for name in LOCATIONS:
        scenes = LOCATIONS[name]
        if any(s in visited for s in scenes) or name in visited or name in base:
            unlocked.append(name)
    # 已解锁地点的传闻 → 点亮传闻地点（未解锁、去重）
    rumored = []
    for name in unlocked:
        for r in LOCATION_RUMORS.get(name, []):
            t = r.get("target", "")
            if t and t not in unlocked and all(x["name"] != t for x in rumored):
                rumored.append({"name": t, "hint": r.get("hint", "")})
    current = _current_location(state)
    # 引导：第一个"未去且不是传闻"的地点（相邻地）→ 可赴；否则下一传闻地
    next_station = None
    for name in LOCATIONS:
        if name != current and name not in unlocked and name not in [r["name"] for r in rumored]:
            next_station = name
            break
    if next_station is None and rumored:
        next_station = rumored[0]["name"]
    return {
        "current": current,
        "unlocked": unlocked,
        "next_station": next_station,
        "rumored": rumored,
        # 全量地点顺序（天下舆图渲染用）：前端不再硬编码 5 个 P1 地点，防与后端 LOCATIONS 失步
        "locations": list(LOCATIONS.keys()),
    }


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
