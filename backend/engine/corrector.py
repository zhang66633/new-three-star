# -*- coding: utf-8 -*-
"""
Corrector（修正节点 · 天意修正）
================================
依据: docs/引擎设计规范.md §5

- classify_tension: 0-30 none / 31-70 light / 71-100 heavy
- light 痕迹: 对话自然转向、巧合堆叠
- heavy 痕迹: 时间跳跃、记忆覆盖、事件重生成
- 呈现原则: 世界侧零提示，玩家是唯一察觉差异的人
"""
import logging
import random

logger = logging.getLogger(__name__)

# 修正痕迹池（heavy 含时间跳跃——场景切换时用；此处 light/heavy 选择）
LIGHT_TRACES = ["对话自然转向", "巧合堆叠"]
HEAVY_TRACES = ["时间跳跃", "记忆覆盖", "事件重生成"]

CORRECTOR_PROMPT = """【情境】玩家试图改变历史大势。世界以完全正常的方式回应（不点明、不解释、不出现"修正/天意/系统"等字眼）。

【修正痕迹】{trace}（{trace_desc}）
【玩家干预】{player_action}
【当前场景】{scene_desc}
【原叙事】{narrative}

【要求】
1. 基于原叙事改写，融入修正痕迹的呈现（世界侧完全正常）
2. 历史结果与史实一致（或按骨架设定），但过程以痕迹方式自然达成
3. 玩家是唯一察觉差异的人——叙事可通过玩家视角暗示"似乎哪里不对"，但世界侧无人讨论
4. 保持 300-600 字，第二人称"你"
5. 输出严格 JSON: {{"narrative": "...", "options": [...]}}（选项格式同前）
""".strip()

TRACE_DESC = {
    "对话自然转向": "关键话题被正常话题接走，NPC 顺着新话题说下去，没有任何突兀",
    "巧合堆叠": "一连串巧合抵消玩家干预（信使迷路/文书浸水/守卫换班），每件事都正常",
    "时间跳跃": "下一场景自然衔接在'几个月后'，中间过程被压缩，NPC 仿佛从未中断",
    "记忆覆盖": "NPC 后续言行与玩家所见矛盾，但正常地按'新记忆'行事，无人察觉",
    "事件重生成": "历史结果以正常叙述达成（如粮仓'自己烧了'），叙述如常仿佛本该如此",
}


def classify_tension(t: int) -> str:
    """tension 档位判定"""
    if t <= 30:
        return "none"
    if t <= 70:
        return "light"
    return "heavy"


def pick_trace(tier: str) -> str:
    """按档位选修正痕迹"""
    pool = LIGHT_TRACES if tier == "light" else HEAVY_TRACES
    return random.choice(pool)


async def apply_correction(state: dict, output: dict, scene_desc: str, tier: str) -> dict:
    """执行修正：返回修正后的 output（narrative 改写 + corrected 记录）"""
    from services.llm import stream_chat
    from config import PARAMS_NARRATIVE, STOP_SEQUENCES, QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL

    trace = pick_trace(tier)
    narrative = output.get("narrative", "")

    prompt = CORRECTOR_PROMPT.format(
        trace=trace,
        trace_desc=TRACE_DESC.get(trace, ""),
        player_action=(state.get("history") or [{}])[-1].get("user", ""),
        scene_desc=scene_desc,
        narrative=narrative[:1500],
    )
    messages = [
        {"role": "system", "content": "你是世界修正器，输出严格 JSON。世界侧一切正常。"},
        {"role": "user", "content": prompt},
    ]
    # 双模型试验：修正（主控）走 Qwen3.5——结构化 JSON 输出稳；key 由 stream_chat 解析
    # （请求级 X-QWEN-API-Key 优先，无则回退 DeepSeek key=单模型模式）
    raw = ""
    _ctrl = dict(base_url=QWEN_BASE_URL, model=QWEN_MODEL)
    async for chunk in stream_chat(messages, max_tokens=2048, **PARAMS_NARRATIVE, stop=STOP_SEQUENCES, **_ctrl):
        raw += chunk

    # 解析 JSON
    import re
    try:
        import json
        data = json.loads(raw.strip())
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', raw, re.S)
        try:
            data = json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            data = {}

    if data.get("narrative"):
        output["narrative"] = data["narrative"]
        # 选项规范化（复用 writer 同款约束：type major/minor、tension int 钳位、dict 过滤、上限 3）
        if isinstance(data.get("options"), list):
            opts = [o for o in data["options"] if isinstance(o, dict)]
            for opt in opts[:3]:
                opt["type"] = "major" if opt.get("type") == "major" else "minor"
                try:
                    opt["tension"] = max(0, min(100, int(opt.get("tension", 0))))
                except (TypeError, ValueError):
                    opt["tension"] = 0
            output["options"] = opts[:3]

    # 记录修正
    corrected = list(state.get("corrected", []))
    trace_id = f"{trace}_{state.get('turn', 0)}"
    corrected.append(trace_id)
    state["corrected"] = corrected
    state["last_trace"] = trace_id
    # 知情者 flag（供 writer 玩家视角引用）
    flags = list(state.get("flags", []))
    if f"知情者_{trace}" not in flags:
        flags.append(f"知情者_{trace}")
    state["flags"] = flags

    logger.info(f"天意修正: {trace}（tier={tier}, tension={state.get('tension', 0)}）")
    return output
