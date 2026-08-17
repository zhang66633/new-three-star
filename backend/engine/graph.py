# -*- coding: utf-8 -*-
"""
LangGraph 图定义（新三国 星空 · 引擎主图）
==========================================
Phase 1: director → narrate → END
Phase 2: director → narrate ⇄ validate(重写≤2) → corrector(按tension) → remember → END
"""
import copy
import logging
from typing import Literal

from langgraph.graph import StateGraph, START, END

from .state import GameState, from_dict, to_dict
from .director import view_scene, ScenePlan, _location_state
from .writer import narrate
from .validator import validate
from .corrector import classify_tension, apply_correction
from .remember import stm_append, promote_stm_to_ltm, retrieve_memories
from .continuity import on_scene_entry, after_beat, resolve_player_choice

logger = logging.getLogger(__name__)

MAX_RETRY = 2


# 流式：SSE 由 play.py 在引擎跑完后对最终叙事分块透出（post-validate 定稿分块）。
# 引擎内不再用 ContextVar 流式回调（历史遗留两套设计，已统一为一套）。

# ═════════ 节点实现 ═════════

def director_node(state: GameState) -> dict:
    """合成视野，plan 可序列化摘要存入 meta（ScenePlan 对象不落 state）

    era 写回：由 world_date + view_scene 派生（year/season/location/chapter 全部来自
    world_date/phase_of，取代旧场景静态年——杜绝"189-02 仍判 P1"）。
    供前端 eraLabel、validator P0 时间连续性、writer 时空面板、remember 时间标签使用。
    """
    plan = view_scene(state)
    # 时代状态写回（统一时钟：era 由 world_date 派生，单调向前不回退）
    era = dict(state.get("era", {}))
    wd = state.get("world_date") or {}
    era["year"] = int(plan.year or wd.get("year", 0) or 0)
    if plan.season:
        era["season"] = plan.season
    if plan.location:
        era["location"] = plan.location
    era["chapter"] = plan.chapter

    # 入场锚定 flag：关键节点"必亲历"的工程保证（如 见证者_官道之辩），
    # 由 registry 场景 flags_on_enter 声明，director 直接写入，不依赖 LLM 关键词碰运气
    flags = list(state.get("flags", []))
    for f in plan.flags_on_enter:
        if f not in flags:
            flags.append(f)

    # 主线推进接线（审查⑦）：无地点动作时沿 aftermath.flow 推进一拍（叙事选项推动主线，
    # 不再要求玩家手动"前往X"）；但休息/等待等驻留空闲动作保持驻留（玩家可歇息恢复不被推走）；
    # END 不应用（自循环守卫=暂停推进防伪重开）。next_pos 此前悬空从未写回 skeleton_pos。
    from .world import is_idle_action
    np = plan.next_pos
    if np and np != "END":
        last_a = ""
        for h in reversed(state.get("history", [])):
            if h.get("user"):
                last_a = h["user"]
                break
        if last_a and is_idle_action(last_a):
            np = ""  # 驻留空闲（休息/等待）：不推进
    skeleton_pos = np if np else plan.scene_id

    return {
        "meta": {
            **state.get("meta", {}),
            "plan_summary": {
                "scene_id": plan.scene_id,
                "next_pos": plan.next_pos,
                "chapter_label": plan.chapter_label,
                "year": plan.year,
                "season": plan.season,
                "location": plan.location,
                "title": plan.title,
                "setting": plan.setting,
                "world_normal": plan.world_normal,
                "player_pov": plan.player_pov,
                "locked_lines": plan.locked_lines,
                "distance_map": plan.distance_map,
                "options": plan.scene.get("options", []),  # 场景手调选项（LLM 可选用或改写）
                "atmo": plan.atmo,
                "music": plan.music,
                "flags_on_enter": plan.flags_on_enter,
                "aftermath": plan.aftermath,
            },
            # 记录上轮时空（供 validate P0 时间连续性检测）
            "prev_era": dict(state.get("era", {})),
            # 本拍打听解锁的传闻地（供 writer 演"确认消息"，运行时信息不持久化）
            **({"rumor_unlock": plan.rumor_unlock} if plan.rumor_unlock else {}),
        },
        "era": era,
        "flags": flags,
        "skeleton_pos": skeleton_pos,
        "location_state": _location_state(state, plan.rumor_unlock),  # 地点面板状态（current/unlocked/next_station/rumored）
        **({"rumor_unlocked": list(state.get("rumor_unlocked") or []) + [plan.rumor_unlock]}
           if plan.rumor_unlock else {}),  # 传闻解锁：打听确认的消息落地（独立于 visited）
        "retry_count": 0,  # 每轮重置重写计数
        "turn": state.get("turn", 0) + 1,  # turn 在导演层自增（每真实回合一次，不被重写污染）
        # 连续性子系统：场景变化时初始化 scene_state（开局 scene_state=None 也触发首拍登记）
        **({"scene_state": on_scene_entry(state, plan)["scene_state"]}
           if not isinstance(state.get("scene_state"), dict)
           or (state.get("scene_state") or {}).get("scene_id") != plan.scene_id else {}),
    }


async def narrate_node(state: GameState) -> dict:
    """生成叙事 + 选项（重写时注入失败原因）"""
    ps = state.get("meta", {}).get("plan_summary")
    plan = ScenePlan.from_summary(ps) if ps else view_scene(state)

    # 重写提示：注入上轮失败原因（retry_reasons 存 meta）
    retry_reasons = (state.get("meta") or {}).get("retry_reasons", [])
    if retry_reasons:
        plan.meta_retry = retry_reasons  # type: ignore

    # 记忆检索注入（PIN + top5 LTM + STM）
    player_action = (state.get("history") or [{}])[-1].get("user", "") if state.get("history") else ""
    # 检索以玩家动作为主（setting 是常量，会让开场记忆反复命中占据检索结果）
    memory_pack = retrieve_memories(state, player_action or plan.setting)

    # 叙事生成（SSE 流式由 play.py 跑完引擎后分块，这里不接流式回调）
    output = await narrate(state, plan, memory_pack=memory_pack)
    # 清重写标记（turn 由 director_node 自增，重写不污染轮次）
    meta = dict(state.get("meta", {}))
    meta.pop("retry_reasons", None)
    return {
        "last_output": output,
        "meta": meta,
    }


async def validate_node(state: GameState) -> dict:
    """8 PHASE 校验（确定性 + LLM 层）"""
    output = dict(state.get("last_output") or {})
    ps = state.get("meta", {}).get("plan_summary", {})
    scene_desc = f"{ps.get('chapter_label', '')} · {ps.get('title', '')} | {ps.get('setting', '')}"
    ok, reasons, report = await validate(state, output, scene_desc)
    # 报告同步进 last_output（前端可见）+ meta（路由用）
    output["validated"] = ok
    output["phase_report"] = report
    output["retry_reasons"] = reasons
    return {
        "last_output": output,
        "meta": {**state.get("meta", {}), "validate_ok": ok, "validate_reasons": reasons, "phase_report": report},
    }


def route_after_validate(state: GameState) -> Literal["rewrite", "forward"]:
    """校验路由：失败且重写<2 → rewrite；否则 forward"""
    meta = state.get("meta", {})
    ok = meta.get("validate_ok", True)
    reasons = meta.get("validate_reasons", [])
    retry = state.get("retry_count", 0)
    if not ok and retry < MAX_RETRY and reasons:
        return "rewrite"
    return "forward"


def rewrite_node(state: GameState) -> dict:
    """重写准备：失败原因回灌，retry_count+1"""
    meta = dict(state.get("meta", {}))
    meta["retry_reasons"] = meta.get("validate_reasons", [])
    return {
        "retry_count": state.get("retry_count", 0) + 1,
        "meta": meta,
    }


async def corrector_node(state: GameState) -> dict:
    """天意修正：按 tension 档位执行（none 跳过）"""
    output = dict(state.get("last_output") or {})
    tier = classify_tension(state.get("tension", 0))
    if tier == "none" or not output.get("narrative"):
        return {"last_trace": ""}
    ps = state.get("meta", {}).get("plan_summary", {})
    scene_desc = f"{ps.get('chapter_label', '')} · {ps.get('title', '')}"
    output = await apply_correction(state, output, scene_desc, tier)
    # 修正文本不再过 8-PHASE（审查⑭）：补确定性硬门（hidden 泄漏/点明不对劲/无选项），
    # 硬失败回退到修正前已过校验的 last_output（修正意图仍在 corrected 留痕，但不用破损文本）
    from .validator import deterministic_checks
    hard, _ = deterministic_checks(state, output)
    corrected_ok = not hard
    if hard:
        logger.warning("corrector 修正未过确定性硬门，回退原文本: %s", hard[:2])
        output = dict(state.get("last_output") or {})
    # 审查修复：重修正（事件重生成/记忆覆盖）改写叙事成功后，丢弃 LLM 声明的状态增量——
    # 否则 memory/relations/player_updates 按未修正版本落地，与改写后的叙事矛盾
    if tier == "heavy" and corrected_ok:
        output["state_updates"] = {}
    # 修正记录回写（LangGraph 只认节点返回值，apply_correction 对 state 的原地修改不生效）
    corrected = list(state.get("corrected", []))
    trace_id = state.get("last_trace", "")
    flags = list(state.get("flags", []))
    tension = state.get("tension", 0)
    if tier == "heavy":
        tension = 0  # 重修正后回落（防连续触发）
    return {
        "last_output": output,
        "tension": tension,
        "corrected": corrected,
        "last_trace": trace_id,
        "flags": flags,
    }


async def remember_node(state: GameState) -> dict:
    """记忆节点：STM 追加 + 晋升检查 + state_updates 合并回 GameState"""
    output = state.get("last_output") or {}
    updates = output.get("state_updates", {}) or {}

    # 1. 记忆追加：动态事件（LLM memory）优先 → 场景固定摘要兜底 → 叙事开头最后兜底。
    #    场景固定摘要每拍相同，若优先会覆盖玩家选择产生的事件，记忆面板只剩"定位"没有"进展"；
    #    叙事开头是环境描写不是事件，两者都只在 LLM memory 缺席时才启用。
    memory_adds = updates.get("memory_add", [])
    ps = state.get("meta", {}).get("plan_summary", {})
    scene_label = f"{ps.get('chapter_label', '')}·{ps.get('title', '')}".strip("·") or ""
    scene_memory = (ps.get("aftermath") or {}).get("memory_add", [])
    if not memory_adds and scene_memory:
        memory_adds = scene_memory
    # （无 narrative[:60] 兜底：与 writer 的事件提取统一，避免"环境复述"进记忆）
    # 可读时间标记
    era = state.get("era", {})
    time_label = f"{era.get('year', '?')}年·{era.get('season', '?')}" if era else ""
    st = copy.deepcopy(state)  # 深拷贝防嵌套 dict 原地改输入（浅拷贝别名隐患）
    # 只取最重要的 1 条（规范：每轮 1 条 STM 客观事实摘要）
    best = memory_adds[0] if memory_adds else (output.get("narrative", "")[:60])
    st = stm_append(st, str(best)[:80], scene_label=scene_label, time_label=time_label)
    # 满 6 晋升
    if len(st.get("memory", {}).get("stm", [])) >= 6:
        st = await promote_stm_to_ltm(st)

    # 2. 关系/信任增量合并（LLM 产出的 delta 叠加到当前值，钳位 0-100）
    relations = dict(state.get("relations", {}))
    for name, delta in (updates.get("relations_delta") or {}).items():
        try:
            old = relations.get(name, 50)  # 默认 50 中性
            relations[name] = max(0, min(100, old + int(delta)))
        except (TypeError, ValueError):
            pass

    trust = dict(state.get("trust", {}))
    for name, delta in (updates.get("trust_delta") or {}).items():
        try:
            old = trust.get(name, 50)  # 默认 50 中性
            trust[name] = max(0, min(100, old + int(delta)))
        except (TypeError, ValueError):
            pass

    # 2.4 初次相遇落地：first_impressions（新角色初见好感 10-60）→ relations/trust 写入 + encountered 登记。
    #    relations_delta 对已有角色默认 50 起点；初见则直接设 LLM 生成的初始值（不叠加 50）。
    encountered = list(state.get("encountered", []))
    # 泛型/即兴 NPC 不建关系（胖妇人/瘸腿老头等场景背景角色不进关系网）
    from .writer import GENERIC_NAMES, KNOWN_NAMES
    _known_set = set(KNOWN_NAMES)
    for name, imp in (updates.get("first_impressions") or {}).items():
        if not isinstance(imp, dict) or name in relations:
            continue
        if name in GENERIC_NAMES or (name not in _known_set and name not in set(state.get("character_states") or {})):
            continue  # 泛型或陌生即兴 NPC：不建关系
        try:
            relations[name] = max(0, min(100, int(imp.get("relation", 30))))
            trust[name] = max(0, min(100, int(imp.get("trust", 30))))
        except (TypeError, ValueError):
            relations[name] = 30
            trust[name] = 30
        if name not in encountered:
            encountered.append(name)

    # 2.5 角色软状态合并（自由大世界·决策9：LLM 管软状态 doing/goal/attitude/tags/notes）
    from .character_states import merge_character_soft_state
    try:
        merge_character_soft_state(st, updates.get("character_updates"))
    except Exception:
        logger.exception("角色软状态合并失败")
    # 双轨合并：attitude 一律从 relations 同步（关系网唯一权威，杜绝 attitude_delta
    # 与 relations_delta 并行演化导致的漂移——LLM 好感变化走 relations_delta 单通道）
    # 审查修复：同步对象必须是 deepcopy 副本 st（即返回值来源），改原始 state 会被 LangGraph 丢弃
    for nm, cst in (st.get("character_states") or {}).items():
        if isinstance(cst, dict):
            try:
                cst["attitude"] = max(0, min(100, int(relations.get(nm, cst.get("attitude", 50)))))
            except (TypeError, ValueError):
                pass

    # 3. 伏笔合并
    foreshadowing = list(state.get("foreshadowing", []))
    for fs in (updates.get("foreshadowing_add") or [])[:2]:
        if fs not in foreshadowing:
            foreshadowing.append(fs)

    # 4. 流言合并
    rumors = list(state.get("world_rumors", []))
    for r in (updates.get("rumors_add") or [])[:2]:
        if r not in rumors:
            rumors.append(r)
    # 只保留最近 10 条流言
    rumors = rumors[-10:]

    # 5. flags 合并（暗线/见证者/知情者——供 director aftermath.flow 岔路）
    flags = list(state.get("flags", []))
    for f in (updates.get("flags_add") or [])[:3]:
        if f not in flags:
            flags.append(f)

    ret = {
        "memory": st.get("memory", {}),
        "relations": relations,
        "trust": trust,
        "encountered": encountered,
        "foreshadowing": foreshadowing,
        "world_rumors": rumors,
        "flags": flags,
        # 角色软状态（LLM 声明 doing/goal/attitude/tags/notes）合并发生在 deepcopy 的 st 上，
        # 必须并入 ret 才会被 LangGraph 写回（否则每拍静默丢弃，态度面板永远停在种子值）。
        # 引擎事实（update_char_facts）在 _commit 里对 result 原地更新，此处只回带软状态合并结果。
        "character_states": st.get("character_states", {}),
        # 本拍在场名单（权威）：distance_map 键（按地点过滤的已登记角色/到点事件主角/名场面说话人）
        # + 本拍互动角色（LLM character_updates 声明的即兴人物，如卖茶妇人/说书老头——当拍在场）
        # 前端据此渲染在场面板：场景切换自动换人、新人物登场即时出现、旧人物随切换退出
        "present": sorted(set(
            (ps.get("distance_map") or {}).keys()
        ) | set((updates.get("character_updates") or {}).keys())),
    }
    # 6. 连续性子系统：每拍写回 scene_state（next_anchor/performed_lines/player_choice）
    ps = state.get("meta", {}).get("plan_summary")
    if ps:
        plan_now = ScenePlan.from_summary(ps)
        action = ""
        for h in reversed(state.get("history", [])):
            if h.get("user"):
                action = h["user"]
                break
        choice = resolve_player_choice(action, plan_now) if action else {}
        ret.update(after_beat(state, output, plan_now, player_choice=choice))
    return ret


# ═════════ 图构建 ═════════

def build_graph():
    """编译 LangGraph 图（Phase 2 完整链）"""
    g = StateGraph(GameState)
    g.add_node("director", director_node)
    g.add_node("narrate", narrate_node)
    g.add_node("validate", validate_node)
    g.add_node("rewrite", rewrite_node)
    g.add_node("corrector", corrector_node)
    g.add_node("remember", remember_node)

    g.add_edge(START, "director")
    g.add_edge("director", "narrate")
    g.add_edge("narrate", "validate")
    g.add_conditional_edges("validate", route_after_validate, {
        "rewrite": "rewrite",
        "forward": "corrector",
    })
    g.add_edge("rewrite", "narrate")  # 回到 narrate 重写
    g.add_edge("corrector", "remember")
    g.add_edge("remember", END)
    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ═════════ 外部入口（router 调用）═════════

def _prepare(state_dict: dict, action: str, tension: int) -> GameState:
    """prepare：前端回传 dict → GameState + 玩家动作入史 + 干预度累积（空 action = 开局）"""
    state = from_dict(state_dict)
    if action:
        state["history"] = state.get("history", []) + [{"user": action}]
    # 干预度累积（玩家所选选项的 tension；重修正后由 corrector 重置）
    if tension > 0:
        state["tension"] = max(0, min(100, state.get("tension", 0) + tension))
    # 审查修复：自由输入无选项 tension——按意图估算干预度，防「刺杀董卓」这类
    # 硬干预经自由输入绕过天意修正管线（§5.4 选项+自由输入并行）
    elif action:
        from .action_intent import parse_action
        _intent = parse_action(action, (state.get("era") or {}).get("location", ""),
                               known_names=set((state.get("relations") or {}).keys()))
        _est = 50 if (_intent or {}).get("type") == "战斗" else 0
        for _kw in ("刺杀", "行刺", "弑", "谋反", "篡位", "称帝", "烧粮", "挟天子"):
            if _kw in action:
                _est = max(_est, 70)
                break
        state["tension"] = max(0, min(100, state.get("tension", 0) + _est))
    return state


def _commit(result: dict, state: GameState, action: str) -> dict:
    """commit：assistant 叙事入库 + 自由沙盒世界推进。

    场景由 director 写 skeleton_pos（自由地点导航，不强制线性推进）；
    世界时间/玩家数据/事件队列由 world.py/player_data.py 推进。
    """
    # 追加 assistant 叙事回历史（存尾部 + scene_id；开局 action="" 也入库）
    narr = (result.get("last_output") or {}).get("narrative", "")
    if narr:
        # 头尾都留：>900 字时只存尾部会丢叙事开头（场景环境/在场者），拼接开头一小段 + 完整结尾
        if len(narr) > 900:
            stored = narr[:400].rstrip() + "……" + narr[-900:]
        else:
            stored = narr
        history = list(result.get("history", []))
        ps = (result.get("meta") or {}).get("plan_summary") or {}
        history.append({"assistant": stored, "scene_id": ps.get("scene_id", "")})
        result["history"] = history[-12:]  # 防无限增长，保留最近 12 轮
    # ── 自由大世界世界推进（每拍有玩家动作时）──
    # advance_world：日期推进 + 到点事件 + 历史压缩跳时 + 阶段切换（世界自主运转核心）。
    # player_data：玩家数据（LLM 声明 + 行动恢复 + 濒死）+ 玩家事件写回 + 成就。
    if action:
        from .world import advance_world, freshen_events
        from .player_data import (apply_player_updates, apply_recovery, check_achievements,
                                  check_vitals, apply_vital_bounce, apply_failure, check_darkline_grants)
        try:
            # 1. 世界推进（advance_world 收敛：日期/到点事件/跳时/阶段/周期/衰减）
            wd_before = result.get("world_date") or state.get("world_date") or {"year": 184, "month": 2, "day": 1}
            world_inc = advance_world(state, action, result)
            new_wd = world_inc["world_date"]
            result["world_date"] = new_wd
            result["world_events"] = world_inc["world_events"]
            result["new_briefing"] = bool(result.get("new_briefing") or world_inc["new_briefing"])
            result["scene_turns"] = world_inc["scene_turns"]
            if isinstance(result.get("era"), dict):
                result["era"]["chapter"] = world_inc["era"].get("chapter", (result["era"] or {}).get("chapter", "P1 黄金风起"))
                result["era"]["year"] = world_inc["era"].get("year", int(new_wd.get("year", 0)))
                result["era"]["season"] = world_inc["era"].get("season", (result["era"] or {}).get("season", ""))
                result["era"]["location"] = world_inc["era"].get("location", (result["era"] or {}).get("location", ""))
            # 玩家位置写回（前往X 到达目标地点 → player.location，view_scene 据此合成视野）
            if isinstance(result.get("player"), dict) and world_inc["era"].get("location"):
                result["player"]["location"] = world_inc["era"]["location"]
            # 角色事实更新（引擎管事实：到点事件在场角色位置/活动/存活）
            from .character_states import update_char_facts
            try:
                update_char_facts(result, world_inc.get("due_events") or [], new_wd,
                                  world_inc["era"].get("location", ""),
                                  prev_location=(state.get("player") or {}).get("location", ""))
            except Exception:
                logger.exception("角色事实更新失败")
            # 2. 玩家数据（LLM 声明的 player_updates + 行动恢复）
            # action 传入：恢复类动作的系统结算独家，剥离 LLM 重复声明的 stats_delta/coins_delta（审查⑨）
            result = apply_player_updates(result, result.get("last_output") or {}, action)
            # 失败代价（决策 12：不真死付代价）——应用 LLM failure / 兜底败北代价
            from .action_intent import parse_action
            _intent = parse_action(action, (result.get("era") or {}).get("location", ""),
                                   known_names=set((state.get("relations") or {}).keys()) | set((result.get("character_states") or {}).keys()))
            player = result.get("player") or {}
            player = apply_failure(player, result.get("last_output") or {}, action, _intent)
            # 失败的关系/信任代价写回 state 顶层（apply_failure 存 player._failure_* 中转）
            _fr = player.pop("_failure_relations", {}) or {}
            _ft = player.pop("_failure_trust", {}) or {}
            if _fr or _ft:
                rels = dict(result.get("relations") or state.get("relations") or {})
                for k, v in _fr.items():
                    rels[k] = max(0, min(100, rels.get(k, 50) + v))
                result["relations"] = rels
                trs = dict(result.get("trust") or state.get("trust") or {})
                for k, v in _ft.items():
                    trs[k] = max(0, min(100, trs.get(k, 50) + v))
                result["trust"] = trs
            player = apply_recovery(player, action, new_wd)
            # 濒死检测：单属性触底 → 写 vitals_alarm（下拍 writer 演后果）；
            # 上拍已注入警告仍触底（LLM 未恢复）→ 兜底回弹防卡死；
            # 三属性同时极端 → 死亡（alive=False，前端读档最近快照）。
            vitals = check_vitals(player)
            if vitals["dead"]:
                player["alive"] = False
                result["dead"] = True
            elif vitals["alarm"]:
                if state.get("vitals_alarm"):   # 上拍已注入过警告仍触底 → 兜底回弹
                    player = apply_vital_bounce(player)
                result["vitals_alarm"] = vitals["alarm"]
            else:
                result["vitals_alarm"] = ""     # 已脱离濒死 → 清除标记
            result["player"] = player
            # P1 暗线自由化（决策 17）：自由行动触发流亡/黄金/许家 → 授予资产+flag+伏笔
            # 必须在 result["player"] = player 之后：check_darkline_grants 改 result["player"].assets，
            # 若在其前调用会被后面的写回覆盖（审查：暗线 flag 触发但信物资产丢失）
            try:
                dl = check_darkline_grants(result, action)
                if dl.get("assets_add") or dl.get("flags_add"):
                    result["new_briefing"] = True  # 获得信物/同路人 → 世界留痕
            except Exception:
                logger.exception("暗线检查失败")
            # 3. 玩家行为写回世界：LLM 声明的 world_events_add → world_events 队列（strong，玩家引发）
            we_add = (result.get("last_output") or {}).get("state_updates", {}).get("world_events_add") or []
            if we_add:
                events = list(result.get("world_events") or [])
                for ev in we_add[:2]:
                    if not str(ev.get("event", "")).strip():
                        continue
                    events.append({
                        "event_id": f"player_{len(events)}_{new_wd.get('year', 0)}_{new_wd.get('month', 1)}",
                        "date": f"{new_wd.get('year', 0)}-{new_wd.get('month', 1):02d}",
                        "event": str(ev.get("event", ""))[:80],
                        "related_to_player": "strong",
                        "seen": False,
                        "source": "player",
                    })
                result["world_events"] = events[-50:]
                result["new_briefing"] = True   # 玩家引发的事件 → 简报
            # 4. 检查成就
            new_ach = check_achievements(result)
            if new_ach:
                result["new_achievements"] = new_ach
        except Exception:
            # 世界推进失败不影响主叙事，但必须留痕（审查②）：否则半更新状态静默返回、排障无从下手
            logger.exception("世界推进失败（半更新可能已返回）：action=%r world_date=%s", action, result.get("world_date"))
            # 可观测：错误标记进 meta，前端 phase 报告可见（P1 世界推进失败可观测）
            _meta = dict(result.get("meta") or {})
            _ps = dict(_meta.get("plan_summary") or {})
            _ps["world_error"] = f"世界推进异常（已跳过，不影响本拍叙事）"
            _meta["plan_summary"] = _ps
            result["meta"] = _meta
    return to_dict(result)


async def run_step(state_dict: dict, action: str = "", tension: int = 0) -> dict:
    """跑一轮（三分离）：prepare → 图执行 → commit → 简报合成"""
    state = _prepare(state_dict, action, tension)
    result = await get_graph().ainvoke(state)
    result = _commit(result, state, action)
    # A3 LLM 合成简报（§3.3）：本拍有世界动态 → 合成一段可读简报（含时间跨度+相关点）
    # 失败静默返回 ''，前端回退逐条事件列表
    if result.get("new_briefing"):
        fresh = [e for e in (result.get("world_events") or []) if not e.get("seen")][-6:]
        if fresh:
            from .writer import synthesize_briefing
            result["briefing"] = await synthesize_briefing(
                fresh, state.get("world_date"), result.get("world_date")
            )
            # 简报事件：不在引擎侧标 seen——由 play.py 发出 briefing SSE 后再标，
            # 否则前端筛"未读"恒空、简报弹窗永不触发（修复死代码）。
            # 把已入简报的 event_id 透出，供 play.py 标 seen。
            result["_briefing_ids"] = [e.get("event_id") for e in fresh if e.get("event_id")]
    return result
