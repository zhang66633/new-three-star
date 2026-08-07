# -*- coding: utf-8 -*-
"""
LangGraph 图定义（新三国 星空 · 引擎主图）
==========================================
Phase 1: director → narrate → END（最小链）
Phase 2: + validate ⇄ narrate(重写) → corrector → remember
"""
import logging

from langgraph.graph import StateGraph, START, END

from .state import GameState, new_game_state, from_dict, to_dict
from .director import choose_scene, ScenePlan
from .writer import narrate

logger = logging.getLogger(__name__)


# ═════════ 节点实现 ═════════

def director_node(state: GameState) -> dict:
    """选择场景，plan 可序列化摘要存入 meta（ScenePlan 对象不落 state）"""
    plan = choose_scene(state)
    return {
        "meta": {
            **state.get("meta", {}),
            "plan_summary": {
                "scene_id": plan.scene_id,
                "next_pos": plan.next_pos,
                "chapter_label": plan.chapter_label,
                "title": plan.title,
                "setting": plan.setting,
                "world_normal": plan.world_normal,
                "player_pov": plan.player_pov,
                "locked_lines": plan.locked_lines,
                "distance_map": plan.distance_map,
            },
        },
        "skeleton_pos": plan.scene_id,
    }


async def narrate_node(state: GameState) -> dict:
    """生成叙事 + 选项"""
    # 从 meta 的 plan_summary 重建 ScenePlan（或直接选场景）
    ps = state.get("meta", {}).get("plan_summary")
    if ps:
        plan = ScenePlan.from_summary(ps)
    else:
        plan = choose_scene(state)
    output = await narrate(state, plan)
    # assistant 回复入历史（图内更新，持久化）
    history = list(state.get("history", []))
    if output.get("narrative"):
        history.append({"assistant": output["narrative"]})
    return {
        "last_output": output,
        "turn": state.get("turn", 0) + 1,
        "history": history,
    }


# ═════════ 图构建 ═════════

def build_graph():
    """编译 LangGraph 图（Phase 1 最小链）"""
    g = StateGraph(GameState)
    g.add_node("director", director_node)
    g.add_node("narrate", narrate_node)
    g.add_edge(START, "director")
    g.add_edge("director", "narrate")
    g.add_edge("narrate", END)
    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ═════════ 外部入口（router 调用）═════════

async def run_step(state_dict: dict, action: str = "") -> dict:
    """跑一轮：输入前端回传 state + 玩家动作 → 输出更新后的 state + NarrativeOutput

    Phase 1 返回非流式 dict；Phase 4 改为 astream 透出 SSE。
    """
    state = from_dict(state_dict)
    # 玩家动作入历史（空 action = 开局；由 narrate_node 追加 assistant）
    if action:
        state["history"] = state.get("history", []) + [{"user": action}]
    result = await get_graph().ainvoke(state)
    # 场景推进：玩家提交选择后（action 非空），按场景 aftermath.flow 更新 skeleton_pos
    if action:
        ps = result.get("meta", {}).get("plan_summary")
        if ps and ps.get("next_pos"):
            result["skeleton_pos"] = ps["next_pos"]
    return to_dict(result)
