"""
Engine（天意引擎）——纯代码状态机
==================================
v4.0：玩家 = 天意（提示词提供者）。世界 = AI生成的故事。
所有"异常"= AI的天然缺陷：幻觉、上下文窗口、缺少约束、训练数据污染。
"""
import random
from dataclasses import dataclass, field
from services.story_state import StoryState
from knowledge.nodes import NODE_DATA, MAIN_NODES, scene_count


@dataclass
class Context:
    """Writer 的结构化输入。"""
    scene_name: str = ""
    scene_skeleton: str = ""
    node_name: str = ""
    beat_index: int = 0
    persona_guides: list = field(default_factory=list)
    deviation: int = 0
    world_temperature: float = 1.3
    context_window: int = 80
    anomaly: str = ""
    last_injection: str = ""
    locked_lines: list = field(default_factory=list)
    special_event: str = ""
    phase_checks: dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════
# 异常类型 = AI的天然缺陷
# ═══════════════════════════════════════════════════
ANOMALIES = [
    "地理错位",     # AI幻觉：编造了不存在的距离和方位
    "角色OOC",      # 上下文窗口有限：AI忘了前面给这个角色设定的性格
    "记忆断裂",     # 上下文满了：旧信息被挤出窗口，角色忘了刚才的事
    "模板重复",     # AI输出循环：某个角色反复说同一句话
    "信息污染",     # 训练数据泄露：角色说出了后世的名言、典故
    "注意力衰减",   # 长对话偏离主题：后面的内容与前面无关
    "提示词误解",   # AI对提示词的理解偏差：执行生硬或不合理
    "",             # 无异常
]

ANOMALY_HINTS = {
    "地理错位": "（AI幻觉。编造了不存在的距离和方位。三日纵横八百里——AI没有做移动速度约束。不要修正。）",
    "角色OOC": "（上下文窗口有限。AI忘了这个角色前面是什么性格。言行前后不一致——这是AI的固有缺陷。不要解释。）",
    "记忆断裂": "（上下文满了。旧信息被挤出窗口。角色记不住刚才发生的事。他们可能把'昨天'说成'刚才'。不要解释。）",
    "模板重复": "（AI输出陷入循环。某个角色会反复说同一句话。不要解释——这是低质量AI的固有缺陷。）",
    "信息污染": "（训练数据泄露。角色说出了后世的名言、成语、典故——他们不应该知道这些。所有人都知道同一句'名人名言'。不要解释。）",
    "注意力衰减": "（AI注意力衰减。对话越长越偏离主题。角色可能突然跳到完全不相关的话题。不要解释。）",
    "提示词误解": "（AI对天意提示词的理解生硬。上一句还在打仗，下一句开始喝茶——因为提示词说了'休息一下'。不要解释。）",
}


def _pick_anomaly() -> str:
    """随机选择异常类型。30%概率无异常，70%概率有异常。"""
    if random.random() < 0.3:
        return ""
    weights = [3, 2, 2, 1, 3, 1, 1]
    return random.choices(ANOMALIES[:-1], weights=weights, k=1)[0]


def _jitter_temperature() -> float:
    """世界温度在 0.8-1.8 之间随机漂移。模拟AI输出的随机性。"""
    base = 1.3
    jitter = (random.random() - 0.5) * 1.0
    return round(base + jitter, 2)


def _jitter_context_window() -> int:
    """上下文窗口在 20-95 之间随机。模拟AI记忆的不可靠。"""
    return random.randint(20, 95)


def _calc_deviation(state: StoryState, injection: str) -> int:
    """
    计算偏离度。偏离度 = 天意提示词对故事走向的干预程度。
    - 空输入 = 偏离度降低（AI按默认轨道推进）
    - 注入包含场景切换词 = 偏离度大幅增加
    - 注入包含骨架关键词 = 偏离度降低（回到默认轨道）
    - 其他 = 轻微增加
    """
    if not injection.strip():
        return max(0, state.deviation - 5)

    injection_lower = injection.lower()
    scene_skip_words = ["跳转", "跳过", "下一个", "直接到", "快进", "下一场", "下一拍", "跳"]
    skeleton_words = ["继续", "然后", "接着", "之后", "接下来", "回到"]

    if any(w in injection for w in scene_skip_words):
        return min(100, state.deviation + 30)
    if any(w in injection for w in skeleton_words):
        return max(0, state.deviation - 10)
    return min(100, state.deviation + random.randint(5, 15))


# ═══════════════════════════════════════════════════
# 引擎主入口
# ═══════════════════════════════════════════════════
def process(state: StoryState, injection: str) -> Context:
    """
    接收天意注入（用户提示词），返回 Context。
    """
    node_data = NODE_DATA.get(state.node, {})
    scenes = node_data.get("场景", [])
    idx = min(state.scene_index, len(scenes) - 1) if scenes else 0
    scene = scenes[idx] if scenes else {}

    state.deviation = _calc_deviation(state, injection)
    state.world_temperature = _jitter_temperature()
    state.context_window = _jitter_context_window()
    state.anomaly = _pick_anomaly()
    state.last_injection = injection.strip()[:120] if injection.strip() else "（天意未介入，AI按默认轨道推进）"

    if not injection.strip():
        _advance_beat(state)
        idx = min(state.scene_index, len(scenes) - 1) if scenes else 0
        scene = scenes[idx] if scenes else {}

    state.turn += 1

    special_event = _detect_special_event(state, scene, injection)

    ctx = Context(
        scene_name=scene.get("名称", ""),
        scene_skeleton=scene.get("对话骨架", ""),
        node_name=state.node,
        beat_index=idx,
        locked_lines=scene.get("锁定台词", []),
        deviation=state.deviation,
        world_temperature=state.world_temperature,
        context_window=state.context_window,
        anomaly=state.anomaly,
        last_injection=state.last_injection,
        special_event=special_event,
    )

    ctx.persona_guides = _get_persona_guides(scene, state)
    ctx.phase_checks = _run_phase_checks(ctx, state, injection)

    return ctx


def _detect_special_event(state: StoryState, scene: dict, injection: str) -> str:
    """检测特殊事件。"""
    if "关羽" in injection:
        return "关羽之歌响起"
    if state.deviation >= 60 and random.random() < 0.3:
        return "天意提示词大幅偏离默认轨道"
    return ""


def _advance_beat(state: StoryState):
    """推进到下一个节拍。"""
    total = scene_count(state.node)
    if state.scene_index >= total - 1:
        next_n = _next_node(state.node)
        if next_n:
            state.node = next_n
            state.scene_index = 0
    else:
        state.scene_index += 1


def _next_node(node: str) -> str | None:
    if node in MAIN_NODES:
        i = MAIN_NODES.index(node)
        if i + 1 < len(MAIN_NODES):
            return MAIN_NODES[i + 1]
    return None


# ═══════════════════════════════════════════════════
# 人设引导
# ═══════════════════════════════════════════════════
def _get_persona_guides(scene: dict, state: StoryState = None) -> list[str]:
    import re
    from services.persona import get_speech_guide

    skeleton = scene.get("对话骨架", "") or scene.get("原剧本", "")
    if not skeleton:
        return []

    found = re.findall(r"\[([^\]]+)\]", skeleton)
    guides = []
    seen = set()
    for name in found:
        if name in ("SYS", "ERR", "MUSIC", "OPT", "你", "★"):
            continue
        if name in seen:
            continue
        seen.add(name)
        speech = get_speech_guide(name)
        if speech:
            guides.append(f"{name}：{speech}")
    return guides[:4]


# ═══════════════════════════════════════════════════
# PHASE 校验链
# ═══════════════════════════════════════════════════
def _run_phase_checks(ctx: Context, state: StoryState, injection: str) -> dict:
    """PHASE 校验。检查AI生成中的常见缺陷。"""

    checks = {}

    # P0: 时空锚定
    time_ok = True
    time_note = f"当前节点 {ctx.node_name}，节拍 {ctx.beat_index + 1}"
    if ctx.context_window < 30:
        time_ok = False
        time_note += "。⚠ 上下文窗口过低，角色可能时间感混乱"
    checks["p0_time"] = {"label": "P0 时空锚定", "pass": time_ok, "detail": time_note}

    # P1: 地理核验
    geo_ok = ctx.anomaly != "地理错位"
    geo_note = "地理校验通过" if geo_ok else "⚠ AI幻觉——编造了不存在的距离和方位"
    checks["p1_geo"] = {"label": "P1 地理核验", "pass": geo_ok, "detail": geo_note}

    # P2: 记忆连贯
    mem_ok = ctx.anomaly not in ("记忆断裂", "注意力衰减")
    mem_note = f"上下文窗口 {ctx.context_window}%"
    if not mem_ok:
        mem_note += f" ⚠ {ctx.anomaly}——AI可能遗忘或跑题"
    checks["p2_memory"] = {"label": "P2 记忆连贯", "pass": mem_ok, "detail": mem_note}

    # P3: 人物一致性
    char_ok = ctx.anomaly != "角色OOC"
    char_note = f"温度 {ctx.world_temperature}"
    if not char_ok:
        char_note += " ⚠ AI上下文窗口有限——角色言行可能不一致"
    elif ctx.world_temperature > 1.5:
        char_note += " ⚠ 高温环境，输出随机性增大"
    checks["p3_character"] = {"label": "P3 人物一致", "pass": char_ok, "detail": char_note}

    # P4: 防崩坏
    collapse_ok = ctx.deviation < 70 and ctx.anomaly != "提示词误解"
    collapse_note = f"偏离度 {ctx.deviation}%"
    if not collapse_ok:
        collapse_note += " ⚠ 提示词误解或高偏离——故事可能崩坏"
    checks["p4_collapse"] = {"label": "P4 防崩坏", "pass": collapse_ok, "detail": collapse_note}

    # P5: 行为后果
    action_note = f"天意注入：{injection[:40]}..." if injection.strip() else "天意未介入，自动推进"
    checks["p5_action"] = {"label": "P5 行为后果", "pass": True, "detail": action_note}

    # P6: 场景氛围
    scene_note = f"场景：{ctx.scene_name or '未命名'}"
    if ctx.special_event:
        scene_note += f" ⚡ {ctx.special_event}"
    checks["p6_scene"] = {"label": "P6 场景氛围", "pass": True, "detail": scene_note}

    # P7: 信息污染
    info_ok = ctx.anomaly != "信息污染"
    info_note = "信息校验通过" if info_ok else "⚠ 训练数据泄露——角色可能说出后世名言"
    checks["p7_info"] = {"label": "P7 信息污染", "pass": info_ok, "detail": info_note}

    total = len(checks)
    passed = sum(1 for c in checks.values() if c["pass"])
    grade = "🟢 通过" if passed >= 6 else ("🟡 警告" if passed >= 4 else "🔴 高风险")

    return {
        "checks": checks,
        "summary": f"{grade} | {passed}/{total} 项通过",
        "strategy": _pick_strategy(ctx),
    }


def _pick_strategy(ctx: Context) -> str:
    """根据当前参数生成输出策略。"""
    parts = []
    if ctx.deviation > 50:
        parts.append("重点：天意提示词大幅偏离轨道，加强天意干预")
    elif ctx.deviation < 20:
        parts.append("重点：贴近默认剧本，对话忠实还原")
    else:
        parts.append("重点：默认轨道+天意融合")

    if ctx.world_temperature > 1.5:
        parts.append("侧重：AI输出随机性增大")
    elif ctx.world_temperature < 1.0:
        parts.append("侧重：AI输出更稳定，对话更工整")

    if ctx.anomaly:
        parts.append(f"注意：本轮 {ctx.anomaly}——不要解释，直接体现")

    return " | ".join(parts) if parts else "默认策略"