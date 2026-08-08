# -*- coding: utf-8 -*-
"""
Validator（校验层 · 8 PHASE 硬校验）
=====================================
依据: docs/引擎设计规范.md §3（映射自 AAA 规范）

两层结构：
1. 确定性层（快、免 LLM，可重复）——拆「硬/软」：
   硬（触发重写）：P7a 无选项、P1b hidden 泄漏（长片段 n-gram 匹配）、P0a 时空倒退
   软（只记录不重写）：P6 五感、P7 字数/描写均衡/情感链/毒句、P1a 角色名
2. LLM 层（一次调用出 P0-P5 判定 JSON）：
   - P0 时空锚定 / P1 真实性 / P2 意图记忆 / P3 人物一致 / P4 防崩坏 / P5 行为后果
   - P6 场景氛围 / P7 输出质量（自检，只记录不触发重写）

硬失败项 → retry_reasons 回灌 narrate（重写 ≤2 次）
"""
import json
import logging
import re

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


def _distinctive_fragments(s: str, min_len: int = 6, max_len: int = 12) -> set:
    """取文本中所有连续片段（min_len..max_len），作为泄漏判定的特征。

    只用 ≥6 字的长片段：短的世界观词（"黄金军""洛阳""天意""张角"）是叙事必用的
    正常词汇，若作为泄漏特征会误报（曾导致每轮强制重写、LLM 层 P0-P5 被短路）。
    """
    frags = set()
    n = len(s)
    if n < min_len:
        return frags
    hi = min(max_len, n)
    for L in range(min_len, hi + 1):
        for i in range(0, n - L + 1):
            frags.add(s[i:i + L])
    return frags


def check_hidden_leak(narrative: str, hidden: list[str]) -> list[str]:
    """P1b+LEAK: narrative 是否泄漏 hidden 知识（长特征片段匹配）。

    判定：叙事中只要出现某条 hidden 知识的一个 ≥6 字连续片段，即视为泄漏。
    2-3 字的世界观通用词（人名/地名/核心概念）不再单独触发。
    """
    if not hidden:
        return []
    leaks = []
    for h in hidden:
        h_clean = re.sub(r"[，。！？、；：\s·…—'\"“”‘’]", "", h)
        frags = _distinctive_fragments(h_clean)
        for frag in frags:
            if frag and frag in narrative:
                leaks.append(f"LEAK: 泄漏 hidden 信息『{frag}』")
                break  # 每条 hidden 最多报一次
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


# ── P1a: 角色名白名单 ──
# 从 writer 导入的已知角色名（含扩充的 NPC 名）
from .writer import KNOWN_NAMES as _P1A_KNOWN_NAMES

# 排除泛称名词（非角色名的常见词，避免误报）
_P1A_EXCLUDE = {"黄金", "黄巾", "黄金军", "黄巾军", "苍天", "天下", "洛阳",
                "长安", "颍川", "徐州", "荆州", "官渡", "赤壁", "中原",
                "天子", "皇帝", "陛下", "主公", "将军", "丞相", "军师"}


def check_character_names(narrative: str) -> list[str]:
    """P1a: 叙事中出现的疑似角色名是否在已知白名单内。

    策略：检测「姓+名」双字组合（中文人名最常见形式），
    若不在 KNOWN_NAMES 或 _P1A_EXCLUDE 中，发出警告（软性，不计入硬失败）。
    排除：泛称词、地名、官职、单字名（容易误报）。
    """
    import re
    # 提取所有双字中文（跳过标点/空白）
    bigrams = set()
    # 取 2-3 字候选（中文人名通常 2-3 字），跳过英文/数字
    for m in re.finditer(r'[一-鿿]{2,3}', narrative):
        w = m.group(0)
        if w not in _P1A_EXCLUDE and w not in _P1A_KNOWN_NAMES:
            bigrams.add(w)
    # 只报告可能是人名的（含姓：首字在常见姓列表中）
    _COMMON_SURNAMES = {"曹", "刘", "关", "张", "孙", "周", "诸葛", "司马",
                        "赵", "马", "黄", "魏", "姜", "吕", "董", "袁",
                        "夏侯", "许", "典", "徐", "庞", "法", "鲁", "陆",
                        "陈", "王", "华", "贾", "郭", "荀", "程", "甘",
                        "太史", "公孙", "皇甫", "朱", "何", "丁", "邓",
                        "钟", "文", "颜", "高", "纪", "潘", "杨", "廖",
                        "蒋", "费", "吴", "韩", "鲍", "孔", "陶", "田"}
    unknowns = set()
    for w in bigrams:
        # 2 字词：首字必须是常见姓
        if len(w) == 2 and w[0] in _COMMON_SURNAMES:
            unknowns.add(w)
        # 3 字词：前两字是复姓
        elif len(w) == 3 and w[:2] in _COMMON_SURNAMES:
            unknowns.add(w)
    # 上限 3 个未知名（避免一个场景引入过多编造角色）
    if len(unknowns) > 3:
        return [f"P1: 疑似编造角色名过多({len(unknowns)}个): {', '.join(sorted(unknowns)[:5])}"]
    return []


# ── P7b: deslop 毒句式计数 ──
# 复用 services.deslop 的毒句式正则（不改文本，只计数）
from services.deslop import TOXIC_PATTERNS

# 引发硬失败的毒句式阈值（每个模式的最大容忍命中数）
_DESLOP_THRESHOLD = {
    "不是A而是B": 1,    # 出现 ≥2 次则 FAIL
    "神态模板": 2,       # 出现 ≥3 次则 FAIL
    "收束腔": 1,
}

_DESLOP_LABELS = {
    "不是A而是B": "不是A而是B句式",
    "带着状语": "带着…万能状语",
    "无情绪声线": "无情绪声线",
    "他知道": "他知道（告诉而非展示）",
    "比喻词": "比喻词堆叠",
    "神态模板": "神态模板（眼中闪过/嘴角勾起）",
    "收束腔": "抽象收束腔",
    "filler动作": "filler动作（深吸一口气/不禁）",
}


def check_deslop(narrative: str) -> list[str]:
    """P7b: 统计 AI 毒句式，超标则触发重写"""
    reasons = []
    for name, pat in TOXIC_PATTERNS.items():
        count = len(pat.findall(narrative))
        threshold = _DESLOP_THRESHOLD.get(name, 99)  # 未设阈值的模式不强制
        if count > threshold:
            label = _DESLOP_LABELS.get(name, name)
            reasons.append(f"P7: AI毒句式『{label}』出现{count}次（阈值≤{threshold}）")
    return reasons


# ── P6: 五感覆盖检测 ──

# 五感关键词（每类至少命中 1 个）
_SENSE_VISUAL = {"看", "见", "望", "光", "暗", "色", "影", "映", "照", "闪", "辉", "明", "黑",
                 "白", "红", "金", "青", "蓝", "赤", "黄", "绿", "紫", "烛", "灯", "火把", "星",
                 "目", "眼", "视", "观", "盯", "凝视", "注视", "远眺"}
_SENSE_AUDIO = {"听", "声", "响", "静", "喧", "喊", "叫", "鸣", "吼", "啸", "呼", "啸",
                "雷", "风", "雨声", "蹄", "鼓", "金", "铃", "嘶", "啼", "脚步", "耳"}
_SENSE_SMELL = {"闻", "味", "香", "臭", "腥", "焦", "腐", "烟", "血腥", "泥土", "草香",
                "酒香", "药味", "霉", "檀", "熏"}
_SENSE_TOUCH = {"冷", "热", "凉", "暖", "湿", "干", "风", "雨", "雪", "冰", "烫",
                "粗糙", "光滑", "硬", "软", "刺", "痛", "麻", "寒", "温", "触", "抚"}
_SENSE_TEMP = {"温", "寒", "燥", "闷", "潮", "凉意", "热气", "冷风", "暖阳"}

_SENSE_CATEGORIES = {
    "视觉": _SENSE_VISUAL, "听觉": _SENSE_AUDIO, "嗅觉": _SENSE_SMELL,
    "触觉": _SENSE_TOUCH, "温度": _SENSE_TEMP,
}


def check_five_senses(narrative: str) -> list[str]:
    """P6: 检测五感覆盖（光/声/味/温/触），至少覆盖 3 类"""
    if not narrative:
        return ["P6: 空叙事"]
    covered = []
    missing = []
    for cat, keywords in _SENSE_CATEGORIES.items():
        if any(kw in narrative for kw in keywords):
            covered.append(cat)
        else:
            missing.append(cat)
    if len(covered) < 3:
        return [f"P6: 五感覆盖不足（仅{len(covered)}类: {','.join(covered)}，缺: {','.join(missing)}）"]
    return []


# ── P7: 字数检测 ──

def check_word_count(narrative: str) -> list[str]:
    """P7: 叙事字数检测（目标 ≥600 字，硬下限 150 字）"""
    if not narrative:
        return ["P7: 空叙事"]
    # 去除英文/标点，统计中文字数
    import re
    cn_chars = len(re.findall(r'[一-鿿]', narrative))
    if cn_chars < 150:
        return [f"P7: 中文字数{cn_chars}严重不足（硬下限150）"]
    if cn_chars < 400:
        return [f"P7: 中文字数{cn_chars}偏低（建议≥600）"]
    return []


# ── P7: 描写均衡检测 ──

_ACTION_WORDS = {"挥", "走", "握", "拔", "转", "站", "坐", "冲", "杀", "推", "拉",
                 "骑", "奔", "跃", "踢", "举", "落", "抽", "按", "拍", "踏", "踹",
                 "策马", "奔驰", "翻身", "拔剑", "拱手", "下马", "上前", "退后"}
_DIALOGUE_MARKERS = {"「", "」", '"', '"', "“", "”", "："}  # 对话引导符 + 全角引号
_PSYCH_MARKERS = {"心", "想", "暗", "忖", "思", "忆", "感", "觉", "念", "意",
                  "记得", "知道", "明白", "觉得", "心想", "暗想", "思忖", "恍惚",
                  "心中", "心底", "脑海里", "疑虑", "猜测", "醒悟", "恍然"}
_ENV_WORDS = {"风", "雨", "树", "山", "火", "屋", "街", "天", "地", "草", "马",
              "灯", "路", "河", "云", "月", "星", "泥", "石", "营", "帐", "旗",
              "荒野", "密林", "古道", "城郭", "天空", "大地", "篝火", "残垣"}


def check_narrative_balance(narrative: str) -> list[str]:
    """P7: 描写均衡检测（动作/对话/心理/环境），至少覆盖 3 类"""
    if not narrative:
        return []
    score = 0
    missing = []
    if any(w in narrative for w in _ACTION_WORDS):
        score += 1
    else:
        missing.append("动作")
    if any(m in narrative for m in _DIALOGUE_MARKERS):
        score += 1
    else:
        missing.append("对话")
    if any(w in narrative for w in _PSYCH_MARKERS):
        score += 1
    else:
        missing.append("心理")
    if any(w in narrative for w in _ENV_WORDS):
        score += 1
    else:
        missing.append("环境")
    if score < 3:
        return [f"P7: 描写不均衡（仅覆盖{score}/4类，缺: {','.join(missing)}）"]
    return []


# ── P7: 情感链条检测 ──

_TRIGGER_WORDS = {"突然", "忽", "只见", "听到", "感到", "察觉", "发现", "传来", "远远"}
_BODY_WORDS = {"心跳", "手抖", "脸", "目", "瞳孔", "汗", "颤", "僵", "握紧",
               "呼吸", "胸口", "掌心", "脊背", "腿", "脚步", "眉头", "喉", "拳"}
_EMOTION_WORDS = {"怒", "喜", "惧", "忧", "惊", "疑", "慌", "沉", "悲", "恨",
                  "欣慰", "不安", "兴奋", "恐惧", "愤怒", "悲伤", "震惊", "疑虑"}
_BEHAVIOR_WORDS = {"站起", "后退", "前进", "拔剑", "转身", "喊", "喝", "冲",
                   "跪", "拜", "拱手", "策马", "挥手", "点头", "摇头", "叹息"}


def check_emotion_chain(narrative: str) -> list[str]:
    """P7: 情感链条检测（触发→生理→心理→行为），至少覆盖 3 段"""
    if not narrative:
        return []
    score = 0
    missing = []
    if any(w in narrative for w in _TRIGGER_WORDS):
        score += 1
    else:
        missing.append("触发")
    if any(w in narrative for w in _BODY_WORDS):
        score += 1
    else:
        missing.append("生理")
    if any(w in narrative for w in _EMOTION_WORDS):
        score += 1
    else:
        missing.append("心理")
    if any(w in narrative for w in _BEHAVIOR_WORDS):
        score += 1
    else:
        missing.append("行为")
    if score < 3:
        return [f"P7: 情感链条不完整（仅{score}/4段，缺: {','.join(missing)}）"]
    return []


def deterministic_checks(state: dict, output: dict) -> tuple[list[str], list[str]]:
    """确定性层全检：返回 (硬失败原因, 软自检原因)。

    硬失败（触发重写）：结构性/信息泄漏类，不修则叙事不可用。
    - P7a 选项为 0（无法游玩）｜P1b 泄漏 hidden｜P0a 时间倒退
    软自检（只记录，不触发重写）：质量类（P6 五感、P7 字数/均衡/情感链/毒句/角色名）。
    """
    hard: list[str] = []
    soft: list[str] = []

    # ── 硬：0 选项（无法游玩）──
    opt_reasons = check_options_count(output.get("options", []))
    # >3 由 writer 侧钳位（narrate 已 options[:3]），这里只把"无选项"当硬失败
    hard += [r for r in opt_reasons if "无选项" in r]

    # ── 硬：hidden 泄漏 / 时间倒退 ──
    hard += check_hidden_leak(
        output.get("narrative", ""),
        (state.get("knowledge") or {}).get("hidden", []),
    )
    hard += check_time_continuity(
        (state.get("meta") or {}).get("prev_era"),
        state.get("era", {}),
    )

    # ── 软：质量自检（记录不重写）──
    soft += [r for r in opt_reasons if "无选项" not in r]
    soft += check_character_names(output.get("narrative", ""))
    soft += check_deslop(output.get("narrative", ""))
    soft += check_five_senses(output.get("narrative", ""))
    soft += check_word_count(output.get("narrative", ""))
    soft += check_narrative_balance(output.get("narrative", ""))
    soft += check_emotion_chain(output.get("narrative", ""))
    return hard, soft


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

    # 解析 JSON（容错：LLM 可能输出数组/裸值，一律落回 dict）
    data = {}
    try:
        parsed = json.loads(raw.strip())
        if isinstance(parsed, dict):
            data = parsed
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', raw, re.S)
        if m:
            try:
                parsed = json.loads(m.group(0))
                if isinstance(parsed, dict):
                    data = parsed
            except json.JSONDecodeError:
                data = {}
    return data


# ═════════ 总入口 ═════════

async def validate(state: dict, output: dict, scene_desc: str = "") -> tuple[bool, list[str], dict]:
    """主入口：返回 (通过?, 失败原因列表, phase_report)

    - 确定性硬失败 → 直接 FAIL（不调 LLM）
    - 确定性软自检 → 只进 report，不触发重写
    - 确定性通过 → LLM 层判定 P0-P5（硬）+ LEAK；P6/P7 只记录
    """
    hard_reasons, soft_reasons = deterministic_checks(state, output)
    report = {
        "deterministic": [{"phase": "deterministic", "pass": False, "reason": r} for r in hard_reasons],
        "soft": [{"phase": "soft", "pass": False, "reason": r} for r in soft_reasons],
    }

    if hard_reasons:
        return False, hard_reasons, report

    # LLM 层
    llm = await llm_checks(state, output, scene_desc)
    report["llm"] = llm
    reasons = []
    for phase in HARD_PHASES:
        p = llm.get(phase.lower())
        if p and not p.get("pass", True):
            reasons.append(f"{phase}: {p.get('reason', '未通过')}")
    # LEAK 检查（LLM 判定）
    leak = llm.get("leak")
    if leak and not leak.get("pass", True):
        reasons.append(f"LEAK: {leak.get('reason', '泄漏 hidden 信息')}")

    return (len(reasons) == 0), reasons, report
