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
from .director import choose_scene, ScenePlan, _location_state
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
    """选择场景，plan 可序列化摘要存入 meta（ScenePlan 对象不落 state）

    era 写回：把场景的 year/season/location 同步进 state.era，
    供前端 eraLabel、validator P0 时间连续性、writer 时空面板、remember 时间标签使用。
    """
    plan = choose_scene(state)
    # 时代状态写回（统一时钟：era.year = max(场景静态年, 世界年)，回访不回退）
    era = dict(state.get("era", {}))
    wd_year = (state.get("world_date") or {}).get("year", 0)
    era["year"] = max(int(plan.year or 0), int(wd_year or 0)) or 0
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
        "skeleton_pos": plan.scene_id,
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
    plan = ScenePlan.from_summary(ps) if ps else choose_scene(state)

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
        "foreshadowing": foreshadowing,
        "world_rumors": rumors,
        "flags": flags,
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
    # ── 自由沙盒世界推进（每拍有玩家动作时）──
    # 推进世界日期 + 应用玩家数据（LLM 声明）+ 生成世界事件 + 检查成就。
    if action:
        from .world import advance_date, action_days, should_generate_events, generate_events
        from .player_data import apply_player_updates, apply_recovery, check_achievements, check_vitals, apply_vital_bounce
        try:
            wd = result.get("world_date") or state.get("world_date") or {"year": 184, "month": 2, "day": 1}
            # 1. 推进日期（按行动类型耗时；location 供赶路距离解析——当前地点）
            days = action_days(action, [], (result.get("era") or {}).get("location", ""))
            new_wd = advance_date(wd, days)
            # 前往更晚场景：world_date 快进到目标场景年代（吸收旅途/时代跳跃，如 184→189 洛阳）
            ps = (result.get("meta") or {}).get("plan_summary") or {}
            scene_year = int(ps.get("year") or 0)
            if scene_year > int(new_wd.get("year", 0)):
                old_wd = dict(new_wd)
                new_wd = dict(new_wd)
                new_wd["year"] = scene_year
                # 月份对齐场景季节（如秋→9 月）：防 189-02 仍判 P1 黄金乱起（世界常态不切换）/
                # 季节与日期矛盾（显示"秋"却 2 月）——时代快进要真的进入那个时代
                season_month = {"春": 3, "夏": 6, "秋": 9, "冬": 12}.get(ps.get("season") or "")
                if season_month:
                    new_wd["month"] = season_month
                # 时代快进：补 (旧, 新] 期间的时间线事件（你错过的天下事）→ 简报，
                # 世界真正"前进了"而不只是年份数字变了（黄金溃兵/董卓进京等都被吸收）
                from .world import period_events
                period = period_events(old_wd, new_wd)
                if period:
                    events = list(result.get("world_events") or state.get("world_events") or [])
                    seen_ids = {e.get("event_id") for e in events}
                    for ev in period:
                        if ev.get("event_id") not in seen_ids:
                            events.append(ev)
                    result["world_events"] = events[-50:]
                    result["new_briefing"] = True
            result["world_date"] = new_wd
            # 统一时钟：era.year 跟随 world_date（单调向前，回访不回退）
            if isinstance(result.get("era"), dict):
                result["era"]["year"] = int(new_wd.get("year", 0))
            # 2. 应用玩家数据（LLM 声明的 player_updates + 行动恢复）
            result = apply_player_updates(result, result.get("last_output") or {})
            player = result.get("player") or {}
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
            # 3. 生成世界事件（移动时 + 周期）
            moved = should_generate_events(state, result)
            # 驻留计数：移动则重置（新地点第 1 拍），否则递增——供周期事件判定
            result["scene_turns"] = 1 if moved else int(result.get("scene_turns") or state.get("scene_turns") or 1) + 1
            if moved:
                new_events = generate_events(state, new_wd, moved, location=(result.get("era") or {}).get("location", ""))
                if new_events:
                    events = list(result.get("world_events") or state.get("world_events") or [])
                    seen_ids = {e.get("event_id") for e in events}
                    for ev in new_events:
                        if ev.get("event_id") not in seen_ids:
                            events.append(ev)
                    result["world_events"] = events[-50:]  # 只保留最近 50 条
                    result["new_briefing"] = True  # 前端标记有新简报
            # 历史压缩（§1.3）：玩家驻留空闲（休息/等待）且距下一时间线事件过远 → 跳时
            # 门控：主动行动（对话/打听/赶路/买卖）不跳时，避免打断进行中的互动
            from .world import next_timeline_skip, is_idle_action
            skip = next_timeline_skip(new_wd) if is_idle_action(action) else None
            if skip:
                new_wd = skip["date"]
                result["world_date"] = new_wd
                events = list(result.get("world_events") or state.get("world_events") or [])
                events.append(skip["event"])
                result["world_events"] = events[-50:]
                result["new_briefing"] = True
                if isinstance(result.get("era"), dict):
                    result["era"]["year"] = int(new_wd.get("year", 0))
            # 离开期间简报（B-⑩）：休息/赶路跨越大段时间（≥3 天）且未生成事件/未跳时
            # → 补 (推进前, 当前] 期间的时间线事件，玩家醒来/落地后简报"期间天下事"
            if days >= 3 and not moved and not skip:
                from .world import period_events
                period = period_events(wd, new_wd)
                if period:
                    events = list(result.get("world_events") or state.get("world_events") or [])
                    seen_ids = {e.get("event_id") for e in events}
                    for ev in period:
                        if ev.get("event_id") not in seen_ids:
                            events.append(ev)
                    result["world_events"] = events[-50:]
                    result["new_briefing"] = True
            # 玩家行为写回世界：LLM 声明的 world_events_add → world_events 队列（strong，玩家引发）
            we_add = (result.get("last_output") or {}).get("state_updates", {}).get("world_events_add") or []
            if we_add:
                events = list(result.get("world_events") or state.get("world_events") or [])
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
            # 事件相关度衰减（B-①）：strong（与你有关）事件随日期推移淡出（>6 月降 weak）
            if result.get("world_events"):
                from .world import freshen_events
                result["world_events"] = freshen_events(result["world_events"], new_wd)
            # 4. 检查成就
            new_ach = check_achievements(result)
            if new_ach:
                result["new_achievements"] = new_ach
        except Exception:
            pass  # 世界推进失败不影响主叙事
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
    return result
