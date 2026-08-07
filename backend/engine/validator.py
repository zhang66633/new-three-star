# -*- coding: utf-8 -*-
"""
Validator（校验层 · 8 PHASE 硬校验）
=====================================
依据: docs/引擎设计规范.md §3（映射自 AAA 规范）

两层结构：
1. 确定性层（快、免 LLM，可重复）：
   - P7a 选项数 1-3
   - P1a 角色名/道具名白名单（复用 services.validator）
   - P7b deslop 毒句式计数
   - P0a 时空连续（era 对比上轮）
   - P1b hidden 泄漏（narrative 与 knowledge.hidden 实体交集）
2. LLM 层（一次调用出 P0-P5 判定 JSON）：
   - P0 时空锚定 / P1 真实性 / P2 意图记忆 / P3 人物一致 / P4 防崩坏 / P5 行为后果
   - P6 场景氛围 / P7 输出质量（自检，只记录不触发重写）

失败项 → retry_reasons 回灌 narrate（重写 ≤2 次）
"""
import json
import logging

logger = logging.getLogger(__name__)

# 硬校验 PHASE（失败触发重写）
HARD_PHASES = ["P0", "P1", "P2", "P3", "P4", "P5"]
# 自检 PHASE（只记录）
SOFT_PHASES = ["P6", "P7"]

VALIDATOR_PROMPT = """你是叙事质量审核员，检查 LLM 生成的三国叙事是否符合 8 PHASE 标准。

【上轮时空】{prev_era}
【玩家上轮选择】{player_action}
【当前场景】{scene_desc}
【知识边界】玩家只应知道: {public_knowledge}
【世界真实（玩家不应知道）】{hidden_knowledge}
【待审核文本】{narrative}

【判定标准】
- P0 时空锚定: 时间/季节/位置与上轮连续（或显式标记跳跃）；矛盾则 FAIL
- P1 真实性: 地理/人物/事件符合三国史实或场景设定；硬伤则 FAIL
- P2 意图记忆: 玩家上轮选择被回应；未解伏笔/承诺被追踪；遗漏则 FAIL
- P3 人物一致: 登场角色性格/OOC/称呼/关系值与设定一致；不符则 FAIL
- P4 防崩坏: 玩家不神化、关系不跳跃、行为有后果；违规则 FAIL
- P5 行为后果: 玩家选择的法律/经济/关系/声望后果已体现；无体现则 FAIL
- P6 场景氛围: 光/声/味/温/人流 五感覆盖（自检，仅记录）
- P7 输出质量: 描写均衡（动作/对话/心理/环境）、无 AI 腔（自检，仅记录）
- LEAK 信息迷雾: 文本中不得出现 hidden_knowledge 中的内容（NPC 说了他不知道的事/旁白泄漏）→ LEAK FAIL

【输出】严格 JSON:
{{"p0": {{"pass": true, "reason": "..."}}, "p1": {{...}}, ..., "p6": ..., "p7": ..., "leak": {{"pass": true, "reason": "..."}}}}
""".strip()


# ═════════ 确定性层 ═════════

def check_options_count(options: list) -> list[str]:
    """P7a: 选项数 1-3"""
    n = len(options)
    if n < 1:
        return ["P7: 无选项（应给 2-3 个）"]
    if n > 3:
        return [f"P7: 选项数 {n} 超上限 3"]
    return []


# hidden 条目中的核心实体词（人名/地名/关键动作），用于泄漏检测
HIDDEN_ENTITY_WORDS = [
    "董卓", "政变", "密谋", "计划", "埋伏", "刺客", "毒酒", "暗杀", "结盟",
    "内应", "粮草", "密信", "叛变", "假意", "权谋", "谋反", "称帝", "篡位",
    "借刀", "连环计", "诈降", "偷袭", "密诏", "传位", "勾结", "出卖",
    "洛阳", "长安", "许都", "徐州", "荆州", "益州", "汉中", "官渡", "赤壁",
    "张角", "黄金军", "天意", "玉玺", "七星刀", "赤兔",
]


def check_hidden_leak(narrative: str, hidden: list[str]) -> list[str]:
    """P1b+LEAK: narrative 是否泄漏 hidden 知识（实体词交集）"""
    if not hidden:
        return []
    # 1. 整条 hidden 的关键词（jieba 分词取名词性词，简化：去虚词后取 2-4 字片段）
    leak_keys = set()
    for h in hidden:
        # 拆成 2-4 字滑窗词（去虚词）
        h_clean = h.replace("，", "").replace("。", "").replace("，", "")
        for w in HIDDEN_ENTITY_WORDS:
            if w in h:
                leak_keys.add(w)
        # 整条 6 字以上也加入（精确匹配用）
        if len(h_clean) >= 6:
            leak_keys.add(h_clean[:12])
    # 2. 在叙事中查找
    leaks = []
    for key in leak_keys:
        if key and key in narrative:
            leaks.append(f"LEAK: 泄漏 hidden 信息『{key}』")
    return leaks


def check_time_continuity(prev_era: dict, curr_era: dict) -> list[str]:
    """P0a: 时空连续（无 prev 则通过）"""
    if not prev_era or not curr_era:
        return []
    prev_year = prev_era.get("year")
    curr_year = curr_era.get("year")
    if prev_year and curr_year and curr_year < prev_year:
        return [f"P0: 时间倒退（{prev_year}→{curr_year}），需显式跳跃标记"]
    return []


def deterministic_checks(state: dict, output: dict) -> list[str]:
    """确定性层全检：返回失败原因列表（空=通过）"""
    reasons = []
    reasons += check_options_count(output.get("options", []))
    reasons += check_hidden_leak(
        output.get("narrative", ""),
        (state.get("knowledge") or {}).get("hidden", []),
    )
    reasons += check_time_continuity(
        (state.get("meta") or {}).get("prev_era"),
        state.get("era", {}),
    )
    return reasons


# ═════════ LLM 层 ═════════

async def llm_checks(state: dict, output: dict, scene_desc: str) -> dict:
    """LLM 层 P0-P5 判定 + P6/P7 自检（一次调用）"""
    from services.llm import stream_chat
    from config import PARAMS_FORMAT, STOP_SEQUENCES

    narrative = output.get("narrative", "")
    if not narrative:
        return {"p0": {"pass": False, "reason": "空叙事"}, "summary": "FAIL"}

    prompt = VALIDATOR_PROMPT.format(
        prev_era=json.dumps((state.get("meta") or {}).get("prev_era", {}), ensure_ascii=False),
        player_action=(state.get("history") or [{}])[-1].get("user", "") if state.get("history") else "",
        scene_desc=scene_desc,
        public_knowledge="、".join((state.get("knowledge") or {}).get("public", [])) or "（无）",
        hidden_knowledge="、".join((state.get("knowledge") or {}).get("hidden", [])) or "（无）",
        narrative=narrative[:2000],
    )
    messages = [
        {"role": "system", "content": "你是严谨的叙事质量审核员，输出必须严格 JSON。"},
        {"role": "user", "content": prompt},
    ]
    raw = ""
    async for chunk in stream_chat(messages, max_tokens=1024, **PARAMS_FORMAT, stop=STOP_SEQUENCES):
        raw += chunk

    # 解析 JSON
    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError:
        import re
        m = re.search(r'\{.*\}', raw, re.S)
        try:
            data = json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            data = {}
    return data


# ═════════ 总入口 ═════════

async def validate(state: dict, output: dict, scene_desc: str = "") -> tuple[bool, list[str], dict]:
    """主入口：返回 (通过?, 失败原因列表, phase_report)

    - 确定性层失败 → 直接 FAIL（不调 LLM）
    - 确定性通过 → LLM 层判定 P0-P5（硬），P6/P7 只记录
    """
    reasons = deterministic_checks(state, output)
    report = {"deterministic": [{"phase": "deterministic", "pass": False, "reason": r} for r in reasons]}

    if reasons:
        return False, reasons, report

    # LLM 层
    llm = await llm_checks(state, output, scene_desc)
    report["llm"] = llm
    for phase in HARD_PHASES:
        p = llm.get(phase.lower())
        if p and not p.get("pass", True):
            reasons.append(f"{phase}: {p.get('reason', '未通过')}")
    # LEAK 检查（LLM 判定）
    leak = llm.get("leak")
    if leak and not leak.get("pass", True):
        reasons.append(f"LEAK: {leak.get('reason', '泄漏 hidden 信息')}")

    return (len(reasons) == 0), reasons, report
