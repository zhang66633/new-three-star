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

from .state import GameState, new_game_state, from_dict, to_dict
from .director import choose_scene, ScenePlan, fame_should_block_advance, CHAPTER_CLOCK, _SEASON_ORDER
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
    # 时代状态写回（P1_s3_leap 等场景推进年份/季节/地点）
    era = dict(state.get("era", {}))
    if plan.year:
        era["year"] = plan.year
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
                "prep_actions": plan.prep_actions,
                "atmo": plan.atmo,
                "music": plan.music,
                "flags_on_enter": plan.flags_on_enter,
                "aftermath": plan.aftermath,
                "min_turns": plan.min_turns,
            },
            # 记录上轮时空（供 validate P0 时间连续性检测）
            "prev_era": dict(state.get("era", {})),
        },
        "era": era,
        "flags": flags,
        "skeleton_pos": plan.scene_id,
        "retry_count": 0,  # 每轮重置重写计数
        "turn": state.get("turn", 0) + 1,  # turn 在导演层自增（每真实回合一次，不被重写污染）
        # 连续性子系统：场景变化时初始化 scene_state（开局 scene_state=None 也触发首拍登记）
        **({"scene_state": on_scene_entry(state, plan)["scene_state"]}
           if not isinstance(state.get("scene_state"), dict)
           or (state.get("scene_state") or {}).get("scene_id") != plan.scene_id else {}),
        # 世界时钟：章节切换时初始化（每章一条时间轴，见 director.CHAPTER_CLOCK）
        **({"world_clock": {"chapter": plan.chapter, **CHAPTER_CLOCK.get(plan.chapter, {"season": "春", "turns_left": 3})}}
           if (state.get("world_clock") or {}).get("chapter") != plan.chapter else {}),
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
    """commit：场景推进（aftermath.flow 更新 skeleton_pos/scene_turns）+ assistant 叙事入库。

    场景推进在图中 director 已写 skeleton_pos=plan.scene_id 的基础上做驻留计数：
    min_turns 满则推进到 next_pos，否则驻留多拍探索。
    assistant 存尾部 + scene_id，开局（action=""）也入库供第 2 回合接续锚点。
    """
    if action:
        ps = result.get("meta", {}).get("plan_summary")
        # END 哨兵（占位自循环安全阀）不推进 skeleton_pos：registry 无 'END' 场景，
        # 盲写会回退 P1_s1_rain 造成"带记忆的伪重开"。保持当前场景挂起。
        if ps and ps.get("next_pos") and ps.get("next_pos") != "END":
            scene_turns = state.get("scene_turns", 1)
            min_turns = ps.get("min_turns", 1)
            if scene_turns >= min_turns:
                next_pos = ps["next_pos"]
                # 名场面门禁（世界时钟）：时节未到 → 驻留攒就位；时节到未就位 → 错过失败
                gate = fame_should_block_advance(next_pos, state)
                if gate == "":
                    result["skeleton_pos"] = next_pos
                    result["scene_turns"] = 1  # 进入下一场景，驻留计数重置
                elif gate == "miss":
                    # 错过关键名场面 → 标记失败（前端提示失败 + 读档回上个名场面重打）
                    result["skeleton_pos"] = next_pos
                    result["scene_turns"] = 1
                    result["fame_missed"] = next_pos
                # gate == "wait"：名场面时节未到（还没发生），驻留当前场景攒就位（不推进）
            else:
                # skeleton_pos 保持当前场景（director_node 已写 plan.scene_id），续生成探索拍
                result["scene_turns"] = scene_turns + 1
    # 世界时钟推进：每拍（有玩家动作）消耗世界时间；turns_left 扣尽则时节前进
    if action:
        wc = dict(state.get("world_clock") or {})
        if wc:
            tl = int(wc.get("turns_left", 0)) - 1
            if tl <= 0:
                seasons = list(_SEASON_ORDER.keys())
                cur = wc.get("season", "春")
                nxt = seasons[(seasons.index(cur) + 1) % 4] if cur in _SEASON_ORDER else "春"
                wc["season"] = nxt
                wc["turns_left"] = 3  # 每时节固定行动预算
            else:
                wc["turns_left"] = tl
            result["world_clock"] = wc
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
    return to_dict(result)


async def run_step(state_dict: dict, action: str = "", tension: int = 0) -> dict:
    """跑一轮（三分离）：prepare → 图执行 → commit"""
    state = _prepare(state_dict, action, tension)
    result = await get_graph().ainvoke(state)
    return _commit(result, state, action)
