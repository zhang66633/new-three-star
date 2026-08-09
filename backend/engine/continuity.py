# -*- coding: utf-8 -*-
"""
Continuity（连续性子系统 · 一等公民）
====================================
定位：把"上一拍状态"落成持久化结构化字段 scene_state，取代一切从被窗口化的历史
（存 12 轮、喂 6 条）反推"已演出"的机制——prev_tail 文本锚 / _is_first_beat 历史扫描
/ 规则 prose 判定。

本文件是"上一拍状态"的唯一读写点：生成侧（writer/build_messages/context）与校验侧
（validator）都从这里取事实，不再有第二份"已演出"推断。

scene_state 结构：
    scene_id: str               权威场景边界（与 skeleton_pos 同步；prompt 可见）
    first_beat_done: bool       首拍是否完成 —— 取代 _is_first_beat 历史扫描
    beat_index: int             本场景第几拍（1 起）
    performed_events: list      本场景已演出事件（去重键）—— 取代"从历史推断已演出"
    performed_lines: list       已逐字演出的锁定台词（去重键）
    answered_questions: list    已权威回答的玩家提问（防 Q&A 重复）
    pov_consumed: list          已消费的 player_pov 条目（非首拍不再全量注入）
    present_names: list         本拍在场角色（确定性）
    player_choice: dict         上拍玩家选择 {text, effect, option_index, tension, has_effect}
    next_anchor: str            上拍结尾锚点（最后一句完整句）—— 取代 prev_tail 200 字文本
    transition_note: str        跨场景过渡摘要（换场景时生成，只注入一次）

迁移策略：scene_state 缺失（旧存档 / 尚未接线）时回退现有历史扫描逻辑，保证行为不变；
接线完成后（nodes 接入 on_scene_entry/after_beat，见重构 Step 2/3）走结构化路径。
"""
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import GameState
    from .director import ScenePlan


# ═════════ 读侧：连续性事实查询（迁移版：有字段读字段，无则回退历史扫描）═════════

def _is_first_beat(state, plan) -> bool:
    """本场景是否首拍。

    优先读 scene_state.first_beat_done（接线后由 after_beat 写回）；缺失（旧存档/未接线）
    回退历史扫描（现有行为）保证兼容。
    """
    ss = state.get("scene_state") or {}
    if isinstance(ss, dict) and ss.get("scene_id") == plan.scene_id and "first_beat_done" in ss:
        return not ss["first_beat_done"]
    return not any(
        h.get("assistant") and h.get("scene_id") == plan.scene_id
        for h in state.get("history", [])
    )



def in_scene_names(state, plan) -> set:
    """在场角色单一来源（present 语义：锁定台词说话人 + distance_map + 关系>40）。

    供 context panel 渲染；extract 的"互动角色"是另一语义（interact），不在此统一。
    """
    names = set()
    for line in plan.locked_lines:
        sp = line.get("speaker", "")
        if sp:
            names.add(sp)
    for name in plan.distance_map:
        names.add(name)
    relations = state.get("relations", {})
    for name, v in relations.items():
        if v > 40:
            names.add(name)
    return names


# ═════════ 写侧：scene_state 生命周期（Step 2 接线到 director/remember 节点）═════════

def on_scene_entry(state, plan) -> dict:
    """场景入场：初始化 scene_state。由 director 节点在 scene_id 变化时调用（Step 2 接线）。

    跨场景时用上一场景的结尾锚点生成 transition_note（只注入一次，取代跨场景散文透传）。
    返回 {"scene_state": {...}}（节点返回值，LangGraph 合并回 state）。
    """
    transition_note = ""
    old_ss = state.get("scene_state") or {}
    if isinstance(old_ss, dict) and old_ss.get("scene_id") and old_ss.get("scene_id") != plan.scene_id:
        anchor = (old_ss.get("next_anchor") or "").strip()
        if anchor:
            transition_note = f"你从上一场景一路辗转至此（上场景收尾：……{anchor}）"
    return {"scene_state": {
        "scene_id": plan.scene_id,
        "first_beat_done": False,
        "beat_index": 1,
        "performed_events": [],
        "performed_lines": [],
        "answered_questions": [],
        "pov_consumed": [],
        "present_names": sorted(in_scene_names(state, plan)),
        "player_choice": {},
        "next_anchor": "",
        "transition_note": transition_note,
    }}


def after_beat(state, output, plan, player_choice: dict = None) -> dict:
    """每拍后更新 scene_state。由 remember 节点调用（Step 2 接线）。

    骨架版提取：锁定台词逐字出现记 performed_lines；叙事末句记 next_anchor。
    结构化 performed_events 的强化提取在 Step 4（memory events[] 单一事件源）。
    """
    narrative = (output or {}).get("narrative", "") or ""
    ss = dict(state.get("scene_state") or {})
    if ss.get("scene_id") != plan.scene_id:
        ss = on_scene_entry(state, plan)["scene_state"]  # 跨场景则重建（含首拍置位）

    # next_anchor：叙事最后一句完整句（只注入一次，取代 prev_tail 200 字文本）
    last = _last_sentence(narrative)
    if last:
        ss["next_anchor"] = last

    # performed_lines：锁定台词逐字出现记入（去重键 = 台词文本）
    performed = set(ss.get("performed_lines") or [])
    for line in plan.locked_lines:
        t = line.get("text", "")
        if t and t in narrative:
            performed.add(t)
    ss["performed_lines"] = sorted(performed)

    # performed_events：当拍 memory_add（LLM events 摘要 / 兜底事件句）进已演出事件，
    # 供连续性块"已演出事件"注入 → 后续拍不重演
    new_events = ((output or {}).get("state_updates") or {}).get("memory_add") or []
    evts = list(ss.get("performed_events") or [])
    for ev in new_events:
        if ev and ev not in evts:
            evts.append(ev)
    ss["performed_events"] = evts[-8:]

    ss["first_beat_done"] = True
    ss["beat_index"] = int(ss.get("beat_index", 0)) + 1
    # 只写真实玩家选择（开局 action="" 或空文本不写）
    if player_choice and player_choice.get("text"):
        ss["player_choice"] = player_choice
    # qualifications：玩家选中行动（含 prep_actions 准备期行动盘）的 grants 累积就位条件
    choice = player_choice or {}
    idx = choice.get("option_index")
    if isinstance(idx, int) and 0 <= idx < len(plan.options):
        grants = plan.options[idx].get("grants") or []
        if grants:
            quals = list(ss.get("qualifications") or [])
            for g in grants:
                if g and g not in quals:
                    quals.append(g)
            ss["qualifications"] = quals
    return {"scene_state": ss}


def locked_lines_note(state, plan) -> dict:
    """锁定台词注入信息（数据驱动，取代"全量展示+禁止引用"的矛盾措辞）。

    返回 {status, must_perform[]}：首拍全量逐字；非首拍只注入 performed_lines 里
    还没演出的项（已演出项从 prompt 消失，LLM 无从重演）。
    """
    first = _is_first_beat(state, plan)
    ss = state.get("scene_state") or {}
    performed = set(ss.get("performed_lines") or []) if isinstance(ss, dict) else set()
    all_lines = [l.get("text", "") for l in plan.locked_lines if l.get("text")]
    if first:
        return {"status": "opening", "must_perform": all_lines}
    return {"status": "ongoing", "must_perform": [t for t in all_lines if t not in performed]}


def render_continuity_block(state, plan) -> str:
    """唯一连续性块：注入上一拍结构化事实 + 锁定台词数据驱动，取代 prev_tail 文本锚、
    _is_first_beat 历史扫描的 prose 化与规则 1/16/17 的否定式反例。

    全正向表述：不写"严禁重演 X"（负向提示会 priming 被禁内容），而是列出
    已演出事实 + 未演出锁定台词，让"只写本拍新发生的事"成为数据驱动的自然结果。
    """
    ss = state.get("scene_state") or {}
    first = _is_first_beat(state, plan)
    lines = ["【连续性 · 上一拍（只读事实，本拍从这里继续）】"]

    if isinstance(ss, dict) and ss.get("scene_id") == plan.scene_id:
        beat = int(ss.get("beat_index", 1))
        lines.append(f"· 场景：{plan.chapter_label} · {plan.title} · 第 {beat}/{plan.min_turns} 拍（{'首拍，只开场' if first else '首拍已完成，续接推进'}）")
        choice = ss.get("player_choice") or {}
        if choice.get("text"):
            eff = f" → 承诺后果：{choice['effect']}" if choice.get("effect") else ""
            lines.append(f"· 上拍玩家选择：「{choice['text']}」{eff}")
        anchor = (ss.get("next_anchor") or "").strip()
        if anchor:
            lines.append(f"· 上拍结尾：……{anchor}")
        tn = (ss.get("transition_note") or "").strip()
        if tn:
            lines.append(f"· 场景过渡：{tn}")
        events = ss.get("performed_events") or []
        if events:
            lines.append("· 已演出事件：" + "；".join(events))
    else:
        lines.append(f"· 场景：{plan.chapter_label} · {plan.title} · 第 1/{plan.min_turns} 拍（首拍，只开场）")

    note = locked_lines_note(state, plan)
    if note["must_perform"]:
        shown = [f"[{l['speaker']}]{l['text']}" for l in plan.locked_lines if l.get("text") in note["must_perform"]]
        lines.append("· 本拍可出现的锁定台词：" + "；".join(shown))

    if first:
        lines.append("· 本拍任务：只交代开场情境与在场者，把路线/方向选择留给玩家选项——不替玩家做未选择的行为，不提前开启逃亡/战斗/暗线。")
    else:
        lines.append("· 本拍任务：从上一拍结尾继续推进，只写本拍新发生的事。")
    return "\n".join(lines)


def resolve_player_choice(action: str, plan) -> dict:
    """玩家动作 → 结构化 player_choice：匹配场景选项回填承诺后果。

    由 narrate 节点调用（Step 2 接线）。自由输入则 {text, effect:"", has_effect:False}。
    """
    action = (action or "").strip()
    for i, opt in enumerate(plan.options or []):
        if opt.get("text") and opt["text"].strip() == action:
            return {
                "text": action,
                "effect": opt.get("effect", ""),
                "option_index": i,
                "tension": opt.get("tension", 0),
                "has_effect": bool(opt.get("effect")),
            }
    return {"text": action, "effect": "", "option_index": -1, "tension": 0, "has_effect": False}


# ═════════ 内部工具 ═════════

def _last_sentence(text: str) -> str:
    """叙事最后一句完整句（next_anchor 用）；无句读时取末尾 80 字。"""
    t = text.strip()
    if not t:
        return ""
    m = re.findall(r'[^。！？]*[。！？]', t)
    return m[-1].strip() if m else t[-80:]
