# -*- coding: utf-8 -*-
"""
LangGraph 图定义（新三国 星空 · 引擎主图）
==========================================
Phase 1: director → narrate → END
Phase 2: director → narrate ⇄ validate(重写≤2) → corrector(按tension) → remember → END
"""
import logging
from typing import Literal

from langgraph.graph import StateGraph, START, END

from .state import GameState, new_game_state, from_dict, to_dict
from .director import choose_scene, ScenePlan
from .writer import narrate
from .validator import validate
from .corrector import classify_tension, apply_correction
from .remember import stm_append, promote_stm_to_ltm, retrieve_memories

logger = logging.getLogger(__name__)

MAX_RETRY = 2


# 流式回调：ContextVar 请求级作用域（不入 state，避免 JSON 序列化失败）
# 用 contextvars 而非进程全局 —— 多个并发 /play 请求互不串流
import contextvars as _cv

_stream_cb_var: _cv.ContextVar = _cv.ContextVar("stream_cb", default=None)
_options_cb_var: _cv.ContextVar = _cv.ContextVar("options_cb", default=None)


def set_stream_cb(cb):
    """设置当前请求的流式回调（ContextVar，任务/请求级隔离）"""
    _stream_cb_var.set(cb)


def get_stream_cb():
    return _stream_cb_var.get()


def clear_stream_cb():
    _stream_cb_var.set(None)


def set_options_cb(cb):
    _options_cb_var.set(cb)


def get_options_cb():
    return _options_cb_var.get()


def clear_options_cb():
    _options_cb_var.set(None)


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
                "atmo": plan.atmo,
                "music": plan.music,
            },
            # 记录上轮时空（供 validate P0 时间连续性检测）
            "prev_era": dict(state.get("era", {})),
        },
        "era": era,
        "skeleton_pos": plan.scene_id,
        "retry_count": 0,  # 每轮重置重写计数
        "turn": state.get("turn", 0) + 1,  # turn 在导演层自增（每真实回合一次，不被重写污染）
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
    memory_pack = retrieve_memories(state, f"{plan.setting} {player_action}")

    # SSE 流式回调（从全局读取，不入 state）
    cb = get_stream_cb()
    output = await narrate(state, plan, memory_pack=memory_pack, on_chunk=cb)
    # 立即回调 options（不等 validate/corrector/remember —— 减少前端等待）
    opts_cb = get_options_cb()
    if opts_cb and output.get("options"):
        try:
            opts_cb(output["options"])
        except Exception:
            pass
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

    # 1. 记忆追加
    memory_adds = updates.get("memory_add", [])
    if not memory_adds and output.get("narrative"):
        # 叙事前 60 字作 STM 条目（含场景信息，去重由 stm_append 的 id 哈希处理）
        memory_adds = [output["narrative"][:60]]
    # 场景标记（供前端记忆抽屉显示场景上下文）
    ps = state.get("meta", {}).get("plan_summary", {})
    scene_label = f"{ps.get('chapter_label', '')}·{ps.get('title', '')}".strip("·") or ""
    # 可读时间标记
    era = state.get("era", {})
    time_label = f"{era.get('year', '?')}年·{era.get('season', '?')}" if era else ""
    st = dict(state)
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

    return {
        "memory": st.get("memory", {}),
        "relations": relations,
        "trust": trust,
        "foreshadowing": foreshadowing,
        "world_rumors": rumors,
        "flags": flags,
    }


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

async def run_step(state_dict: dict, action: str = "", tension: int = 0, stream_cb=None) -> dict:
    """跑一轮：输入前端回传 state + 玩家动作 + 所选选项干预度 → 输出更新后的 state

    stream_cb: 可选回调（text: str）→ LLM chunk 逐块透出（SSE 流式）
    """
    state = from_dict(state_dict)
    # 玩家动作入历史（空 action = 开局；assistant 输出在图跑完后追加）
    if action:
        state["history"] = state.get("history", []) + [{"user": action}]
    # 干预度累积（玩家所选选项的 tension；重修正后由 corrector 重置）
    if tension > 0:
        state["tension"] = max(0, min(100, state.get("tension", 0) + tension))
    # 流式回调：请求级 ContextVar（不入 state），完成后清理
    if stream_cb:
        set_stream_cb(stream_cb)
    try:
        result = await get_graph().ainvoke(state)
    finally:
        clear_stream_cb()
        clear_options_cb()
    # 场景推进：玩家提交选择后（action 非空），按场景 aftermath.flow 更新 skeleton_pos
    if action:
        ps = result.get("meta", {}).get("plan_summary")
        if ps and ps.get("next_pos"):
            result["skeleton_pos"] = ps["next_pos"]
    # 追加 assistant 叙事回历史（供 writer build_messages 的"最近6轮"看到上轮输出）
    if action:
        narr = (result.get("last_output") or {}).get("narrative", "")
        if narr:
            history = list(result.get("history", []))
            history.append({"assistant": narr[:600]})
            result["history"] = history[-12:]  # 防无限增长，保留最近 12 轮
    return to_dict(result)
